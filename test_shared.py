"""Checks for the shared ledger (Supabase backend), against an in-memory stand-in for the two database functions in
supabase/schema.sql. No network is used and no real ledger is opened. Run after changing ledger.py:
    python test_shared.py
test_shared_live.py runs the same kind of round trip against a real Supabase project.
"""
import contextlib
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ledger as L  # noqa: E402

fails = 0


def check(name, ok, detail=""):
    global fails
    fails += not ok
    print(f"{'ok  ' if ok else 'FAIL'} {name}" + (f"\n      {str(detail)[:400]}" if not ok and detail else ""))


class Server:
    """Does what ledger_pull and ledger_push in supabase/schema.sql do."""

    def __init__(self):
        self.items, self.links, self.events, self.state = {}, {}, [], {}
        self.up, self.refuse, self.before_push, self.calls = True, False, None, []

    def __call__(self, fn, args, timeout):
        self.calls.append(fn)
        if not self.up:
            raise L.SharedError("can't reach the shared ledger (test: offline)")
        if self.refuse:
            raise L.SharedError("the shared ledger refused the request (401: ledger: token not recognised)")
        if fn == "ledger_pull":
            return {"items": [dict(i) for i in self.items.values()], "links": [dict(x) for x in self.links.values()],
                    "state": [dict(s) for s in self.state.values()], "by": "test"}
        if self.before_push:
            hook, self.before_push = self.before_push, None
            hook(self)
        b, renamed, missing = args["p_batch"], {}, []
        for it in b.get("items", []):
            it = dict(it)
            nid = it["id"]
            if it.pop("_new", False):
                if nid in self.items:
                    pfx = re.match(r"[A-Za-z]+", nid).group(0)
                    nums = [int(i[len(pfx):]) for i in self.items if re.fullmatch(pfx + r"\d+", i)]
                    nid = f"{pfx}{max(nums, default=0) + 1}"
                    renamed[it["id"]] = nid
                self.items[nid] = dict(it, id=nid)
            else:
                nid = renamed.get(nid, nid)
                if nid in self.items:
                    self.items[nid].update({k: v for k, v in it.items() if k != "id"})
                else:
                    missing.append(nid)
        for ln in b.get("links", []):
            ln = dict(ln, src=renamed.get(ln["src"], ln["src"]), dst=renamed.get(ln["dst"], ln["dst"]))
            self.links[(ln["src"], ln["rel"], ln["dst"])] = ln
        for ev in b.get("events", []):
            self.events.append(dict(ev, item=renamed.get(ev.get("item"), ev.get("item")),
                                    project=ev.get("project") or b.get("project")))
        for st in b.get("state", []):
            self.state[st["key"]] = dict(st, value=renamed.get(st.get("value"), st.get("value")))
        return {"renamed": renamed, "missing": missing, "by": "test"}


def run(*args, stdin=None):
    """One command in this process, as hooks and sessions run it; returns stdout + stderr."""
    out, err = io.StringIO(), io.StringIO()
    old_argv, old_stdin = sys.argv, sys.stdin
    sys.argv = ["ledger.py", *args]
    sys.stdin = io.StringIO(json.dumps(stdin)) if stdin is not None else io.StringIO("")
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            L.main()
    except SystemExit as e:
        out.write(f"[exit {e.code}]")
    finally:
        sys.argv, sys.stdin = old_argv, old_stdin
    return out.getvalue() + err.getvalue()


def context(out):
    out = out.strip()
    return json.loads(out)["hookSpecificOutput"]["additionalContext"] if out.startswith("{") else ""


def machine(folder, owner="Sam"):
    """One machine's shared-ledger folder (its own cache), as shared-setup makes it."""
    d = os.path.join(folder, ".ledger")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "config.json"), "w", encoding="utf-8") as f:
        json.dump({"owner": owner, "backend": "supabase"}, f)
    return ["--dir", d]


def git(cwd, *args):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


tmp = tempfile.mkdtemp(dir=HERE, prefix="_test_tmp")
env_before = dict(os.environ)
try:
    srv = Server()
    L.RPC = srv
    L.PULL_FRESH = 0  # every command pulls, so each run sees the other machine's writes
    os.environ["LEDGER_PROJECT"] = "garden"
    A, B = machine(os.path.join(tmp, "laptop")), machine(os.path.join(tmp, "cloud"))

    # ---------------------------------------------------------------- one record, two machines
    out = run(*A, "add", "rule", "Never water at midday", "--quote", "never water at midday, it burns the leaves",
              "--basis", "owner-words", "--tags", "water,watering,midday")
    check("add on machine A goes to the server", "added R1" in out and "R1" in srv.items, out)
    check("the item is filed under this session's project", srv.items["R1"]["project"] == "garden", srv.items)
    check("the event log goes to the server", any(e["action"] == "add" and e["item"] == "R1" for e in srv.events))
    b = context(run(*B, "hook-start", "b", stdin={"cwd": tmp}))
    check("machine B's session start shows A's rule, with the owner's words", "R1" in b and "midday" in b, b)
    a = context(run(*B, "hook-start", "a", stdin={"cwd": tmp}))
    check("the brief names the shared ledger and the project", "shared ledger" in a and "`garden`" in a, a)
    check("machine B's cache keeps no events (the server has them)",
          not __import__("sqlite3").connect(L.DB).execute("SELECT COUNT(*) FROM events").fetchone()[0])
    check("nothing is written to ledger.jsonl (no record that could end up in a repository)",
          not os.path.exists(L.JSONL))

    # ---------------------------------------------------------------- edits merge by field
    run(*A, "add", "decision", "Drip irrigation", "--quote", "drip it is", "--basis", "owner-words",
        "--tags", "irrigation,drip,hoses")
    run(*B, "set", "D1", "status=done")
    run(*A, "set", "D1", "priority=1")
    check("two machines editing different fields of one item keep both edits",
          srv.items["D1"]["status"] == "done" and int(srv.items["D1"]["priority"]) == 1, srv.items["D1"])
    run(*B, "set", "D1", "status=active")

    # ---------------------------------------------------------------- the same new ID from two machines
    def other_session_adds_d2(s):
        s.items["D2"] = {"id": "D2", "project": "garden", "kind": "decision", "title": "Raised beds",
                         "created": "2026-01-01 10:00", "updated": "2026-01-01 10:00", "status": "active",
                         "priority": 2, "body": "", "quote": "", "source": "", "who": "owner", "basis": "",
                         "owner": "", "tags": ""}
    srv.before_push = other_session_adds_d2
    out = run(*A, "add", "decision", "Mulch the beds", "--quote", "mulch everything", "--serves", "R1")
    check("a new item whose ID another session took first is renumbered, and the session is told",
          "D2 is now D3" in out and srv.items["D3"]["title"] == "Mulch the beds"
          and srv.items["D2"]["title"] == "Raised beds", out)
    check("its links follow the new ID", ("D3", "serves", "R1") in srv.links, list(srv.links))
    check("the machine's cache follows too", "Mulch the beds" in run(*A, "show", "D3")
          and "Raised beds" in run(*A, "show", "D2"))

    p = context(run(*B, "hook-prompt", stdin={"cwd": tmp, "prompt": "actually water at midday from now on"}))
    check("machine B's prompt hook flags A's rule (once the ledger holds a few standing items)", "LEDGER CHECK" in p and "R1" in p, p)

    # ---------------------------------------------------------------- projects
    os.environ["LEDGER_PROJECT"] = "shed"
    run(*A, "add", "rule", "Shed paint is green", "--quote", "green, like the gate", "--tags", "paint,green")
    run(*A, "add", "rule", "Ask before buying anything", "--quote", "ask me before you buy anything",
        "--project", "all", "--tags", "buy,money")
    run(*A, "focus", "R2", "--quote", "the shed first")
    check("an event is filed under its item's project, not the session's",
          [e["project"] for e in srv.events if e["item"] == "R3" and e["action"] == "add"] == ["all"],
          [e for e in srv.events if e["item"] == "R3"])
    os.environ["LEDGER_PROJECT"] = "garden"
    b = context(run(*B, "hook-start", "b", stdin={"cwd": tmp}))
    check("a garden session sees garden items and 'all' items, not the shed's",
          "R1" in b and "R3" in b and "Shed paint" not in b, b)
    a = context(run(*B, "hook-start", "a", stdin={"cwd": tmp}))
    check("each project keeps its own focus", "None chosen" in a and "R2" not in a.split("## Current focus")[1][:200], a)
    check("the brief mentions the other projects", "shed (" in a, a)
    os.environ["LEDGER_PROJECT"] = "shed"
    run(*A, "add", "ref", "Shed plans: GitHub sam/shed, branch plans -> PLANS.md")
    os.environ["LEDGER_PROJECT"] = "garden"
    run(*A, "add", "ref", "Garden report: GitHub sam/garden, branch analysis -> REPORT.md", "--basis", "my-call")
    a = context(run(*B, "hook-start", "a", stdin={"cwd": tmp}))
    check("the brief names this project's pointers to earlier work, not other projects'",
          "Read first" in a and "REPORT.md" in a and "PLANS.md" not in a, a)
    check("check stays in the project", "Shed paint" not in run(*B, "check", "paint", "green"))
    check("list stays in the project unless asked", "Shed paint" not in run(*B, "list")
          and "Shed paint" in run(*B, "list", "--all-projects"))
    long_body = "Focus: grow food.\n- Why: " + "tomatoes and beans, " * 50 + "END-OF-FOCUS"
    run(*A, "add", "goal", "Grow our own food", "--project", "all", "--body", long_body, "--quote", long_body)
    out = run(*A, "focus", "G1", "--project", "all")
    a = context(run(*B, "hook-start", "a", stdin={"cwd": tmp}))
    check("a focus set on 'all' heads part a of a project that has none, printed whole (past 600 characters)",
          "G1 Grow our own food" in a and "for every project" in a and "END-OF-FOCUS" in a
          and "- Why: tomatoes" in a, a[:1500])
    b = context(run(*B, "hook-start", "b", stdin={"cwd": tmp}))
    check("part b lists the focus goal without a cut-off copy of its text",
          "G1 Grow our own food" in b and "full text is in part a" in b and "END-OF-FOCUS" not in b, b)
    os.environ["LEDGER_PROJECT"] = "shed"
    check("a project's own focus wins over the one on 'all'",
          "R2 Shed paint" in context(run(*B, "hook-start", "a", stdin={"cwd": tmp})).split("## Read first")[0])
    check("the shed session sees its focus", "R2 Shed paint" in context(run(*B, "hook-start", "a",
                                                                          stdin={"cwd": tmp})))
    os.environ["LEDGER_PROJECT"] = "garden"

    # ---------------------------------------------------------------- offline
    srv.up = False
    out = run(*A, "add", "task", "Buy a soaker hose", "--serves", "D1")
    check("offline: the change is kept on the machine, and the session is told", "added T1" in out
          and "saved on this machine" in out and os.path.exists(L.OUTBOX), out)
    a = context(run(*A, "hook-start", "a", stdin={"cwd": tmp}))
    check("offline: the brief says so and still shows the last copy", "SHARED LEDGER PROBLEM" in a and "T1" in a, a)
    out = run(*A, "set", "T1", "status=in-progress")
    check("offline: a second change waits behind the first", sum(1 for _ in open(L.OUTBOX)) == 2, out)

    def other_session_adds_t1(s):
        s.items["T1"] = dict(s.items["D2"], id="T1", kind="task", title="Weed the beds", status="open")
    srv.up, srv.before_push = True, other_session_adds_t1
    out = run(*A, "list")
    check("back online: waiting changes are sent first, the clash renumbered",
          not os.path.exists(L.OUTBOX) and srv.items["T2"]["title"] == "Buy a soaker hose"
          and srv.items["T1"]["title"] == "Weed the beds", out)
    check("back online: the later change follows the renumbered item",
          srv.items["T2"]["status"] == "in-progress" and srv.items["T1"]["status"] == "open")
    check("back online: the problem note is gone",
          "SHARED LEDGER PROBLEM" not in context(run(*A, "hook-start", "a", stdin={"cwd": tmp})))

    srv.refuse = True
    a = context(run(*B, "hook-start", "a", stdin={"cwd": tmp}))
    check("a refused token shows in the brief", "token not recognised" in a, a)
    srv.refuse = False

    # ---------------------------------------------------------------- the project name
    repo = os.path.join(tmp, "Garden-App")
    os.makedirs(repo)
    git(repo, "init", "-q")
    git(repo, "remote", "add", "origin", "https://github.com/someone/Garden-App.git")
    check("project = the repository's name from its remote", L.project_for(repo) == "garden-app",
          L.project_for(repo))
    os.makedirs(os.path.join(repo, "src"))
    check("from a folder inside it too", L.project_for(os.path.join(repo, "src")) == "garden-app")
    plain = os.path.join(tempfile.mkdtemp(), "Notes")  # outside any repository
    os.makedirs(plain)
    check("no repository: the folder's name", L.project_for(plain) == "notes", L.project_for(plain))
    del os.environ["LEDGER_PROJECT"]
    run(*A, "hook-start", "a", stdin={"cwd": repo})
    check("a hook takes the project from the session's folder", L.PROJECT == "garden-app", L.PROJECT)
    check("shared-ledger hooks run in any folder", L.in_scope({"cwd": plain}))

    # ---------------------------------------------------------------- setup commands
    os.environ["LEDGER_HOME"] = home = os.path.join(tmp, "home", ".ledger")
    os.environ["CLAUDE_CONFIG_DIR"] = cdir = os.path.join(tmp, "home", ".claude")
    os.makedirs(cdir)
    with open(os.path.join(cdir, "settings.json"), "w") as f:
        json.dump({"model": "keep-me", "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo hi"}]}]}}, f)
    out = run("shared-setup", "--owner", "Sam", "--url", "https://example.invalid", "--key", "sb_publishable_x")
    st = json.load(open(os.path.join(cdir, "settings.json")))
    check("shared-setup writes the config and the machine-wide hooks, keeping other settings",
          json.load(open(os.path.join(home, "config.json")))["backend"] == "supabase" and st["model"] == "keep-me"
          and st["hooks"]["Stop"] and "hook-prompt" in st["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"], out)
    check("shared-setup tests the connection", "connected as token 'test'" in out, out)
    run("shared-setup")
    st = json.load(open(os.path.join(cdir, "settings.json")))
    check("running it again doesn't double the hooks", len(st["hooks"]["SessionStart"]) == 1, st["hooks"])
    check("the shared folder ignores itself in git", open(os.path.join(home, ".gitignore")).read() == "*\n")
    out = run("new-token", "laptop", "--save")
    tok = json.load(open(os.path.join(home, "credentials.json")))["token"]
    check("new-token saves the token and prints only its hash",
          tok not in out and hashlib.sha256(tok.encode()).hexdigest() in out
          and json.load(open(os.path.join(home, "credentials.json")))["url"] == "https://example.invalid", out)
    out = run("new-token", "cloud")
    tfile = os.path.join(home, "token-cloud.txt")
    check("new-token without --save writes it to a file to copy", os.path.isfile(tfile)
          and open(tfile).read().strip() not in out, out)
    check("new-token refuses an odd label", "usage" in run("new-token", "x'; drop table"))
    out = run("shared-repo", "--root", repo)
    rs = json.load(open(os.path.join(repo, ".claude", "settings.json")))
    cmd = rs["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    check("shared-repo adds cloud-only hooks that never fail a session",
          'CLAUDE_CODE_REMOTE" = "true"' in cmd and cmd.endswith("|| true") and "hook-start a" in cmd, cmd)
    out = run("--dir", home, "shared-status")
    check("shared-status says where credentials come from, never the values",
          "credentials.json" in out and tok not in out and "sb_publishable_x" not in out, out)
finally:
    os.environ.clear()
    os.environ.update(env_before)
    gc = __import__("gc")
    gc.collect()

    def writable(func, path, _):
        os.chmod(path, 0o700)
        func(path)
    shutil.rmtree(tmp, onerror=writable)

print("\nall passed" if not fails else f"\n{fails} FAILED")
sys.exit(1 if fails else 0)
