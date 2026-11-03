"""Project ledger: one record per repository of the owner's words, rules, decisions, open questions, tasks, promises,
conflicts and lessons, with links between them, so AI coding sessions keep the owner's intent across sessions and
compactions.

Why: markdown handoffs and compaction summaries keep recent work and drop intent. The ledger is the single source of
truth for its repository. Claude Code hooks load its brief at every session start and after every compaction, check
each of the owner's messages against their standing rules, goals and decisions (override detection), and save a
handoff before every compaction. `check` must be run before offering options, planning a stage or writing a handoff.

Storage, in <repo>/.ledger/:
  ledger.jsonl   the record: plain text, one JSON object per line, committed to git and merged with git's union driver
  config.json    the owner's name
  ledger.db      a local SQLite cache, rebuilt from ledger.jsonl whenever that file changes (after a pull, say)
  BRIEF.md, ledger.html, handoffs/   generated
Only ledger.jsonl, config.json and the folder's .gitignore / .gitattributes are committed.

Setup: put this folder in a repository (as a git submodule, say tools/ledger), then from the repository root run
  python tools/ledger/ledger.py init [--owner NAME] [--private]
init creates .ledger/, adds the hooks to .claude/settings.local.json and adds LEDGER.md to CLAUDE.md. The hooks name
this machine's Python, so run init once on each machine after cloning; it's safe to re-run. --private keeps the
ledger's contents out of git.

Usage:  python <tool>/ledger.py [--dir <repo>/.ledger] <command>
  (without --dir: the nearest .ledger folder above the current folder, then above this tool)
  init [--owner NAME] [--private] [--root PATH]   set up a repository (see above)
  import OLD.db [--project P] [--as NAME]  copy items from an older ledger.db into this empty ledger: all of them,
                              or one project plus its "all" items; NAME = the person the old ledger called its owner
  brief [--project P]         regenerate BRIEF.md and print it (the whole brief, or one project plus "all")
  add KIND "title" [opts]     opts: --body --quote --source --who --basis --status --owner --tags --priority
                                    --project (default "main"; "all" = workspace-wide) --serves IDS --blocks IDS
                                    --supersedes IDS --conflicts IDS --about IDS
  override ID "new title" --quote "the owner's words" [--source S] [--once] [--tags T]
                              The owner changes a standing item: the new item supersedes ID (or, with --once, a
                              one-time exception is noted and ID stays in force). Prints what depends on ID, to review.
  focus ID|none [--quote Q] [--project P]   set the current focus (what the owner chose to work on); shown at the top of the brief
  set ID key=value ...        change fields (status, owner, priority, tags, body, quote, source, basis, title, project)
  link SRC REL DST [note]     REL: serves blocks depends_on supersedes conflicts about evidence resolves
  show ID                     one item with all its links
  find TEXT                   full-text search (all statuses)
  check TOPIC...              everything in force that touches a topic: run before acting
  match "text"                what the prompt hook would flag for this text (testing)
  list [--kind K] [--status S] [--owner O] [--project P] [--tag T] [--all]
  audit                       drift warnings
  handoff                     markdown handoff generated from the ledger
  export                      rewrite ledger.jsonl, BRIEF.md and ledger.html (also done after every write)
Shared ledger (one record in Supabase for all of the owner's sessions, local and cloud; see supabase/schema.sql):
  shared-setup [--owner NAME] [--url URL --key KEY] [--no-hooks] [--no-check]
                              use it on this machine: ~/.ledger (or LEDGER_HOME) gets the config and cache, and
                              ~/.claude/settings.json the hooks, so every session here sees it. The project is the
                              session's repository name (LEDGER_PROJECT overrides); "all" items show everywhere
  new-token LABEL [--save]    make an access token; prints the SQL that registers its hash, never the token
  shared-repo [--root PATH]   add cloud-only hooks to this repository's .claude/settings.json (commit it)
  shared-status               connection, project, last pull, changes waiting to be sent
Hooks (read the hook JSON on stdin; quiet outside the repository):
  hook-start a|b              SessionStart: part a = focus, conflicts, waiting on the owner, promises, tasks, audit;
                              part b = goals, the owner's asks, decisions, rules (each part stays under 10,000
                              characters)
  hook-prompt                 UserPromptSubmit: flags standing items the owner's message may override
  hook-precompact             PreCompact: writes handoffs/<time>.md from the ledger
"""
import datetime as dt
import hashlib
import html
import json
import math
import os
import pathlib
import re
import sqlite3
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DIRNAME = ".ledger"
BRIEF_MAX = 16000  # BRIEF.md is read on demand (no cap); each hook's own output stays under 10,000
HOOK_MAX = 9500  # each SessionStart hook's additionalContext is capped at 10,000 characters

LEDGER_DIR = DB = BRIEF = JSONL = HTML = CONFIG = HANDOFFS = WORKSPACE = OUTBOX = None
OWNER = "the owner"
SHARED = False  # True when config.json says "backend": "supabase": the record is the shared ledger, not ledger.jsonl
PROJECT = None  # shared ledger: this session's project (its repository's name); FAMILY = it plus "all"
FAMILY = None

KINDS = {  # kind: (id prefix, plain name; {o} = the owner's name)
    "goal": ("G", "goal"), "ask": ("A", "{o} asked for"), "rule": ("R", "rule"), "decision": ("D", "decision"),
    "question": ("Q", "open question"), "task": ("T", "task"), "defect": ("X", "defect"), "conflict": ("C", "conflict"),
    "promise": ("P", "my promise"), "lesson": ("L", "lesson"), "fact": ("F", "fact"), "ref": ("S", "file / source"),
    "note": ("N", "note"),
}
STATUSES = ["open", "active", "in-progress", "proposed", "waiting", "blocked", "done", "parked", "superseded",
            "rejected", "resolved"]
LIVE = ("open", "active", "in-progress", "proposed", "waiting", "blocked")
RELS = ["serves", "blocks", "depends_on", "supersedes", "conflicts", "about", "evidence", "resolves"]
BASES = {
    "owner-words": "{o}'s own words",
    "owner-overrode": "{o} chose this over my recommendation",
    "owner-picked-rec": "{o} picked my recommended option",
    "owner-approved": "{o} approved my plan",
    "my-call": "my own call, not confirmed by {o}",
    "my-promise": "I promised this",
    "notes": "from my earlier notes (no quote on file)",
    "measured": "measured / verified on disk",
}
SHORT_BASIS = {"owner-words": "{o}", "owner-overrode": "{o}, over my rec", "owner-picked-rec": "{o} picked my rec",
               "owner-approved": "{o} approved", "my-call": "MINE, unconfirmed", "my-promise": "my promise",
               "notes": "notes", "measured": "verified"}
PLURAL = {"goal": "Goals", "ask": "{o}'s asks", "rule": "Rules", "decision": "Decisions",
          "question": "Open questions", "task": "Tasks", "defect": "Defects", "conflict": "Conflicts",
          "promise": "My promises", "lesson": "Lessons", "fact": "Facts", "ref": "Files and sources", "note": "Notes"}
FIELDS = ["title", "body", "quote", "source", "who", "basis", "status", "owner", "priority", "tags", "project"]
ITEM_COLS = ["id", "project", "kind", "title", "body", "quote", "source", "who", "basis", "status", "owner",
             "priority", "tags", "created", "updated"]
DEFAULT_PROJECT = "main"  # items go here unless --project names another; "all" = workspace-wide (shared: the repo)


def o(text):
    """Fill the owner's name into a label."""
    return text.replace("{o}", OWNER)


def basis_label(b, short=False):
    return o((SHORT_BASIS if short else BASES).get(b, b))


# ---------------------------------------------------------------- where the ledger lives

def use_dir(path):
    """Point the module at one ledger folder (<repo>/.ledger)."""
    global LEDGER_DIR, DB, BRIEF, JSONL, HTML, CONFIG, HANDOFFS, WORKSPACE, OWNER, OUTBOX, SHARED
    LEDGER_DIR = os.path.abspath(path)
    DB, BRIEF, JSONL, HTML, CONFIG, OUTBOX = (os.path.join(LEDGER_DIR, n) for n in (
        "ledger.db", "BRIEF.md", "ledger.jsonl", "ledger.html", "config.json", "outbox.jsonl"))
    HANDOFFS = os.path.join(LEDGER_DIR, "handoffs")
    WORKSPACE = os.path.dirname(LEDGER_DIR)
    cfg = read_config()
    OWNER = cfg.get("owner") or "the owner"
    SHARED = cfg.get("backend") == "supabase"
    set_project(None)


def set_project(path):
    """Shared ledger: this session's project is its repository's name (LEDGER_PROJECT overrides)."""
    global PROJECT, FAMILY, DEFAULT_PROJECT
    if not SHARED:
        PROJECT, FAMILY, DEFAULT_PROJECT = None, None, "main"
        return
    PROJECT = os.environ.get("LEDGER_PROJECT") or project_for(path or os.getcwd())
    FAMILY = family_for(PROJECT)
    DEFAULT_PROJECT = PROJECT


def project_for(path):
    """The repository's name from its origin remote (the same on every machine and in the cloud), else the folder's."""
    code, url = git(["remote", "get-url", "origin"], path)
    name = re.split(r"[/:\\]", url.strip().rstrip("/"))[-1] if code == 0 and url.strip() else ""
    if not name:
        code, top = git(["rev-parse", "--show-toplevel"], path)
        name = os.path.basename(top.rstrip("/\\")) if code == 0 and top else os.path.basename(os.path.abspath(path))
    name = re.sub(r"\.git$", "", name).strip().lower()
    return name if name and name != "all" else "main"


def read_config():
    try:
        with open(CONFIG, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def find_dir():
    """LEDGER_DIR from the environment, else the nearest .ledger above the current folder, then above this tool."""
    if os.environ.get("LEDGER_DIR"):
        return os.environ["LEDGER_DIR"]
    for start in (os.getcwd(), HERE):
        d = os.path.abspath(start)
        while True:
            if os.path.isdir(os.path.join(d, DIRNAME)):
                return os.path.join(d, DIRNAME)
            parent = os.path.dirname(d)
            if parent == d:
                break
            d = parent
    return None


def slash(p):
    return p.replace("\\", "/")


def q(p):
    return f'"{p}"' if " " in p else p


def tool_cmd():
    """The exact command sessions should run on this machine for this ledger."""
    return (f"{q(slash(sys.executable))} {q(slash(os.path.join(HERE, 'ledger.py')))} "
            f"--dir {q(slash(LEDGER_DIR))}")


# ---------------------------------------------------------------- storage: ledger.jsonl is the record, ledger.db a cache

SCHEMA = """
CREATE TABLE IF NOT EXISTS items(
  id TEXT PRIMARY KEY, project TEXT NOT NULL DEFAULT 'main', kind TEXT NOT NULL, title TEXT NOT NULL,
  body TEXT DEFAULT '', quote TEXT DEFAULT '', source TEXT DEFAULT '', who TEXT DEFAULT 'claude',
  basis TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'open', owner TEXT DEFAULT '', priority INTEGER DEFAULT 2,
  tags TEXT DEFAULT '', created TEXT NOT NULL, updated TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS links(
  src TEXT NOT NULL, rel TEXT NOT NULL, dst TEXT NOT NULL, note TEXT DEFAULT '', created TEXT NOT NULL,
  PRIMARY KEY(src, rel, dst));
CREATE TABLE IF NOT EXISTS events(ts TEXT NOT NULL, action TEXT NOT NULL, item TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY, value TEXT, updated TEXT);
CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(id UNINDEXED, title, body, quote, tags);
"""
LOCAL_STATE = ("jsonl_hash",)  # state kept in the cache only, never written to ledger.jsonl; so are keys "local_*"


class LedgerFileError(Exception):
    pass


def file_hash(path):
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return ""


def connect(fresh=False):
    """The cache, brought up to date: from ledger.jsonl, or (shared) from Supabase; fresh = always pull first."""
    con = sqlite3.connect(DB, timeout=20)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    if SHARED:
        shared_sync(con, fresh)
        return con
    h = file_hash(JSONL)
    if h and get_state(con, "jsonl_hash") != h:  # the record changed outside this cache (a pull, a merge, a new clone)
        load_jsonl(con)
        set_state(con, "jsonl_hash", h)
        con.commit()
    return con


def newer(a, b, key):
    """True when record a should replace record b (later timestamp; a later line wins ties)."""
    return (a.get(key) or "") >= (b.get(key) or "")


def same_item(a, b):
    """Two versions of one item (an edit on each side of a merge), not two items that got the same ID."""
    return all(a.get(k) == b.get(k) for k in ("created", "kind", "title"))


def read_jsonl(path):
    """Parse the record. Tolerates git's union merge: identical lines collapse, the later edit of an item wins, and
    two different items that got the same ID on two machines are both kept (the later one renumbered)."""
    items, links, events, state, clashes, seen = {}, {}, [], {}, [], set()
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    for n, s in enumerate(lines, 1):
        if not s.strip():
            continue
        if s.startswith(("<<<<<<<", "=======", ">>>>>>>", "|||||||")):
            raise LedgerFileError(f"{path} line {n} has a git conflict marker; finish the merge first")
        try:
            rec = json.loads(s)
        except ValueError:
            raise LedgerFileError(f"{path} line {n} isn't valid JSON") from None
        if "item" in rec:
            it = rec["item"]
            old = items.get(it["id"])
            if old is None:
                items[it["id"]] = it
            elif same_item(old, it):
                if newer(it, old, "updated"):
                    items[it["id"]] = it
            elif it not in clashes:
                clashes.append(it)
        elif "link" in rec:
            ln = rec["link"]
            items_key = (ln["src"], ln["rel"], ln["dst"])
            if items_key not in links or newer(ln, links[items_key], "created"):
                links[items_key] = ln
        elif "event" in rec:
            k = json.dumps(rec["event"], sort_keys=True)
            if k not in seen:
                seen.add(k)
                events.append(rec["event"])
        elif "state" in rec:
            st = rec["state"]
            if st["key"] not in state or newer(st, state[st["key"]], "updated"):
                state[st["key"]] = st
    notes = []
    for it in clashes:  # same ID, different item: keep the earlier-created one, renumber the other
        keep = items[it["id"]]
        if it["created"] < keep["created"]:
            items[it["id"]], it = it, keep
        prefix = KINDS.get(it["kind"], ("N",))[0]
        nums = [int(i[len(prefix):]) for i in items if i.startswith(prefix) and i[len(prefix):].isdigit()]
        new_id = f"{prefix}{max(nums, default=0) + 1}"
        notes.append(f"{it['id']} was used for two items after a merge; \"{it['title']}\" is now {new_id} "
                     f"(links made on its machine still name {it['id']})")
        items[new_id] = dict(it, id=new_id)
    events.sort(key=lambda e: e.get("ts") or "")
    return items, list(links.values()), events, list(state.values()), notes


def load_jsonl(con):
    items, links, events, state, notes = read_jsonl(JSONL)
    with con:
        for t in ("items", "links", "events", "state", "fts"):
            con.execute(f"DELETE FROM {t}")
        for it in items.values():
            con.execute(f"INSERT INTO items({','.join(ITEM_COLS)}) VALUES({','.join('?' * len(ITEM_COLS))})",
                        [it.get(c, "" if c != "priority" else 2) for c in ITEM_COLS])
            reindex(con, it["id"])
        for ln in links:
            con.execute("INSERT OR REPLACE INTO links VALUES(?,?,?,?,?)",
                        (ln["src"], ln["rel"], ln["dst"], ln.get("note", ""), ln.get("created", "")))
        for ev in events:
            con.execute("INSERT INTO events VALUES(?,?,?,?)", (ev["ts"], ev["action"], ev.get("item"), ev.get("detail")))
        for st in state:
            con.execute("INSERT OR REPLACE INTO state VALUES(?,?,?)", (st["key"], st.get("value"), st.get("updated")))
        if notes:
            con.execute("INSERT OR REPLACE INTO state VALUES(?,?,?)", ("merge_notes", "\n".join(notes), now()))
            con.execute("INSERT INTO events VALUES(?,?,?,?)",
                        (now(), "merge-renumber", None, json.dumps(notes, ensure_ascii=False)))


def write_jsonl(con):
    order = "ORDER BY substr(id,1,1), CAST(substr(id,2) AS INTEGER), id"
    out = [json.dumps({"item": dict(r)}, ensure_ascii=False, sort_keys=True)
           for r in con.execute(f"SELECT * FROM items {order}")]
    out += [json.dumps({"link": dict(r)}, ensure_ascii=False, sort_keys=True)
            for r in con.execute("SELECT * FROM links ORDER BY src, rel, dst")]
    out += [json.dumps({"event": dict(r)}, ensure_ascii=False, sort_keys=True)
            for r in con.execute("SELECT * FROM events ORDER BY rowid")]
    out += [json.dumps({"state": dict(r)}, ensure_ascii=False, sort_keys=True)
            for r in con.execute(f"SELECT * FROM state WHERE key NOT IN ({','.join('?' * len(LOCAL_STATE))}) "
                                 "AND key NOT LIKE 'local!_%' ESCAPE '!' ORDER BY key", LOCAL_STATE)]
    tmp = JSONL + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write("".join(s + "\n" for s in out))
    os.replace(tmp, JSONL)
    set_state(con, "jsonl_hash", file_hash(JSONL))
    con.commit()


# ---------------------------------------------------------------- storage, shared: Supabase is the record, ledger.db a cache
#
# One record for all of the owner's sessions, local and cloud (supabase/schema.sql sets up the server). Each command
# pulls the record into the cache (writes always; reads unless the last pull is under PULL_FRESH seconds old), works
# on the cache as before, then pushes only what it changed: new items, the fields it edited, new links, events and
# state. If Supabase can't be reached, the change waits in outbox.jsonl and is sent first next time.
#
# Credentials: LEDGER_SUPABASE_URL, LEDGER_SUPABASE_KEY (the project's publishable key, which opens nothing by itself)
# and LEDGER_TOKEN, from the environment or from credentials.json beside config.json. With no token, the server reads
# an x-ledger-token header, which a cloud environment's network secret can add without the session seeing it.

PULL_FRESH = 20  # seconds; hook-start a and b, run back to back, share one pull
TIMEOUT = 15  # seconds per request; hooks use HOOK_TIMEOUT
HOOK_TIMEOUT = 6
SNAP = None  # the cache as last pulled or pushed: what a command's changes are measured against
IN_HOOK = False  # running as a hook: stdout is the hook's JSON
NO_SYNC = False  # set when another session on this machine holds the cache lock: read the cache, don't pull or push


class CacheLock:
    """One command at a time per cache, from its pull to its push. Without it, a session on the same machine could
    refresh the cache between another session saving a new item and sending it, and the item would never be sent.
    The operating system drops the lock if the process dies."""

    def __init__(self, path):
        self.path, self.f = path, None

    def acquire(self, timeout):
        self.f = open(self.path, "a+b")
        deadline = time.time() + timeout
        while True:
            try:
                if os.name == "nt":
                    import msvcrt
                    self.f.seek(0)
                    msvcrt.locking(self.f.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return True
            except OSError:
                if time.time() >= deadline:
                    self.f.close()
                    self.f = None
                    return False
                time.sleep(0.05)

    def release(self):
        if self.f:
            try:
                if os.name == "nt":
                    import msvcrt
                    self.f.seek(0)
                    msvcrt.locking(self.f.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
            self.f.close()
            self.f = None


class SharedError(Exception):
    pass


def creds():
    """(url, key, token, where from), environment first, then credentials.json."""
    try:
        with open(os.path.join(LEDGER_DIR, "credentials.json"), encoding="utf-8") as f:
            saved = json.load(f)
    except (OSError, ValueError):
        saved = {}
    out, where = [], []
    for env, k in (("LEDGER_SUPABASE_URL", "url"), ("LEDGER_SUPABASE_KEY", "key"), ("LEDGER_TOKEN", "token")):
        v = os.environ.get(env) or saved.get(k) or ""
        out.append(v)
        where.append(f"{k}: " + ("environment" if os.environ.get(env) else "credentials.json" if v else "not set"))
    return (*out, ", ".join(where))


def http_rpc(fn, args, timeout):
    """Call one of the ledger's two database functions over HTTPS."""
    url, key, token, _ = creds()
    if not url or not key:
        raise SharedError("no Supabase URL or key (set LEDGER_SUPABASE_URL and LEDGER_SUPABASE_KEY, or run "
                          "shared-setup --url URL --key KEY)")
    if token:
        args = dict(args, p_token=token)
    headers = {"apikey": key, "Content-Type": "application/json"}
    if not key.startswith("sb_"):  # an older anon key is a JWT and goes in Authorization too
        headers["Authorization"] = "Bearer " + key
    req = urllib.request.Request(url.rstrip("/") + "/rest/v1/rpc/" + fn, method="POST", headers=headers,
                                 data=json.dumps(args, ensure_ascii=False).encode("utf-8"))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8") or "null")
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode("utf-8")).get("message") or e.reason
        except (ValueError, OSError, AttributeError):
            msg = e.reason
        raise SharedError(f"the shared ledger refused the request ({e.code}: {msg})") from None
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise SharedError(f"can't reach the shared ledger ({getattr(e, 'reason', e)})") from None


RPC = http_rpc  # the tests swap in a fake server


def is_local_key(k):
    return k in LOCAL_STATE or k.startswith("local_")


def snapshot(con):
    return {"items": {r["id"]: dict(r) for r in con.execute("SELECT * FROM items")},
            "links": {(r["src"], r["rel"], r["dst"]): dict(r) for r in con.execute("SELECT * FROM links")},
            "state": {r["key"]: r["value"] for r in con.execute("SELECT * FROM state") if not is_local_key(r["key"])},
            "ev": con.execute("SELECT COALESCE(MAX(rowid), 0) FROM events").fetchone()[0]}


def load_pulled(con, data):
    with con:
        for t in ("items", "links", "events", "fts"):  # events were sent when they were made; the server keeps them
            con.execute(f"DELETE FROM {t}")
        con.execute("DELETE FROM state WHERE key NOT LIKE 'local!_%' ESCAPE '!'")
        for it in data.get("items") or []:
            con.execute(f"INSERT INTO items({','.join(ITEM_COLS)}) VALUES({','.join('?' * len(ITEM_COLS))})",
                        [it.get(c) if it.get(c) is not None else ("" if c != "priority" else 2) for c in ITEM_COLS])
            reindex(con, it["id"])
        for ln in data.get("links") or []:
            con.execute("INSERT OR REPLACE INTO links VALUES(?,?,?,?,?)",
                        (ln["src"], ln["rel"], ln["dst"], ln.get("note") or "", ln.get("created") or ""))
        for st in data.get("state") or []:
            con.execute("INSERT OR REPLACE INTO state VALUES(?,?,?)", (st["key"], st.get("value"), st.get("updated")))


def pull(con):
    load_pulled(con, RPC("ledger_pull", {}, TIMEOUT))
    set_state(con, "local_pulled_ts", str(time.time()))
    set_state(con, "local_pulled_at", now())
    set_state(con, "local_problem", "")
    con.commit()


def shared_sync(con, fresh=False):
    global SNAP
    if NO_SYNC:
        SNAP = snapshot(con)
        return
    try:
        if flush_outbox() and (fresh or time.time() - float(get_state(con, "local_pulled_ts") or 0) > PULL_FRESH):
            pull(con)
    except SharedError as e:
        set_state(con, "local_problem", str(e))
        con.commit()
    SNAP = snapshot(con)


def changes(con):
    """What this command changed in the cache since SNAP, as one batch for ledger_push (None = nothing)."""
    items = []
    for r in con.execute("SELECT * FROM items ORDER BY rowid"):
        d, old = dict(r), SNAP["items"].get(r["id"])
        if old is None:
            items.append(dict(d, _new=True))
        else:
            diff = {k: v for k, v in d.items() if old.get(k) != v}
            if diff:
                items.append(dict(diff, id=d["id"], updated=d["updated"]))
    links = [dict(r) for r in con.execute("SELECT * FROM links")
             if SNAP["links"].get((r["src"], r["rel"], r["dst"])) != dict(r)]
    events = [dict(r, project=r["project"] or PROJECT) for r in con.execute(
        "SELECT e.*, i.project FROM events e LEFT JOIN items i ON i.id = e.item WHERE e.rowid > ? ORDER BY e.rowid",
        (SNAP["ev"],))]  # each event is filed under its item's project
    state = [dict(r) for r in con.execute("SELECT * FROM state")
             if not is_local_key(r["key"]) and SNAP["state"].get(r["key"], object()) != r["value"]]
    if not (items or links or events or state):
        return None
    return {"project": PROJECT, "items": items, "links": links, "events": events, "state": state}


def rename_in(batch, renamed):
    """Apply the server's renames ({old: new}) to a batch that was waiting in the outbox."""
    r = lambda x: renamed.get(x, x)  # noqa: E731
    for it in batch.get("items", []):
        it["id"] = r(it["id"])
    for ln in batch.get("links", []):
        ln["src"], ln["dst"] = r(ln["src"]), r(ln["dst"])
    for ev in batch.get("events", []):
        ev["item"] = r(ev.get("item"))
    for st in batch.get("state", []):
        st["value"] = r(st.get("value"))
    return batch


def check_receipt(batch, res):
    """The server lists the IDs it stored for new items; every new item sent must be among them."""
    sent = sum(1 for it in batch.get("items", []) if it.get("_new"))
    if "inserted" in res and len(res["inserted"]) != sent:
        raise SharedError(f"the shared ledger stored {len(res['inserted'])} of the {sent} new items sent")


def say_renamed(renamed):
    """After the "added X" line, so it's the last word: a hook's stdout is JSON, so hooks get it on stderr."""
    for old, new in (renamed or {}).items():
        print(f"ledger: CORRECTION: the new item is {new}, not {old}. Another session took {old} first; {old} is "
              f"their item. Use {new} from now on.", file=sys.stderr if IN_HOOK else sys.stdout)


def flush_outbox():
    """Send changes saved while the shared ledger was out of reach, oldest first. True when none are left."""
    if not os.path.exists(OUTBOX):
        return True
    with open(OUTBOX, encoding="utf-8") as f:
        waiting = [json.loads(s) for s in f.read().splitlines() if s.strip()]
    renamed = {}
    for i, batch in enumerate(waiting):
        batch = rename_in(batch, renamed)
        try:
            res = RPC("ledger_push", {"p_batch": batch}, TIMEOUT) or {}
        except SharedError as e:
            with open(OUTBOX, "w", encoding="utf-8", newline="\n") as f:
                f.write("".join(json.dumps(b, ensure_ascii=False) + "\n" for b in waiting[i:]))
            raise SharedError(f"{e}; {len(waiting) - i} change(s) wait in {OUTBOX}") from None
        check_receipt(batch, res)
        renamed.update(res.get("renamed") or {})
        waiting[i] = batch
    os.remove(OUTBOX)
    say_renamed(renamed)
    return True


def shared_push(con):
    global SNAP
    if NO_SYNC:
        return
    if os.environ.get("LEDGER_TEST_PAUSE"):  # tests only: widen the gap between saving a change and sending it
        time.sleep(float(os.environ["LEDGER_TEST_PAUSE"]))
    batch = changes(con)
    if not batch:
        return
    try:
        res = RPC("ledger_push", {"p_batch": batch}, TIMEOUT) or {}
    except SharedError as e:
        with open(OUTBOX, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(batch, ensure_ascii=False) + "\n")
        set_state(con, "local_problem", f"{e}; changes wait in {OUTBOX}")
        con.commit()
        print(f"ledger: {e}. The change is saved on this machine ({OUTBOX}) and will be sent next time.",
              file=sys.stderr)
        SNAP = snapshot(con)
        return
    try:
        check_receipt(batch, res)
    except SharedError as e:
        set_state(con, "local_problem", str(e))
        con.commit()
        print(f"ledger: WARNING: {e}. Run `list --all` and re-add anything missing.", file=sys.stderr)
    if res.get("renamed"):
        say_renamed(res["renamed"])
        try:
            pull(con)
        except SharedError:
            pass
    SNAP = snapshot(con)


# ---------------------------------------------------------------- small helpers

def family_for(project):
    """One project plus the workspace-wide items; None = the whole ledger."""
    if not project:
        return None
    return (project, "all")


def pf(projects):
    """SQL filter for a project family (None = everything)."""
    if not projects:
        return ""
    return " AND project IN (" + ",".join("'" + x.replace("'", "") + "'" for x in projects) + ")"


def now():
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M")


def reindex(con, iid):
    con.execute("DELETE FROM fts WHERE id=?", (iid,))
    r = con.execute("SELECT id,title,body,quote,tags FROM items WHERE id=?", (iid,)).fetchone()
    if r:
        con.execute("INSERT INTO fts(id,title,body,quote,tags) VALUES(?,?,?,?,?)", tuple(r))


def log(con, action, item, detail):
    con.execute("INSERT INTO events VALUES(?,?,?,?)", (now(), action, item, json.dumps(detail, ensure_ascii=False)))


def next_id(con, kind):
    p = KINDS[kind][0]
    n = 0
    for (i,) in con.execute("SELECT id FROM items WHERE id LIKE ?", (p + "%",)):
        if i[len(p):].isdigit():
            n = max(n, int(i[len(p):]))
    return f"{p}{n + 1}"


def ids(s):
    return [x.strip() for x in (s or "").split(",") if x.strip()]


def get(con, iid):
    r = con.execute("SELECT * FROM items WHERE id=?", (iid,)).fetchone()
    if not r:
        sys.exit(f"no item {iid}")
    return r


def add_link(con, src, rel, dst, note=""):
    if rel not in RELS:
        sys.exit(f"unknown relation {rel}; use one of {RELS}")
    get(con, src), get(con, dst)
    con.execute("INSERT OR REPLACE INTO links VALUES(?,?,?,?,?)", (src, rel, dst, note, now()))
    log(con, "link", src, {"rel": rel, "dst": dst, "note": note})


def parse_opts(args):
    pos, opts, i = [], {}, 0
    while i < len(args):
        a = args[i]
        if a.startswith("--"):
            k = a[2:]
            if i + 1 < len(args) and not args[i + 1].startswith("--"):
                opts[k] = args[i + 1]
                i += 2
            else:
                opts[k] = True
                i += 1
        else:
            pos.append(a)
            i += 1
    return pos, opts


def norm_basis(b):
    """Any '<name>-words' style basis (owner-words, or an older ledger's sam-words) becomes owner-words."""
    return re.sub(r"^[a-z0-9_.]+-(words|overrode|picked-rec|approved)$", r"owner-\1", (b or "").strip().lower())


def norm_person(v, name=None):
    """'owner', or the owner's name or first name, becomes 'owner'; anything else (e.g. 'claude') stays."""
    name = (name or OWNER).strip().lower()
    v = (v or "").strip()
    return "owner" if v.lower() in {"owner", name, (name.split() or [""])[0]} else v


STOP = set("""the and for that this with from into than then them they their there what when where which while who
whom will would could should can not but are was were has have had its it's our out all any each every more most some
such only own same very just also about above after again against before being below between both down during few
further here how off once other over under until why you your yours his her she him himself claude make made
using use used get got like one two new now way want please""".split())


def stopwords():
    return STOP | set(OWNER.lower().split())


def fts_query(text):
    stop = stopwords()
    words = ["".join(ch for ch in w if ch.isalnum() or ch == "-") for w in text.lower().split()]
    words = [w.strip("-") for w in words if len(w.strip("-")) > 2 and w.strip("-") not in stop]
    return " OR ".join(f'"{w}"' for w in words)


def related(con, text, exclude=(), live_only=True, limit=12):
    query = fts_query(text)
    if not query:
        return []
    rows = con.execute(
        "SELECT i.* FROM fts JOIN items i ON i.id=fts.id WHERE fts MATCH ? ORDER BY bm25(fts) LIMIT 60", (query,)
    ).fetchall()
    out = [r for r in rows if r["id"] not in exclude and (not live_only or r["status"] in LIVE)]
    return out[:limit]


def line(r, quote_len=160):
    basis = f" [{basis_label(r['basis'])}]" if r["basis"] else ""
    owner = f" (owner: {OWNER if r['owner'] == 'owner' else r['owner']})" if r["owner"] else ""
    s = f"- **{r['id']}** {r['title']} — {r['status']}{owner}{basis}"
    if r["quote"]:
        qt = r["quote"].replace("\n", " ")
        s += f'\n  {OWNER}: "{qt[:quote_len]}{"…" if len(qt) > quote_len else ""}"'
    return s


def days_since(ts):
    try:
        return (dt.datetime.now() - dt.datetime.strptime(ts[:16], "%Y-%m-%d %H:%M")).days
    except ValueError:
        return 0


def get_state(con, key, default=""):
    r = con.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
    return r["value"] if r else default


def set_state(con, key, value):
    con.execute("INSERT OR REPLACE INTO state VALUES(?,?,?)", (key, value, now()))


def fk(key, project=None):
    """The state key for a project's focus: the shared ledger keeps one focus per project ("all" = every project
    without its own)."""
    return f"{key}@{project or PROJECT}" if SHARED else key


def current_focus(con):
    """(item ID or "", the project whose focus it is): this project's own focus, else the one set on "all"."""
    f = get_state(con, fk("focus"))
    if SHARED and (not f or f == "none") and PROJECT != "all":
        g = get_state(con, fk("focus", "all"))
        if g and g != "none":
            return g, "all"
    return ("" if f == "none" else f or ""), PROJECT


# ---------------------------------------------------------------- audit and brief

def audit(con, projects=None):
    warn = []
    F = pf(projects)
    live = lambda k: con.execute(  # noqa: E731
        f"SELECT * FROM items WHERE kind=? AND status IN ({','.join('?' * len(LIVE))}){F} ORDER BY priority, id",
        (k, *LIVE)).fetchall()
    servers = lambda iid: con.execute(  # noqa: E731
        f"SELECT i.* FROM links l JOIN items i ON i.id=l.src WHERE l.rel='serves' AND l.dst=? "
        f"AND i.kind='task' AND i.status IN ({','.join('?' * len(LIVE))})", (iid, *LIVE)).fetchall()
    for r in live("conflict"):
        warn.append(f"OPEN CONFLICT {r['id']}: {r['title']}")
    for r in con.execute(f"SELECT * FROM items WHERE owner='owner' AND status IN ({','.join('?' * len(LIVE))}){F} "
                         "ORDER BY created", LIVE):
        warn.append(f"WAITING ON {OWNER} {days_since(r['created'])} d: {r['id']} {r['title']}")
    for k, label in (("ask", f"{OWNER}'s ask"), ("promise", "my promise")):
        for r in live(k):  # "open" = a deliverable; "active" = a standing constraint that needs no task
            if r["status"] == "open" and not servers(r["id"]):
                warn.append(f"NO TASK SERVES {label} {r['id']}: {r['title']}")
    for r in con.execute(f"SELECT * FROM items WHERE kind='task' AND status IN ({','.join('?' * len(LIVE))}){F}",
                         LIVE):
        if not con.execute("SELECT 1 FROM links WHERE src=? AND rel='serves'", (r["id"],)).fetchone():
            warn.append(f"TASK SERVES NOTHING {OWNER} ASKED: {r['id']} {r['title']}")
    for r in con.execute("SELECT * FROM items WHERE kind='decision' AND status='active' AND basis='my-call'" + F):
        warn.append(f"MY OWN CALL, NOT CONFIRMED: {r['id']} {r['title']}")
    for r in con.execute("SELECT * FROM items WHERE status='blocked'" + F):
        if not con.execute("SELECT 1 FROM links WHERE rel='blocks' AND dst=?", (r["id"],)).fetchone():
            warn.append(f"BLOCKED WITH NO BLOCKER LINKED: {r['id']} {r['title']}")
    for r in con.execute("SELECT * FROM items WHERE project='unsorted'"):
        warn.append(f"NO PROJECT SET: {r['id']} {r['title']} (ledger.py set {r['id']} project=...)")
    mn = con.execute("SELECT value, updated FROM state WHERE key='merge_notes'").fetchone()
    if mn and mn["value"] and days_since(mn["updated"] or "") <= 3:
        warn.extend(f"MERGE: {x}" for x in mn["value"].splitlines())
    return warn


NUM = "CAST(substr(id,2) AS INTEGER)"


def make_brief(con, part=None, projects=None):
    """part None = everything (BRIEF.md, handoff); 'a' = state; 'b' = standing items. Each part fits one hook."""
    if SHARED:
        where = (f"the shared ledger (Supabase), one record for all of {OWNER}'s sessions, local and cloud. This "
                 f"session's project is `{PROJECT}`; items marked `all` apply to every project. How to use it: "
                 f"`{slash(os.path.join(HERE, 'LEDGER.md'))}` (read it once). {OWNER}'s view: `{HTML}`")
        problem = get_state(con, "local_problem")
        if problem:
            where += (f".\n\n**SHARED LEDGER PROBLEM:** {problem}. This is the copy from "
                      f"{get_state(con, 'local_pulled_at') or 'the last pull'}; new entries are kept on this machine "
                      f"and sent when it's back. Tell {OWNER} if it persists")
    else:
        where = f"`{JSONL}` ({OWNER}'s view: `{HTML}`)"
    head = [f"# Ledger brief{' (' + part + ' of a/b)' if part else ''}, generated {now()}",
            "",
            f"Source of truth for project state: {where}. If a summary, "
            f"plan, handoff or memory note disagrees with the ledger, the ledger wins; if {OWNER}'s own words disagree "
            "with each other, ask. **Required:** before offering options, planning or starting a stage, or writing "
            f"a handoff, run `{tool_cmd()} check <topic>`. Record each new instruction, decision or answer from "
            f"{OWNER} verbatim with `add` (or `override ID` when it changes a standing item); close items as they "
            f"finish. Tags: [{OWNER}] their words, [MINE, unconfirmed] my own call. `show ID` gives the full quote "
            "and source.",
            ""]
    out = list(head)
    seen = set()
    focus_id, focus_of = current_focus(con)

    def brief_line(r, quote=0, age=False):
        b = basis_label(r["basis"], short=True)
        tag = "" if r["project"] in (DEFAULT_PROJECT, "all") else f"[{r['project']}] "
        s = f"- {r['id']} {tag}{r['title']}"
        extra = [x for x in (r["status"] if r["status"] not in ("active", "open", "waiting") else "",
                             b, f"{days_since(r['created'])} d" if age else "") if x]
        if extra:
            s += f" [{', '.join(extra)}]"
        if r["id"] == focus_id and part == "b":
            s += " (the current focus: its full text is in part a)"
        elif quote and r["quote"]:
            qt = r["quote"].replace("\n", " ")
            s += f'\n  "{qt[:quote]}{"…" if len(qt) > quote else ""}"'
        return s

    def section(title, sql, quote=0, age=False):
        if " ORDER BY " in sql:
            a, b = sql.split(" ORDER BY ", 1)
            sql = a + pf(projects) + " ORDER BY " + b
        else:
            sql += pf(projects)
        rows = [r for r in con.execute(sql).fetchall() if r["id"] not in seen]
        if rows:
            out.append(f"## {title}")
            for r in rows:
                seen.add(r["id"])
                out.append(brief_line(r, quote, age))
            out.append("")

    live = "('open','active','in-progress','waiting','blocked','proposed')"
    order = f" ORDER BY priority, {NUM}"
    if part in (None, "a"):
        f = focus_id
        out.append("## Current focus")
        if f:
            r = con.execute("SELECT * FROM items WHERE id=?", (f,)).fetchone()
            fq = get_state(con, fk("focus_quote", focus_of))
            every = ", for every project" if SHARED and focus_of == "all" else ""
            out.append(f"- {f} {r['title'] if r else '(missing item)'} "
                       f"[set {get_state(con, fk('focus_set', focus_of))}{every}]"
                       + (f'\n  {OWNER}: "{fq[:300]}"' if fq else ""))
            if r and r["body"]:  # printed whole: it's what every step is checked against
                out.extend("  " + x for x in r["body"].splitlines())
        else:
            out.append(f"- None chosen: {OWNER} hasn't picked the next step. Don't start a new work stream on your "
                       "own; answer what they ask, and put the waiting questions to them.")
        out.append(f"- Side requests are fine ({OWNER} is in charge), but say they're side requests, record them as "
                   "their own items, and come back to the focus. Ideas of mine become `proposed` tasks, not work.")
        out.append("")
        if SHARED:  # where earlier sessions left this project's reports: a cloud session can't find them otherwise
            section("Read first: where earlier work is", "SELECT * FROM items WHERE kind='ref' AND status IN "
                                                         "('open','active')" + order)
        section("Open conflicts", "SELECT * FROM items WHERE kind='conflict' AND status IN ('open','active')" + order)
        section(f"Waiting on {OWNER} (age)", f"SELECT * FROM items WHERE owner='owner' AND status IN {live} "
                                             "ORDER BY priority, created", age=True)
        section("Promises not yet kept",
                "SELECT * FROM items WHERE kind='promise' AND status IN ('open','active')" + order)
        section("Tasks in play", f"SELECT * FROM items WHERE kind='task' AND status IN {live}" + order)
        w = [x for x in audit(con, projects) if not x.startswith(("OPEN CONFLICT", "WAITING ON "))]
        if w:
            out.append("## Audit warnings")
            out.extend(f"- {x}" for x in w)
            out.append("")
    if part in (None, "b"):
        if part == "b":
            out = [f"# Ledger brief (b of a/b): {OWNER}'s standing goals, asks, decisions and rules, generated {now()}",
                   "",
                   f"These are in force until {OWNER} changes them. If their message contradicts one, follow the "
                   "override protocol (LEDGER.md): name the item, quote their earlier words with the date, and "
                   "confirm.", ""]
        section("Goals", "SELECT * FROM items WHERE kind='goal' AND status='active'" + order, quote=600)
        section(f"{OWNER}'s asks in force", f"SELECT * FROM items WHERE kind='ask' AND status IN {live}" + order)
        section("Decisions in force", "SELECT * FROM items WHERE kind='decision' AND status='active'" + order)
        section("Rules", "SELECT * FROM items WHERE kind='rule' AND status='active'" + order)
    if part in (None, "a") and projects:
        others = con.execute(f"SELECT project, COUNT(*) n FROM items WHERE status IN {live} AND project NOT IN ("
                             + ",".join("'" + x + "'" for x in projects) + ") GROUP BY project").fetchall()
        if others:
            out.append(f"Other projects in the ledger (not this session's work unless {OWNER} brings them up): "
                       + ", ".join(f"{x['project']} ({x['n']} live)" for x in others) + ".")
    text = "\n".join(out)
    cap = HOOK_MAX if part else BRIEF_MAX
    if len(text) > cap:  # shed detail rather than overflow the hook cap
        text = text[:cap - 140] + f"\n\n…(truncated at {cap} characters: run `ledger.py brief`, or open ledger.html)\n"
    return text


# ---------------------------------------------------------------- exports

def export(con):
    if SHARED:
        shared_push(con)
    else:
        write_jsonl(con)
    with open(BRIEF, "w", encoding="utf-8") as f:
        f.write(make_brief(con))
    items = [dict(r) for r in con.execute("SELECT * FROM items ORDER BY id")]
    links = [dict(r) for r in con.execute("SELECT * FROM links ORDER BY src, rel, dst")]
    write_html(con, items, links)


def write_html(con, items, links):
    by = {i["id"]: i for i in items}
    out_l, in_l = {}, {}
    for ln in links:
        out_l.setdefault(ln["src"], []).append(ln)
        in_l.setdefault(ln["dst"], []).append(ln)
    e = html.escape
    warn = audit(con)

    def card(i, anchor=True):
        lk = []
        for ln in out_l.get(i["id"], []):
            t = by.get(ln["dst"], {}).get("title", "")
            lk.append(f"{e(ln['rel'])} <a href='#{e(ln['dst'])}'>{e(ln['dst'])}</a> {e(t[:60])}")
        for ln in in_l.get(i["id"], []):
            t = by.get(ln["src"], {}).get("title", "")
            lk.append(f"<a href='#{e(ln['src'])}'>{e(ln['src'])}</a> {e(t[:60])} → {e(ln['rel'])} this")
        qt = f"<blockquote>“{e(i['quote'])}”</blockquote>" if i["quote"] else ""
        b = f"<p>{e(i['body'])}</p>" if i["body"] else ""
        src = f"<div class='src'>{e(i['source'])}</div>" if i["source"] else ""
        basis = f"<span class='b'>{e(basis_label(i['basis']))}</span>" if i["basis"] else ""
        who = OWNER if i["owner"] == "owner" else i["owner"]
        own = f"<span class='o'>owner: {e(who)}</span>" if i["owner"] else ""
        lks = ("<ul class='lk'>" + "".join(f"<li>{x}</li>" for x in lk) + "</ul>") if lk else ""
        aid = f" id='{e(i['id'])}'" if anchor else ""
        text = " ".join((i["id"], i["title"], i["body"], i["quote"], i["tags"], i["project"])).lower()
        return (f"<div class='card s-{e(i['status'])}'{aid} data-t='{e(text)}'>"
                f"<div class='h'><b>{e(i['id'])}</b> {e(i['title'])}</div>"
                f"<div class='m'><span class='st'>{e(i['status'])}</span>{own}{basis}"
                f"<span class='p'>{e(i['project'])}</span><span class='tg'>{e(i['tags'])}</span></div>"
                f"{qt}{b}{src}{lks}</div>")

    order = ["conflict", "question", "goal", "ask", "rule", "decision", "promise", "task", "defect", "lesson",
             "fact", "ref", "note"]
    waiting = sorted((i for i in items if i["owner"] == "owner" and i["status"] in LIVE),
                     key=lambda i: (i["priority"], i["created"]))
    secs = []
    fid = current_focus(con)[0]
    if fid and fid in by:
        secs.append("<h2>Current focus</h2>" + card(by[fid], anchor=False))
    if waiting:
        secs.append(f"<h2>Waiting on {e(OWNER)}</h2>" + "".join(card(i, anchor=False) for i in waiting))
    if warn:
        secs.append("<h2>Drift audit</h2><ul class='warn'>" + "".join(f"<li>{e(w)}</li>" for w in warn) + "</ul>")
    for k in order:
        rows = [i for i in items if i["kind"] == k]
        if not rows:
            continue
        live = [i for i in rows if i["status"] in LIVE]
        old = [i for i in rows if i["status"] not in LIVE]
        s = f"<h2>{e(o(PLURAL[k]))} <small>({len(live)} live, {len(old)} closed)</small></h2>"
        s += "".join(card(i) for i in live)
        if old:
            parked = sum(i["status"] == "parked" for i in old)
            label = f"closed, parked or superseded ({len(old)}; {parked} parked)" if parked else \
                f"closed / superseded ({len(old)})"
            s += f"<details><summary>{label}</summary>{''.join(card(i) for i in old)}</details>"
        secs.append(s)
    name = f"{OWNER}'s shared" if SHARED else (os.path.basename(WORKSPACE) or "Project")
    src = f"the shared ledger (last pulled {get_state(con, 'local_pulled_at')})" if SHARED else JSONL
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(name)} ledger</title><style>
:root{{--bg:#fafaf8;--fg:#1d1d1b;--mut:#6b6b66;--card:#fff;--line:#e2e1dc;--acc:#2f5d8a;--warn:#9a3b1c}}
@media (prefers-color-scheme:dark){{:root{{--bg:#161615;--fg:#ecebe6;--mut:#a3a29c;--card:#1f1f1d;--line:#34332f;--acc:#8fb6dd;--warn:#f0a07f}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,Segoe UI,sans-serif;margin:0 auto;max-width:980px;padding:16px}}
h1{{font-size:22px;margin:4px 0}} h2{{font-size:17px;margin:26px 0 8px;border-bottom:1px solid var(--line);padding-bottom:4px}}
small{{color:var(--mut);font-weight:400}} input{{width:100%;box-sizing:border-box;padding:9px 11px;font:inherit;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--fg)}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:9px 12px;margin:7px 0}}
.h{{font-weight:600}} .m{{font-size:12.5px;color:var(--mut);display:flex;flex-wrap:wrap;gap:10px;margin-top:2px}}
.st{{color:var(--acc);font-weight:600}} blockquote{{margin:6px 0;padding-left:10px;border-left:3px solid var(--acc)}}
.src{{font-size:12px;color:var(--mut)}} .lk{{font-size:12.5px;margin:4px 0 0;padding-left:18px}} a{{color:var(--acc)}}
.warn li{{color:var(--warn)}} .s-superseded,.s-rejected{{opacity:.6}} p{{margin:5px 0}}
</style></head><body><h1>{e(name)} ledger</h1><div class="src">Generated {e(now())} from {e(src)}.
Claude writes it; tell Claude in chat to change anything.</div>
<p><input id="f" placeholder="Filter: type a word, an ID (D12) or a tag"></p>{''.join(secs)}
<script>document.getElementById('f').addEventListener('input',function(){{var v=this.value.toLowerCase();
document.querySelectorAll('.card').forEach(function(c){{c.style.display=!v||c.dataset.t.indexOf(v)>=0?'':'none'}});
document.querySelectorAll('details').forEach(function(d){{if(v)d.open=true}})}});</script></body></html>"""
    with open(HTML, "w", encoding="utf-8") as f:
        f.write(page)


# ---------------------------------------------------------------- commands

def cmd_add(con, args):
    pos, op = parse_opts(args)
    if len(pos) < 2 or pos[0] not in KINDS:
        sys.exit(f"usage: add KIND 'title' [opts]; KIND in {list(KINDS)}")
    kind, title = pos[0], " ".join(pos[1:])
    iid = op.get("id") or next_id(con, kind)
    st = op.get("status", "active" if kind in ("goal", "rule", "decision", "fact", "lesson", "ref") else "open")
    if st not in STATUSES:
        sys.exit(f"unknown status {st}")
    t = now()
    con.execute(f"INSERT INTO items({','.join(ITEM_COLS)}) VALUES({','.join('?' * len(ITEM_COLS))})",
                (iid, op.get("project") or DEFAULT_PROJECT, kind, title, op.get("body", ""), op.get("quote", ""),
                 op.get("source", ""), norm_person(op.get("who", "owner" if op.get("quote") else "claude")),
                 norm_basis(op.get("basis", "")), st, norm_person(op.get("owner", "")), int(op.get("priority", 2)),
                 op.get("tags", ""), op.get("created", t), t))
    reindex(con, iid)
    log(con, "add", iid, {"kind": kind, "title": title})
    for rel in RELS:
        for d in ids(op.get(rel)):
            add_link(con, iid, rel, d)
            if rel == "supersedes":
                con.execute("UPDATE items SET status='superseded', updated=? WHERE id=?", (t, d))
    con.commit()
    print(f"added {iid}")
    rel = related(con, f"{title} {op.get('tags', '')}", exclude={iid})
    if rel and not op.get("quiet"):
        print("Related items in force: check each for a contradiction or supersession:")
        for r in rel:
            print("  " + line(r, 120).replace("\n", "\n  "))


def cmd_set(con, args):
    iid, pairs = args[0], args[1:]
    get(con, iid)
    for p in pairs:
        k, _, v = p.partition("=")
        if k not in FIELDS:
            sys.exit(f"unknown field {k}")
        if k == "status" and v not in STATUSES:
            sys.exit(f"unknown status {v}")
        if k in ("owner", "who"):
            v = norm_person(v)
        if k == "basis":
            v = norm_basis(v)
        con.execute(f"UPDATE items SET {k}=?, updated=? WHERE id=?", (v, now(), iid))
        log(con, "set", iid, {k: v})
    reindex(con, iid)
    con.commit()
    print(f"updated {iid}")


def cmd_show(con, iid):
    r = get(con, iid)
    print(line(r, 10000))
    for k in ("body", "source", "tags", "project", "who", "created", "updated"):
        if r[k]:
            print(f"  {k}: {OWNER if k == 'who' and r[k] == 'owner' else r[k]}")
    for lk in con.execute("SELECT * FROM links WHERE src=?", (iid,)):
        d = get(con, lk["dst"])
        print(f"  {lk['rel']} → {d['id']} {d['title']} ({d['status']}) {lk['note']}")
    for lk in con.execute("SELECT * FROM links WHERE dst=?", (iid,)):
        s = get(con, lk["src"])
        print(f"  ← {s['id']} {s['title']} ({s['status']}) {lk['rel']} this {lk['note']}")


def cmd_check(con, topic):
    text = " ".join(topic)
    tagged = con.execute(f"SELECT * FROM items WHERE status IN ({','.join('?' * len(LIVE))})", LIVE).fetchall()
    words = {w.lower() for w in topic}
    hits = {r["id"]: r for r in tagged if words & {t.strip().lower() for t in r["tags"].split(",")}}
    for r in related(con, text, limit=40):
        hits.setdefault(r["id"], r)
    always = con.execute("SELECT * FROM items WHERE kind IN ('goal','conflict') AND status IN ('active','open')")
    for r in always:
        hits.setdefault(r["id"], r)
    if FAMILY:
        hits = {k: r for k, r in hits.items() if r["project"] in FAMILY}
    order = ["goal", "conflict", "rule", "ask", "decision", "question", "promise", "task", "defect", "lesson", "fact",
             "ref", "note"]
    print(f"# check: {text}\n({OWNER}'s words outrank my plans. Resolve any conflict below before acting.)")
    for k in order:
        rows = sorted((r for r in hits.values() if r["kind"] == k), key=lambda r: (r["priority"], r["id"]))
        if rows:
            print(f"\n## {o(KINDS[k][1])}")
            for r in rows:
                print(line(r, 300))


def cmd_list(con, args):
    _, op = parse_opts(args)
    sql, a = "SELECT * FROM items WHERE 1=1", []
    for k in ("kind", "status", "owner", "project"):
        if op.get(k):
            sql += f" AND {k}=?"
            a.append(norm_person(op[k]) if k == "owner" else op[k])
    if op.get("tag"):
        sql += " AND (','||tags||',') LIKE ?"
        a.append(f"%,{op['tag']},%")
    if not op.get("all") and not op.get("status"):
        sql += f" AND status IN ({','.join('?' * len(LIVE))})"
        a.extend(LIVE)
    if FAMILY and not op.get("project") and not op.get("all-projects"):
        sql += pf(FAMILY)
    for r in con.execute(sql + " ORDER BY kind, priority, id", a):
        print(line(r, 120))


def cmd_handoff(con):
    print(f"## Handoff from the ledger ({now()})\n")
    print(make_brief(con, None, FAMILY).split("\n", 1)[1])
    print("## Recently changed (48 h)")
    for r in con.execute("SELECT * FROM items WHERE 1=1" + pf(FAMILY) + " ORDER BY updated DESC LIMIT 25"):
        if days_since(r["updated"]) <= 2:
            print(line(r, 100))


# ---------------------------------------------------------------- override detection, focus, hooks

TRIGGERS = [r"\bfrom now on\b", r"\bnew rule\b", r"\binstead\b", r"\bno longer\b", r"\banymore\b", r"\bno more\b",
            r"\bdon'?t (need|want|bother|care)\b", r"\bforget\b", r"\bscrap\b", r"\bnever ?mind\b", r"\bchange\b",
            r"\bswitch\b", r"\blet'?s not\b", r"\bskip\b", r"\bdrop\b", r"\bactually\b", r"\bstop\b", r"\balways\b",
            r"\bnever\b", r"\brather\b", r"\bgo back\b", r"\bundo\b", r"\bignore\b", r"\bdoesn'?t matter\b",
            r"\breplace\b", r"\boverride\b", r"\bjust (do|use|make|go|put|render)\b", r"\bwithout\b", r"\bremove\b",
            r"\bdelete\b", r"\bquick(ly)?\b", r"\bfaster\b", r"\bcheaper\b", r"\bin (full )?colou?r\b", r"\bmake it\b",
            r"\bshorter\b", r"\blonger\b", r"\bcut\b", r"\bfine to\b", r"\bgo ahead and\b", r"\bplease (use|do)\b"]


def toks(text):
    stop = stopwords()
    out = set()
    for w in re.split(r"[^a-z0-9]+", (text or "").lower()):
        if not w or w in stop or (len(w) < 3 and not (w.isdigit() and len(w) >= 2)):
            continue
        if len(w) > 4 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.add(w)
    return out


def standing(con, projects=None):
    return con.execute(
        "SELECT * FROM items WHERE ((kind IN ('rule','decision','goal') AND status='active') "
        "OR (kind='ask' AND status IN ('open','active','in-progress','waiting')) "
        "OR (kind='question' AND owner='owner' AND status IN ('open','waiting','proposed')))" + pf(projects)
    ).fetchall()


def match_prompt(con, prompt, projects=None):
    """Return (trigger_words, [(score, row, tag_hits)]) for standing items the owner's message touches."""
    low = (prompt or "").lower()
    trig = [m.group(0) for t in TRIGGERS for m in [re.search(t, low)] if m]
    p = toks(prompt)
    items = standing(con, projects)
    tagsets = {r["id"]: toks(r["tags"].replace(",", " ")) for r in items}
    df = {}
    for ts in tagsets.values():
        for t in ts:
            df[t] = df.get(t, 0) + 1
    n = max(len(items), 1)
    hits = []
    for r in items:
        th = p & tagsets[r["id"]]
        tag_score = sum(math.log(n / df[t]) for t in th)
        wh = (p & toks(r["title"] + " " + r["quote"])) - th
        if r["kind"] == "goal":
            fire = bool(trig) and tag_score >= 2.5
        elif r["kind"] == "question":
            fire = tag_score >= 4.0
        else:
            fire = tag_score >= 5.0 or (bool(trig) and tag_score >= 2.5) or (tag_score >= 3.0 and len(wh) >= 2)
        if fire:
            hits.append((tag_score + 0.5 * len(wh), r, sorted(th)))
    hits.sort(key=lambda h: -h[0])
    return trig, hits


def in_scope(hook_input):
    """True when the session works in this ledger's repository (the folder above .ledger) or a folder inside it."""
    if SHARED:
        return True
    cwd = os.path.normcase(os.path.abspath(hook_input.get("cwd") or os.getcwd()))
    ws = os.path.normcase(os.path.abspath(WORKSPACE))
    return cwd == ws or cwd.startswith(ws.rstrip(os.sep) + os.sep)


def read_hook_input():
    try:
        if sys.stdin is not None and not sys.stdin.isatty():
            data = sys.stdin.read()
            return json.loads(data) if data.strip() else {}
    except (ValueError, OSError):
        pass
    return {}


def emit(event, text):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text[:HOOK_MAX]}},
                     ensure_ascii=True))


def prompt_report(con, prompt, projects=None):
    if not prompt or prompt.lstrip().startswith(("<task-notification", "<cross-session-message", "<command-",
                                                 "<local-command")):
        return ""
    trig, hits = match_prompt(con, prompt, projects)
    over = [h for h in hits if h[1]["kind"] != "question"][:6]
    ques = [h for h in hits if h[1]["kind"] == "question"][:3]
    if not over and not ques:
        return ""
    out = [f"LEDGER CHECK (automatic, on {OWNER}'s message)."]
    if over:
        out.append(f"It touches standing items {OWNER} set earlier" +
                   (f" and uses change wording ({', '.join(trig[:4])})" if trig else "") + ":")
        for _, r, th in over:
            qt = (r["quote"] or "").replace("\n", " ")
            src = basis_label(r["basis"], short=True) or r["who"]
            out.append(f"- {r['id']} [{r['kind']}, {src}, {r['created'][:10]}] {r['title']}"
                       + (f' | their words: "{qt[:180]}{"…" if len(qt) > 180 else ""}"' if qt else ""))
        out.append("Override protocol (LEDGER.md): if the message changes or contradicts one of these, don't silently "
                   "comply and don't silently refuse. Before acting on it, name the item, quote their earlier words "
                   "with the date, and ask: change it for good, a one-time exception, or keep it? Only when the "
                   "message itself refers to the earlier rule (e.g. 'I know I said X, but...') may you confirm in one "
                   "line and go ahead; 'from now on' alone doesn't show they remember it. After their answer, record "
                   f"it: `{tool_cmd()} override <ID> \"<new version>\" --quote \"<their words>\"` (add --once for an "
                   "exception) and review the dependants it lists. If the message doesn't change them, carry on and "
                   "don't mention this check.")
    if ques:
        out.append(f"It may answer a question waiting on {OWNER}: " +
                   "; ".join(f"{r['id']} {r['title']}" for _, r, _ in ques) +
                   ". If it does, record the answer (`add decision ... --basis owner-words`, then "
                   "`set <Q> status=resolved`).")
    return "\n".join(out)


def cmd_override(con, args):
    pos, op = parse_opts(args)
    if len(pos) < 2 or not op.get("quote"):
        sys.exit('usage: override ID "new title" --quote "the owner\'s words" [--source S] [--once] [--tags T]')
    old, title = get(con, pos[0]), " ".join(pos[1:])
    t = now()
    cols = f"INSERT INTO items({','.join(ITEM_COLS)}) VALUES({','.join('?' * len(ITEM_COLS))})"
    if op.get("once"):
        iid = next_id(con, "note")
        con.execute(cols, (iid, old["project"], "note", f"One-time exception to {old['id']}: {title}", "",
                           op["quote"], op.get("source", ""), "owner", "owner-words", "done", "", old["priority"],
                           old["tags"], t, t))
        add_link(con, iid, "about", old["id"], "one-time exception; the original stays in force")
        log(con, "exception", old["id"], {"note": iid, "quote": op["quote"]})
        print(f"recorded one-time exception {iid}; {old['id']} stays in force")
    else:
        iid = next_id(con, old["kind"])
        tags = ",".join(x for x in (old["tags"], op.get("tags", "")) if x)
        con.execute(cols, (iid, old["project"], old["kind"], title, op.get("body", f"Replaces {old['id']}: {old['title']}"),
                           op["quote"], op.get("source", ""), "owner", norm_basis(op.get("basis", "owner-words")),
                           "active", "", old["priority"], tags, t, t))
        add_link(con, iid, "supersedes", old["id"], f"{OWNER}'s override")
        con.execute("UPDATE items SET status='superseded', updated=? WHERE id=?", (t, old["id"]))
        log(con, "override", old["id"], {"new": iid, "quote": op["quote"]})
        print(f"{iid} now supersedes {old['id']} ({old['title']})")
    reindex(con, iid)
    con.commit()
    deps = con.execute("SELECT l.rel AS rel, i.id AS id, i.title AS title, i.status AS status FROM links l "
                       "JOIN items i ON i.id=l.src WHERE l.dst=? AND i.id<>? "
                       "UNION SELECT l.rel, i.id, i.title, i.status FROM links l JOIN items i ON i.id=l.dst "
                       "WHERE l.src=?", (old["id"], iid, old["id"])).fetchall()
    if deps:
        print(f"Review these items linked to {old['id']}; close or update any the change makes stale:")
        for d in deps:
            print(f"  {d['id']} ({d['rel']}) {d['title']} [{d['status']}]")
    rel = related(con, f"{old['title']} {old['tags']}", exclude={iid, old["id"]}, limit=8)
    if rel:
        print("Also related (by words):")
        for r in rel:
            print(f"  {r['id']} {r['title']} [{r['status']}]")


def cmd_focus(con, args):
    pos, op = parse_opts(args)
    proj = op.get("project") if isinstance(op.get("project"), str) else None  # shared: "all" = every project
    if not pos:
        print(get_state(con, fk("focus", proj)) or "none")
        return
    if pos[0] != "none":
        get(con, pos[0])
    set_state(con, fk("focus", proj), pos[0])
    set_state(con, fk("focus_quote", proj), op.get("quote", ""))
    set_state(con, fk("focus_set", proj), now())
    log(con, "focus", pos[0], {"quote": op.get("quote", "")})
    con.commit()
    print(f"focus: {pos[0]}")


def cmd_precompact(con):
    import contextlib
    import io
    os.makedirs(HANDOFFS, exist_ok=True)
    path = os.path.join(HANDOFFS, dt.datetime.now().strftime("%Y-%m-%d_%H%M") + ".md")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cmd_handoff(con)
    with open(path, "w", encoding="utf-8") as f:
        f.write(buf.getvalue())
    log(con, "precompact", None, {"file": os.path.basename(path)})
    con.commit()
    export(con)


def cmd_import(con, args):
    pos, op = parse_opts(args)
    if not pos or not os.path.isfile(pos[0]):
        sys.exit("usage: import OLD.db [--project P] [--as NAME]")
    if con.execute("SELECT COUNT(*) FROM items").fetchone()[0]:
        sys.exit("this ledger already has items; import only goes into an empty ledger")
    proj, name = op.get("project"), op.get("as") or OWNER
    old = sqlite3.connect(pathlib.Path(pos[0]).resolve().as_uri() + "?mode=ro", uri=True)
    old.row_factory = sqlite3.Row
    rows = old.execute("SELECT * FROM items" + (" WHERE project IN (?, 'all')" if proj else ""),
                       (proj,) if proj else ()).fetchall()
    keep = set()
    for r in rows:
        d = {c: (r[c] if c in r.keys() else None) for c in ITEM_COLS}
        d["project"] = DEFAULT_PROJECT if (proj and d["project"] == proj) else (d["project"] or DEFAULT_PROJECT)
        d["basis"] = norm_basis(d["basis"])
        d["owner"] = norm_person(d["owner"], name)
        d["who"] = norm_person(d["who"], name)
        con.execute(f"INSERT INTO items({','.join(ITEM_COLS)}) VALUES({','.join('?' * len(ITEM_COLS))})",
                    [d[c] if d[c] is not None else ("" if c != "priority" else 2) for c in ITEM_COLS])
        reindex(con, d["id"])
        keep.add(d["id"])
    nl = ne = 0
    for r in old.execute("SELECT * FROM links"):
        if r["src"] in keep and r["dst"] in keep:
            con.execute("INSERT OR REPLACE INTO links VALUES(?,?,?,?,?)", tuple(r))
            nl += 1
    for r in old.execute("SELECT * FROM events ORDER BY rowid"):
        if r["item"] in keep or (r["item"] is None and not proj):
            con.execute("INSERT INTO events VALUES(?,?,?,?)", tuple(r))
            ne += 1
    for r in old.execute("SELECT * FROM state WHERE key IN ('focus','focus_quote','focus_set')"):
        focus = old.execute("SELECT value FROM state WHERE key='focus'").fetchone()
        if focus and focus[0] in keep:
            con.execute("INSERT OR REPLACE INTO state VALUES(?,?,?)", tuple(r))
    log(con, "import", None, {"from": os.path.basename(pos[0]), "project": proj or "", "items": len(keep)})
    con.commit()
    print(f"imported {len(keep)} items, {nl} links, {ne} events" + (f" (project {proj} plus 'all')" if proj else ""))


# ---------------------------------------------------------------- init: set up a repository

def git(args, cwd):
    try:
        r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=20)
        return r.returncode, r.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return 1, ""


def repo_root():
    """The repository this tool sits in as a submodule, else the git repository of the current folder, else it."""
    code, sup = git(["rev-parse", "--show-superproject-working-tree"], HERE)
    if code == 0 and sup:
        return os.path.abspath(sup)
    code, top = git(["rev-parse", "--show-toplevel"], os.getcwd())
    return os.path.abspath(top) if code == 0 and top else os.getcwd()


def is_ledger_hook(entry):
    return any("ledger.py" in h.get("command", "") and " hook-" in h.get("command", "")
               for h in entry.get("hooks", []))


def is_cloud_hook(entry):
    return any("CLAUDE_CODE_REMOTE" in h.get("command", "") for h in entry.get("hooks", []))


def cmd_init(args, dir_arg=None):
    _, op = parse_opts(args)
    if op.get("root"):
        root = os.path.abspath(op["root"])
    elif dir_arg:
        root = os.path.dirname(os.path.abspath(dir_arg))
    else:
        root = repo_root()
    d = os.path.join(root, DIRNAME)
    done = []
    if not os.path.isdir(d):
        os.makedirs(d)
        done.append(f"created {d}")
    use_dir(d)
    cfg = read_config()
    if op.get("owner") or not cfg.get("owner"):
        _, gname = git(["config", "user.name"], root)
        cfg["owner"] = op.get("owner") or cfg.get("owner") or (gname.split() or ["the owner"])[0]
        with open(CONFIG, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")
        use_dir(d)
        done.append(f"owner: {cfg['owner']} (change it with init --owner NAME)")
    gi = os.path.join(d, ".gitignore")
    if op.get("private") or not os.path.exists(gi):
        with open(gi, "w", encoding="utf-8", newline="\n") as f:
            f.write("*\n" if op.get("private") else "ledger.db\nledger.db-*\nledger.html\nBRIEF.md\nhandoffs/\n*.tmp\n")
        done.append("the ledger stays out of git (--private)" if op.get("private") else
                    "git will track ledger.jsonl and config.json; the cache and generated files are ignored")
    ga = os.path.join(d, ".gitattributes")
    if not os.path.exists(ga):  # union: both sides' lines survive a merge; eol=lf: the bytes stay the same everywhere
        with open(ga, "w", encoding="utf-8", newline="\n") as f:
            f.write("ledger.jsonl merge=union text eol=lf\n")
    if not os.path.exists(JSONL):
        open(JSONL, "w", encoding="utf-8").close()

    # Hooks: machine-specific (they name this Python), so they go in the uncommitted settings.local.json.
    sdir = os.path.join(root, ".claude")
    os.makedirs(sdir, exist_ok=True)
    sfile = os.path.join(sdir, "settings.local.json")
    try:
        with open(sfile, encoding="utf-8") as f:
            settings = json.load(f)
    except OSError:
        settings = {}
    except ValueError:
        sys.exit(f"{sfile} isn't valid JSON; fix it and run init again")
    base = tool_cmd()
    ours = {
        "SessionStart": {"matcher": "startup|resume|compact|clear", "hooks": [
            {"type": "command", "command": f"{base} hook-start a", "timeout": 30},
            {"type": "command", "command": f"{base} hook-start b", "timeout": 30}]},
        "UserPromptSubmit": {"hooks": [{"type": "command", "command": f"{base} hook-prompt", "timeout": 15}]},
        "PreCompact": {"matcher": "manual|auto", "hooks": [
            {"type": "command", "command": f"{base} hook-precompact", "timeout": 30}]},
    }
    hooks = settings.setdefault("hooks", {})
    for ev, entry in ours.items():
        hooks[ev] = [x for x in hooks.get(ev, []) if not is_ledger_hook(x)] + [entry]
    with open(sfile, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(settings, indent=2, ensure_ascii=False) + "\n")
    done.append(f"hooks for this machine in {sfile}")
    shared = os.path.join(sdir, "settings.json")
    try:
        with open(shared, encoding="utf-8") as f:
            if any(is_ledger_hook(x) and not is_cloud_hook(x) for v in json.load(f).get("hooks", {}).values()
                   for x in v):
                done.append(f"WARNING: {shared} has ledger hooks too; remove them there or they'll run twice")
    except (OSError, ValueError, AttributeError):
        pass
    if git(["rev-parse", "--is-inside-work-tree"], root)[0] == 0 and \
            git(["check-ignore", "-q", ".claude/settings.local.json"], root)[0] != 0:
        with open(os.path.join(root, ".gitignore"), "a", encoding="utf-8", newline="\n") as f:
            f.write("\n.claude/settings.local.json\n")
        done.append("added .claude/settings.local.json to .gitignore")

    # Instructions: CLAUDE.md imports LEDGER.md from the tool.
    inside = os.path.normcase(HERE).startswith(os.path.normcase(root.rstrip(os.sep) + os.sep))
    rel = slash(os.path.relpath(HERE, root)) if inside else slash(HERE)
    imp = f"@{rel}/LEDGER.md"
    cmd = os.path.join(root, "CLAUDE.md")
    text = open(cmd, encoding="utf-8").read() if os.path.exists(cmd) else ""
    if imp not in text:
        with open(cmd, "a", encoding="utf-8", newline="\n") as f:
            f.write(("\n" if text and not text.endswith("\n") else "") + ("\n" if text else "") +
                    f"## Project ledger\n\n{imp}\n\nThe ledger tool is `{rel}/ledger.py` (Python 3). If you can't see "
                    f"a \"Ledger brief\" in your context, its hooks aren't set up on this machine: run "
                    f"`python {rel}/ledger.py init` from the repository root (safe to re-run), then "
                    f"`python {rel}/ledger.py brief`.\n")
        done.append(f"CLAUDE.md now imports {imp}")
    con = connect()
    export(con)
    print("ledger ready in " + root + "\n" + "\n".join(f"- {x}" for x in done))


# ---------------------------------------------------------------- the shared ledger: setup

def shared_home():
    return os.environ.get("LEDGER_HOME") or os.path.join(os.path.expanduser("~"), DIRNAME)


def claude_settings():
    return os.path.join(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude"),
                        "settings.json")


def write_private(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def install_hooks(sfile, base, wrap=lambda c: c):
    """Put the three ledger hooks into a Claude Code settings file, replacing earlier ledger hooks there."""
    try:
        with open(sfile, encoding="utf-8") as f:
            settings = json.load(f)
    except OSError:
        settings = {}
    except ValueError:
        sys.exit(f"{sfile} isn't valid JSON; fix it and run this again")
    ours = {
        "SessionStart": {"matcher": "startup|resume|compact|clear", "hooks": [
            {"type": "command", "command": wrap(f"{base} hook-start a"), "timeout": 30},
            {"type": "command", "command": wrap(f"{base} hook-start b"), "timeout": 30}]},
        "UserPromptSubmit": {"hooks": [{"type": "command", "command": wrap(f"{base} hook-prompt"), "timeout": 15}]},
        "PreCompact": {"matcher": "manual|auto", "hooks": [
            {"type": "command", "command": wrap(f"{base} hook-precompact"), "timeout": 30}]},
    }
    hooks = settings.setdefault("hooks", {})
    for ev, entry in ours.items():
        hooks[ev] = [x for x in hooks.get(ev, []) if not is_ledger_hook(x)] + [entry]
    os.makedirs(os.path.dirname(sfile), exist_ok=True)
    with open(sfile, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(settings, indent=2, ensure_ascii=False) + "\n")


def cmd_shared_setup(args):
    """Use the shared ledger on this machine: config in ~/.ledger, hooks for every session in ~/.claude."""
    _, op = parse_opts(args)
    d = shared_home()
    os.makedirs(d, exist_ok=True)
    use_dir(d)
    cfg = read_config()
    _, gname = git(["config", "user.name"], os.getcwd())
    cfg["owner"] = op.get("owner") or cfg.get("owner") or (gname.split() or ["the owner"])[0]
    cfg["backend"] = "supabase"
    write_private(CONFIG, json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")
    write_private(os.path.join(d, ".gitignore"), "*\n")  # nothing here belongs in any repository
    use_dir(d)
    done = [f"owner: {OWNER}; config in {CONFIG}"]
    if op.get("url") or op.get("key"):
        cpath = os.path.join(d, "credentials.json")
        try:
            with open(cpath, encoding="utf-8") as f:
                saved = json.load(f)
        except (OSError, ValueError):
            saved = {}
        saved.update({k: op[k] for k in ("url", "key") if isinstance(op.get(k), str)})
        write_private(cpath, json.dumps(saved, indent=2) + "\n")
        done.append(f"saved the URL and key in {cpath}")
    url, key, token, where = creds()
    done.append(f"credentials: {where}" + ("" if token else " (no token: the server must get it from an "
                                                               "x-ledger-token header, as a cloud network secret adds)"))
    if op.get("no-check"):
        pass
    elif not (url and key):
        done.append("not connected yet: set the URL and key (see README, 'Shared ledger')")
    else:
        try:
            data = RPC("ledger_pull", {}, TIMEOUT)
            done.append(f"connected as token '{data.get('by')}': {len(data.get('items') or [])} items in the "
                        "shared ledger")
        except SharedError as e:
            done.append(f"NOT connected: {e}")
    if not op.get("no-hooks"):
        install_hooks(claude_settings(), tool_cmd())
        done.append(f"hooks for every Claude Code session on this machine in {claude_settings()}")
    print("shared ledger set up\n" + "\n".join(f"- {x}" for x in done))


CLOUD_TOOL = "~/.ledger/tool/ledger.py"


def cmd_shared_repo(args):
    """Add the shared ledger's hooks to this repository's committed .claude/settings.json, for cloud sessions only.
    Locally they do nothing (the machine's own hooks from shared-setup run instead)."""
    _, op = parse_opts(args)
    code, top = git(["rev-parse", "--show-toplevel"], os.getcwd())
    root = os.path.abspath(op["root"]) if isinstance(op.get("root"), str) else (top if code == 0 and top else None)
    if not root:
        sys.exit("run this inside a git repository, or pass --root PATH")
    guard = f'[ "$CLAUDE_CODE_REMOTE" = "true" ] && [ -f {CLOUD_TOOL} ] && python3 {CLOUD_TOOL} --dir ~/.ledger'
    install_hooks(os.path.join(root, ".claude", "settings.json"), guard, wrap=lambda c: f"{c} || true")
    print(f"cloud hooks in {os.path.join(root, '.claude', 'settings.json')}; commit that file. They run only in "
          "cloud sessions whose environment installs the tool (README, 'Shared ledger').")


def cmd_new_token(args):
    """Make a token for one machine or environment. Prints the SQL that registers its hash, never the token."""
    pos, op = parse_opts(args)
    if not pos or not re.fullmatch(r"[A-Za-z0-9_.-]{1,40}", pos[0]):
        sys.exit("usage: new-token LABEL [--save]   (LABEL: letters, digits, - _ .)")
    label, d = pos[0], shared_home()
    os.makedirs(d, exist_ok=True)
    tok = "lt_" + secrets.token_urlsafe(32)
    if op.get("save"):
        path = os.path.join(d, "credentials.json")
        try:
            with open(path, encoding="utf-8") as f:
                saved = json.load(f)
        except (OSError, ValueError):
            saved = {}
        saved["token"] = tok
        write_private(path, json.dumps(saved, indent=2) + "\n")
        where = f"saved as this machine's token in {path}"
    else:
        path = os.path.join(d, f"token-{label}.txt")
        write_private(path, tok + "\n")
        where = f"written to {path}: copy it where it's needed, then delete that file"
    h = hashlib.sha256(tok.encode("utf-8")).hexdigest()
    print(f"token '{label}' {where}.\nRegister it by running this SQL in the Supabase project (it holds only the "
          f"hash):\n  insert into ledger.tokens(label, hash) values ('{label}', '{h}')\n"
          "  on conflict (label) do update set hash = excluded.hash, revoked_at = null;")


def cmd_shared_status(con):
    url, key, token, where = creds()
    pulled = get_state(con, "local_pulled_at") or "never"
    n = con.execute("SELECT project, COUNT(*) n FROM items GROUP BY project ORDER BY project").fetchall()
    waiting = 0
    if os.path.exists(OUTBOX):
        with open(OUTBOX, encoding="utf-8") as f:
            waiting = sum(1 for s in f if s.strip())
    print(f"shared ledger, owner {OWNER}; this folder's project: {PROJECT}\n"
          f"credentials: {where}\nlast pull: {pulled}\n"
          f"problem: {get_state(con, 'local_problem') or 'none'}\nchanges waiting to be sent: {waiting}\n"
          "items by project: " + (", ".join(f"{r['project']} {r['n']}" for r in n) or "none"))


# ---------------------------------------------------------------- main

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    dir_arg = None
    if len(a) >= 2 and a[0] == "--dir":
        dir_arg, a = a[1], a[2:]
    if not a or a[0] in ("-h", "--help", "help"):
        print(__doc__)
        return
    c, rest = a[0], a[1:]
    standalone = {"init": lambda: cmd_init(rest, dir_arg), "shared-setup": lambda: cmd_shared_setup(rest),
                  "shared-repo": lambda: cmd_shared_repo(rest), "new-token": lambda: cmd_new_token(rest)}
    if c in standalone:
        standalone[c]()
        return
    found = dir_arg or find_dir()
    if not found or not os.path.isdir(found):
        if c.startswith("hook-"):
            return  # no ledger here: hooks stay quiet
        sys.exit("no .ledger folder found: run `ledger.py init` from the repository root, or pass --dir")
    use_dir(found)
    hin = read_hook_input() if c.startswith("hook-") else {}
    if SHARED and hin.get("cwd"):
        set_project(hin["cwd"])
    if c.startswith("hook-") and not (in_scope(hin) or "--force" in rest):
        return
    write = c in ("add", "set", "link", "override", "focus", "import")
    global TIMEOUT, NO_SYNC, IN_HOOK
    IN_HOOK = c.startswith("hook-")
    if IN_HOOK:
        TIMEOUT = HOOK_TIMEOUT
    lock = None
    NO_SYNC = False
    if SHARED:
        lock = CacheLock(os.path.join(LEDGER_DIR, "ledger.lock"))
        if not lock.acquire(60 if write else 10):
            lock = None
            if write:
                sys.exit("ledger: another session on this machine has been saving to the shared ledger for a minute; "
                         "nothing was saved. Try the same command again.")
            NO_SYNC = True  # a read: use the copy on this machine as it is
    try:
        run_command(c, rest, hin, write)
    finally:
        if lock:
            lock.release()


def run_command(c, rest, hin, write):
    try:
        con = connect(fresh=write)
    except LedgerFileError as err:
        if c == "hook-start" and (rest[:1] or ["a"])[0] == "a":
            emit("SessionStart", f"LEDGER FILE PROBLEM: {err}. The ledger can't load until this is fixed; tell "
                                 f"{OWNER} before relying on any project state.")
            return
        if c.startswith("hook-"):
            return
        sys.exit(f"ledger: {err}")
    if c == "add":
        cmd_add(con, rest)
    elif c == "set":
        cmd_set(con, rest)
    elif c == "link":
        add_link(con, rest[0], rest[1], rest[2], " ".join(rest[3:]))
        con.commit()
        print("linked")
    elif c == "show":
        cmd_show(con, rest[0])
    elif c == "find":
        for r in related(con, " ".join(rest), live_only=False, limit=40):
            print(line(r, 160))
    elif c == "check":
        cmd_check(con, rest)
    elif c == "list":
        cmd_list(con, rest)
    elif c == "audit":
        print("\n".join(audit(con)) or "no warnings")
    elif c == "brief":
        export(con)
        _, bo = parse_opts(rest)
        print(make_brief(con, None, family_for(bo.get("project")) or FAMILY))
    elif c == "override":
        cmd_override(con, rest)
    elif c == "focus":
        cmd_focus(con, rest)
    elif c == "import":
        cmd_import(con, rest)
    elif c == "match":
        mp, mo = parse_opts(rest)
        print(prompt_report(con, " ".join(mp), family_for(mo.get("project")) or FAMILY) or "(nothing flagged)")
    elif c == "hook-start":
        part = rest[0] if rest and rest[0] in ("a", "b") else "a"
        if part == "a":
            export(con)
        emit("SessionStart", make_brief(con, part, FAMILY))
    elif c == "hook-prompt":
        rep = prompt_report(con, hin.get("prompt", ""), FAMILY)
        if rep:
            emit("UserPromptSubmit", rep)
    elif c == "hook-precompact":
        cmd_precompact(con)
    elif c == "handoff":
        cmd_handoff(con)
    elif c == "export":
        export(con)
        print("exported")
    elif c == "shared-status":
        cmd_shared_status(con)
    else:
        sys.exit(f"unknown command {c}")
    if write:
        export(con)


if __name__ == "__main__":
    main()
