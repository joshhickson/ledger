"""Round trip against a real shared ledger (Supabase). Needs the URL, key and a token, from the environment
(LEDGER_SUPABASE_URL, LEDGER_SUPABASE_KEY, LEDGER_TOKEN) or ~/.ledger/credentials.json. Everything it writes goes
under the project "_live_test"; it prints the SQL that removes it afterwards. Run: python test_shared_live.py
"""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ledger as L  # noqa: E402

fails = 0
PROJECT = "_live_test"
L.PULL_FRESH = 0  # every command pulls


def check(name, ok, detail=""):
    global fails
    fails += not ok
    print(f"{'ok  ' if ok else 'FAIL'} {name}" + (f"\n      {str(detail)[:400]}" if not ok and detail else ""))


def run(*args, stdin=None):
    out, err = io.StringIO(), io.StringIO()
    old_argv, old_stdin = sys.argv, sys.stdin
    sys.argv, sys.stdin = ["ledger.py", *args], io.StringIO(json.dumps(stdin) if stdin is not None else "")
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


def raw(path, body=None, key=None):
    """A request with only the public key: what anyone who found the URL and key could try."""
    url, k, _, _ = L.creds()
    req = urllib.request.Request(url.rstrip("/") + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"apikey": key or k, "Content-Type": "application/json"},
                                 method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


L.use_dir(os.path.join(os.path.expanduser("~"), ".ledger")) if os.path.isdir(
    os.path.join(os.path.expanduser("~"), ".ledger")) else None
url, key, token, where = L.creds() if L.LEDGER_DIR else ("", "", "", "")
if not (url and key and token):
    sys.exit("needs the URL, key and a token (environment or ~/.ledger/credentials.json)")
os.environ.update({"LEDGER_SUPABASE_URL": url, "LEDGER_SUPABASE_KEY": key, "LEDGER_TOKEN": token,
                   "LEDGER_PROJECT": PROJECT})

tmp = tempfile.mkdtemp(prefix="ledger_live_")
try:
    dirs = []
    for name in ("laptop", "cloud"):
        d = os.path.join(tmp, name, ".ledger")
        os.makedirs(d)
        with open(os.path.join(d, "config.json"), "w") as f:
            json.dump({"owner": "Tester", "backend": "supabase"}, f)
        dirs.append(["--dir", d])
    A, B = dirs
    stamp = time.strftime("%H%M%S")

    t0 = time.time()
    out = run(*A, "add", "rule", f"Live rule {stamp}", "--quote", f"live test words {stamp}", "--basis",
              "owner-words", "--tags", "livetest,water,midday")
    check("add on machine A reaches Supabase", "added R" in out and "saved on this machine" not in out, out)
    rid = out.split("added ")[1].split()[0]
    print(f"     (add, pull + push: {time.time() - t0:.1f} s)")
    t0 = time.time()
    b = context(run(*B, "hook-start", "b", stdin={"cwd": tmp}))
    print(f"     (session start on machine B: {time.time() - t0:.1f} s)")
    check("machine B's session start shows it", f"{rid} Live rule {stamp}" in b, b)
    check("machine B can read the owner's exact words", f"live test words {stamp}" in run(*B, "show", rid))
    run(*B, "set", rid, "priority=1")
    run(*A, "set", rid, "status=parked")
    out = run(*B, "show", rid)
    check("edits from both machines to different fields are both kept", "parked" in out, out)

    # Two sessions take the same new ID: A pulls, then another session adds first, then A pushes.
    real = L.RPC

    def racing(fn, args, timeout):
        if fn == "ledger_push" and any(i.get("_new") for i in args["p_batch"]["items"]):
            L.RPC = real
            nid = args["p_batch"]["items"][0]["id"]
            real("ledger_push", {"p_batch": {"project": PROJECT, "items": [{
                "_new": True, "id": nid, "project": PROJECT, "kind": "note", "title": f"Racer {stamp}",
                "created": L.now(), "updated": L.now()}], "links": [], "events": [], "state": []}}, timeout)
        return real(fn, args, timeout)
    L.RPC = racing
    out = run(*A, "add", "note", f"Mine {stamp}")
    L.RPC = real
    check("a clash on a new ID is renumbered on the server and reported", "is now N" in out, out)

    os.environ["LEDGER_TOKEN"] = "lt_wrong"
    a = context(run(*B, "hook-start", "a", stdin={"cwd": tmp}))
    check("a wrong token is refused (and the brief says so)", "token not recognised" in a, a[:600])
    os.environ["LEDGER_TOKEN"] = token

    code, body = raw("/rest/v1/rpc/ledger_pull", {})
    check("with only the public key, ledger_pull is refused", code in (400, 401, 403) and "token" in body,
          (code, body[:200]))
    code, body = raw("/rest/v1/rpc/check_token", {"p_token": "x"})
    check("the token check itself can't be called from outside", code >= 400, (code, body[:200]))
    code, body = raw("/rest/v1/items?select=*")
    check("the tables aren't reachable through the Data API", code >= 400 or body.strip() == "[]", (code, body[:200]))
    code, body = raw("/rest/v1/rpc/ledger_push", {"p_batch": {"items": [{"_new": True, "id": "R999"}]}})
    check("with only the public key, ledger_push is refused", code >= 400 and "token" in body, (code, body[:200]))
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("\nall passed" if not fails else f"\n{fails} FAILED")
print(f"\nTo remove what this wrote, run in Supabase:\n  delete from ledger.links where src in (select id from "
      f"ledger.items where project = '{PROJECT}');\n  delete from ledger.events where project = '{PROJECT}';\n"
      f"  delete from ledger.items where project = '{PROJECT}';")
sys.exit(1 if fails else 0)
