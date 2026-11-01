"""Checks for the ledger tool. Everything runs in throwaway folders next to this file (_test_tmp*), which are removed
afterwards; no real ledger is opened. Run after changing ledger.py:
    python test_ledger.py
"""
import contextlib
import gc
import io
import json
import os
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ledger as L  # noqa: E402

TOOL = os.path.join(HERE, "ledger.py")
fails = 0


def check(name, ok, detail=""):
    global fails
    fails += not ok
    print(f"{'ok  ' if ok else 'FAIL'} {name}" + (f"\n      {str(detail)[:400]}" if not ok and detail else ""))


def run(*args, stdin=None):
    """Run one command in this process, as the hooks and sessions do; return what it printed."""
    buf = io.StringIO()
    old_argv, old_stdin = sys.argv, sys.stdin
    sys.argv = ["ledger.py", *args]
    sys.stdin = io.StringIO(json.dumps(stdin)) if stdin is not None else io.StringIO("")
    try:
        with contextlib.redirect_stdout(buf):
            L.main()
    except SystemExit as e:
        buf.write(f"[exit {e.code}]")
    finally:
        sys.argv, sys.stdin = old_argv, old_stdin
    return buf.getvalue()


def proc(*args, cwd=None, stdin=""):
    """Run the tool as a separate process (a fresh cache each time, like a new session)."""
    r = subprocess.run([sys.executable, TOOL, *args], cwd=cwd, input=stdin, capture_output=True, text=True,
                       encoding="utf-8")
    return r.stdout + r.stderr


def git(cwd, *args):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


def context(out):
    return json.loads(out)["hookSpecificOutput"]["additionalContext"] if out.strip() else ""


def new_ledger(folder, owner="Sam"):
    d = os.path.join(folder, ".ledger")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "config.json"), "w", encoding="utf-8") as f:
        json.dump({"owner": owner}, f)
    return d


tmp = tempfile.mkdtemp(dir=HERE, prefix="_test_tmp")
try:
    # ---------------------------------------------------------------- the commands, on one ledger
    repo = os.path.join(tmp, "garden")
    d = new_ledger(repo)
    D = ["--dir", d]
    out = run(*D, "add", "goal", "Plant a vegetable garden", "--quote", "I want tomatoes this summer",
              "--basis", "owner-words", "--tags", "garden,tomatoes,vegetables")
    check("add gives the first goal G1", "added G1" in out, out)
    run(*D, "add", "rule", "Never water at midday", "--quote", "never water at midday, it burns the leaves",
        "--basis", "sam-words", "--tags", "water,watering,midday,sprinkler", "--quiet")
    run(*D, "add", "decision", "Use drip irrigation for the beds", "--quote", "drip it is",
        "--basis", "owner-picked-rec", "--tags", "drip,irrigation,beds,hose", "--quiet")
    for kind, title, tags in (("rule", "Keep receipts for every tool", "receipts,tools,shopping"),
                              ("rule", "No pesticides", "pesticide,spray,bugs"),
                              ("decision", "Paint the fence green", "fence,paint,green"),
                              ("decision", "Fruit trees on the south side", "fruit,trees,south"),
                              ("decision", "Compost the kitchen scraps", "compost,kitchen,scraps"),
                              ("ask", "A budget of 500 dollars", "budget,money,cost"),
                              ("goal", "Shade for the patio", "shade,patio,umbrella")):
        run(*D, "add", kind, title, "--basis", "owner-words", "--quote", title.lower(), "--tags", tags, "--quiet")
    con = L.connect()
    check("an older ledger's basis (sam-words) is stored as owner-words",
          con.execute("SELECT basis FROM items WHERE id='R1'").fetchone()[0] == "owner-words")
    con.close()
    out = run(*D, "show", "D1")
    check("show prints the item, its quote and the owner's name", "Use drip irrigation" in out and "drip it is" in out
          and "Sam:" in out and "project: main" in out, out)
    run(*D, "add", "question", "Which tomato variety?", "--owner", "Sam", "--tags", "tomato,variety", "--quiet")
    check("--owner with the owner's name means waiting on the owner",
          L.connect().execute("SELECT owner FROM items WHERE id='Q1'").fetchone()[0] == "owner")
    run(*D, "add", "note", "A side project", "--project", "shed", "--quiet")
    check("--project files an item under another project", "project: shed" in run(*D, "show", "N1"))
    out = run(*D, "check", "watering", "drip")
    check("check finds the items a topic touches", "R1" in out and "D1" in out and "G1" in out, out)
    check("find searches every status", "D1" in run(*D, "find", "irrigation"))

    out = run(*D, "override", "D1", "Use soaker hoses for the beds", "--quote",
              "actually let's use soaker hoses instead")
    check("override makes a new decision that supersedes the old", "D5 now supersedes D1" in out, out)
    check("the old decision is marked superseded", "— superseded" in run(*D, "show", "D1"))
    out = run(*D, "override", "R1", "Water at noon today", "--once", "--quote", "water at noon just today, it's cloudy")
    check("a one-time exception keeps the rule in force",
          "stays in force" in out and "— active" in run(*D, "show", "R1"), out)

    _, hits = L.match_prompt(L.connect(), "from now on let's run the sprinkler at midday")
    check("a change to a standing rule is flagged", "R1" in {h[1]["id"] for h in hits}, [h[1]["id"] for h in hits])
    _, hits = L.match_prompt(L.connect(), "thanks, looks good")
    check("small talk flags nothing", not hits, [h[1]["id"] for h in hits])

    # ---------------------------------------------------------------- hooks
    check("in scope: the repository", L.in_scope({"cwd": repo}))
    check("in scope: a folder inside it", L.in_scope({"cwd": os.path.join(repo, "src", "beds")}))
    for outside in (tmp, os.path.dirname(tmp), repo + "cat"):
        check(f"out of scope: {os.path.basename(outside)}", not L.in_scope({"cwd": outside}))
    run(*D, "focus", "G1", "--quote", "let's start with the garden")
    a = context(run(*D, "hook-start", "a", stdin={"cwd": repo}))
    check("session start, part a: focus, owner and the command to run",
          "Current focus" in a and "G1" in a and "Sam" in a and "--dir" in a and "ledger.jsonl" in a, a)
    b = context(run(*D, "hook-start", "b", stdin={"cwd": repo}))
    check("session start, part b: goals, asks, decisions, rules", all(x in b for x in ("G1", "A1", "D5", "R1")), b)
    check("each hook part stays under the 10,000-character cap", len(a) < 10000 and len(b) < 10000)
    check("session start outside the repository prints nothing", run(*D, "hook-start", "a", stdin={"cwd": tmp}) == "")
    p = context(run(*D, "hook-prompt", stdin={"cwd": repo, "prompt": "from now on let's run the sprinkler at midday"}))
    check("the prompt hook flags the rule", "LEDGER CHECK" in p and "R1" in p and "Sam's message" in p, p)
    check("the prompt hook ignores app notifications",
          run(*D, "hook-prompt", stdin={"cwd": repo, "prompt": "<task-notification>midday</task-notification>"}) == "")
    run(*D, "hook-precompact", stdin={"cwd": repo})
    hand = os.listdir(os.path.join(d, "handoffs")) if os.path.isdir(os.path.join(d, "handoffs")) else []
    check("before compaction, a handoff file is written", len(hand) == 1, hand)
    check("hooks stay quiet where there's no ledger",
          proc("hook-start", "a", cwd=tmp, stdin=json.dumps({"cwd": tmp})).strip() == "")

    # ---------------------------------------------------------------- exports and the text record
    page = open(L.HTML, encoding="utf-8").read()
    check("ledger.html shows the items", "Never water at midday" in page and "soaker hoses" in page)
    check("BRIEF.md is written", "Ledger brief" in open(L.BRIEF, encoding="utf-8").read())
    rec = [json.loads(x) for x in open(L.JSONL, encoding="utf-8").read().splitlines()]
    kinds = {next(iter(r)) for r in rec}
    check("ledger.jsonl holds items, links, events and state", kinds == {"item", "link", "event", "state"}, kinds)
    check("the cache's own bookkeeping isn't in ledger.jsonl",
          not any(r.get("state", {}).get("key") == "jsonl_hash" for r in rec))
    before = open(L.JSONL, "rb").read()
    run(*D, "export")
    check("exporting twice gives the same bytes (clean git diffs)", open(L.JSONL, "rb").read() == before)

    snap = {t: L.connect().execute(f"SELECT * FROM {t} ORDER BY 1,2").fetchall() for t in ("items", "links", "state")}
    snap = {t: [tuple(r) for r in rows if t != "state" or r[0] != "jsonl_hash"] for t, rows in snap.items()}
    nev = L.connect().execute("SELECT COUNT(*) FROM events").fetchone()[0]
    os.remove(L.DB)
    con = L.connect()
    again = {t: [tuple(r) for r in con.execute(f"SELECT * FROM {t} ORDER BY 1,2")
                 if t != "state" or r[0] != "jsonl_hash"] for t in ("items", "links", "state")}
    con.close()
    check("deleting ledger.db loses nothing: it's rebuilt from ledger.jsonl",
          again == snap and L.connect().execute("SELECT COUNT(*) FROM events").fetchone()[0] == nev)
    check("the rebuilt cache searches again", "D1" in run(*D, "find", "irrigation"))
    check("the focus survives the rebuild", "G1" in run(*D, "focus"))

    # A union merge from two machines: an edit on each side, and a clashing new ID.
    lines = open(L.JSONL, encoding="utf-8").read().splitlines()
    g1 = next(json.loads(x)["item"] for x in lines if '"id": "G1"' in x)
    edited = dict(g1, status="done", updated="2099-01-01 10:00")
    t_a = {"id": "T1", "project": "main", "kind": "task", "title": "Buy seeds", "body": "", "quote": "", "source": "",
           "who": "claude", "basis": "", "status": "open", "owner": "", "priority": 2, "tags": "seeds",
           "created": "2099-01-01 09:00", "updated": "2099-01-01 09:00"}
    t_b = dict(t_a, title="Fix the gate", tags="gate", created="2099-01-01 09:05", updated="2099-01-01 09:05")
    with open(L.JSONL, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines + lines[:3] + [json.dumps({"item": x}) for x in (edited, t_a, t_b)]) + "\n")
    con = L.connect()
    rows = {r["title"]: r["id"] for r in con.execute("SELECT * FROM items WHERE kind='task'")}
    check("after a merge, duplicate lines collapse", con.execute("SELECT COUNT(*) FROM items WHERE id='G1'")
          .fetchone()[0] == 1)
    check("after a merge, the later edit of an item wins",
          con.execute("SELECT status FROM items WHERE id='G1'").fetchone()[0] == "done")
    check("two new items with one ID are both kept, the later renumbered",
          rows.get("Buy seeds") == "T1" and rows.get("Fix the gate") == "T2", rows)
    check("the renumbering shows in the audit", any("MERGE:" in w for w in L.audit(con)), L.audit(con))
    con.close()

    good = open(L.JSONL, encoding="utf-8").read()
    with open(L.JSONL, "w", encoding="utf-8") as f:
        f.write("<<<<<<< HEAD\n" + good + "=======\n>>>>>>> side\n")
    a = context(run(*D, "hook-start", "a", stdin={"cwd": repo}))
    check("conflict markers: the session is told, not fed a half-read ledger", "LEDGER FILE PROBLEM" in a, a)
    check("conflict markers: the file is left alone for the merge to finish",
          open(L.JSONL, encoding="utf-8").read().startswith("<<<<<<<"))
    check("conflict markers: commands refuse instead of guessing", "conflict marker" in run(*D, "list"))
    with open(L.JSONL, "w", encoding="utf-8") as f:
        f.write(good)

    # ---------------------------------------------------------------- import from an older ledger
    old_db = os.path.join(tmp, "old.db")
    oc = sqlite3.connect(old_db)
    oc.executescript(L.SCHEMA)
    for row in (("R1", "all", "rule", "Keep backups on the NAS", "sam-words", "sam"),
                ("D1", "website", "decision", "Boards sync nightly", "sam-picked-rec", "sam"),
                ("D2", "video", "decision", "Render at 24 fps", "sam-words", "sam"),
                ("Q1", "website", "question", "Which board first?", "", "")):
        oc.execute("INSERT INTO items(id,project,kind,title,basis,who,owner,status,created,updated) "
                   "VALUES(?,?,?,?,?,?,?,?,?,?)", (*row[:5], row[5] or "claude", "sam" if row[2] == "question" else "",
                                                 "active" if row[2] != "question" else "open",
                                                 "2026-10-17 22:00", "2026-10-17 22:00"))
    oc.execute("INSERT INTO links VALUES('D1','serves','R1','','2026-10-17 22:00')")
    oc.execute("INSERT INTO links VALUES('D2','serves','R1','','2026-10-17 22:00')")
    oc.execute("INSERT INTO events VALUES('2026-10-17 22:00','add','D1','{}')")
    oc.execute("INSERT INTO events VALUES('2026-10-17 22:00','add','D2','{}')")
    oc.commit()
    oc.close()
    d2 = new_ledger(os.path.join(tmp, "website"))
    out = proc("--dir", d2, "import", old_db, "--project", "website", "--as", "sam")
    check("import takes one project plus its 'all' items", "imported 3 items, 1 links, 1 events" in out, out)
    con = sqlite3.connect(os.path.join(d2, "ledger.db"))
    got = {r[0]: r[1:] for r in con.execute("SELECT id, project, basis, owner, who FROM items")}
    con.close()
    check("imported: the project becomes main, 'all' stays, other projects are left out",
          got.get("D1", ("",))[0] == "main" and got.get("R1", ("",))[0] == "all" and "D2" not in got, got)
    check("imported: sam-* bases and owner become owner-*", got.get("D1", (0, 0))[1] == "owner-picked-rec"
          and got.get("Q1", (0, 0, 0))[2] == "owner" and got.get("R1", (0, 0, 0, 0))[3] == "owner", got)
    check("imported items are in ledger.jsonl", '"Boards sync nightly"' in open(os.path.join(d2, "ledger.jsonl"),
                                                                           encoding="utf-8").read())
    check("import refuses a ledger that already has items", "already has items" in
          proc("--dir", d2, "import", old_db))

    # ---------------------------------------------------------------- init, git, and a real merge
    host = os.path.join(tmp, "host")
    os.makedirs(host)
    git(host, "init", "-q", "-b", "main")
    git(host, "config", "user.name", "Sam Tester")
    git(host, "config", "user.email", "tester@example.invalid")
    with open(os.path.join(host, "CLAUDE.md"), "w", encoding="utf-8") as f:
        f.write("# Host project\n\nExisting instructions.\n")
    out = proc("init", "--root", host)
    hd = os.path.join(host, ".ledger")
    check("init sets up .ledger with the owner from git", os.path.isfile(os.path.join(hd, "ledger.jsonl"))
          and json.load(open(os.path.join(hd, "config.json")))["owner"] == "Sam", out)
    st = json.load(open(os.path.join(host, ".claude", "settings.local.json"), encoding="utf-8"))
    cmds = [h["command"] for v in st["hooks"].values() for e in v for h in e["hooks"]]
    check("init adds the three hooks to settings.local.json, pointing at this ledger",
          set(st["hooks"]) == {"SessionStart", "UserPromptSubmit", "PreCompact"} and len(cmds) == 4
          and all("--dir" in c and "hook-" in c for c in cmds), cmds)
    cm = open(os.path.join(host, "CLAUDE.md"), encoding="utf-8").read()
    check("init keeps CLAUDE.md and adds the LEDGER.md import", "Existing instructions." in cm and "LEDGER.md" in cm, cm)
    proc("init", "--root", host)
    st2 = json.load(open(os.path.join(host, ".claude", "settings.local.json"), encoding="utf-8"))
    cm2 = open(os.path.join(host, "CLAUDE.md"), encoding="utf-8").read()
    check("running init again changes nothing twice", st2 == st and cm2 == cm)
    a = context(proc("hook-start", "a", cwd=host, stdin=json.dumps({"cwd": host})))
    check("a session in the host gets the brief (ledger found from the folder)", "Ledger brief" in a, a)

    git(host, "add", "-A")
    _, tracked = git(host, "status", "--porcelain", "-uall")
    check("git sees the record and settings, not the cache or the local hooks",
          ".ledger/ledger.jsonl" in tracked and ".ledger/config.json" in tracked and "ledger.db" not in tracked
          and "ledger.html" not in tracked and "BRIEF.md" not in tracked and "settings.local.json" not in tracked,
          tracked)
    H = ["--dir", hd]
    proc(*H, "add", "goal", "Ship the app", "--quote", "ship it", "--basis", "owner-words", "--quiet")
    git(host, "add", "-A")
    code, msg = git(host, "commit", "-q", "-m", "ledger: first goal")
    check("commit in the test repo", code == 0, msg)
    git(host, "checkout", "-q", "-b", "laptop")
    proc(*H, "add", "task", "Write the tests", "--serves", "G1", "--quiet")
    proc(*H, "set", "G1", "status=done")
    git(host, "commit", "-qam", "laptop work")
    git(host, "checkout", "-q", "main")
    out = proc(*H, "list", "--all")
    check("after switching branches the cache follows the file", "Ship the app — active" in out
          and "Write the tests" not in out, out)
    proc(*H, "add", "task", "Design the icon", "--serves", "G1", "--quiet")
    git(host, "commit", "-qam", "desktop work")
    code, msg = git(host, "merge", "-q", "--no-edit", "laptop")
    check("git merges the two ledgers without a conflict (union driver)", code == 0, msg)
    out = proc(*H, "list", "--all")
    check("after the merge both machines' tasks are there, the clash renumbered, the later edit kept",
          "Write the tests" in out and "Design the icon" in out and "Ship the app — done" in out, out)
finally:
    def writable(func, path, _):  # git's object files are read-only on Windows
        os.chmod(path, stat.S_IWRITE)
        func(path)
    gc.collect()  # close any sqlite connection still open, so Windows lets the folder go
    shutil.rmtree(tmp, onerror=writable)

print(f"\n{'all passed' if not fails else f'{fails} failed'}")
sys.exit(1 if fails else 0)
