"""Concurrent writers on the shared ledger. A small HTTP server on this machine plays Supabase (the same rules as
ledger_pull / ledger_push in supabase/schema.sql), and several copies of ledger.py run at once as separate
processes, each adding its own item. Every item must arrive exactly once, whether the writers share one machine's
cache (several sessions on one computer) or each have their own (cloud sessions).
    python test_concurrency.py
"""
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(HERE, "ledger.py")
fails = 0


def check(name, ok, detail=""):
    global fails
    fails += not ok
    print(f"{'ok  ' if ok else 'FAIL'} {name}" + (f"\n      {str(detail)[:600]}" if not ok and detail else ""))


class Store:
    def __init__(self):
        self.items, self.links, self.events, self.state = {}, {}, [], {}
        self.lock = threading.Lock()

    def pull(self):
        with self.lock:
            return {"items": [dict(i) for i in self.items.values()], "links": list(self.links.values()),
                    "state": list(self.state.values()), "by": "test"}

    def push(self, b):
        time.sleep(0.15)  # a slow network: widens the window between a session's pull and its push
        with self.lock:
            renamed, inserted = {}, []
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
                    inserted.append(nid)
                else:
                    nid = renamed.get(nid, nid)
                    if nid in self.items:
                        self.items[nid].update({k: v for k, v in it.items() if k != "id"})
            for ln in b.get("links", []):
                self.links[(renamed.get(ln["src"], ln["src"]), ln["rel"], renamed.get(ln["dst"], ln["dst"]))] = ln
            for ev in b.get("events", []):
                self.events.append(dict(ev, item=renamed.get(ev.get("item"), ev.get("item"))))
            for st in b.get("state", []):
                self.state[st["key"]] = st
            return {"renamed": renamed, "inserted": inserted, "missing": [], "by": "test"}


STORE = Store()


class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])) or b"{}")
        out = STORE.pull() if self.path.endswith("/ledger_pull") else STORE.push(body["p_batch"])
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


def machine(folder):
    d = os.path.join(folder, ".ledger")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "config.json"), "w") as f:
        json.dump({"owner": "Sam", "backend": "supabase"}, f)
    return d


def writers(dirs, n, label):
    """n processes at once, writer i on dirs[i % len(dirs)], each adding one task; returns their outputs."""
    procs = [subprocess.Popen([sys.executable, TOOL, "--dir", dirs[i % len(dirs)], "add", "task", f"{label} {i}"],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8")
             for i in range(n)]
    return [p.communicate(timeout=120)[0] for p in procs]


server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
os.environ.update({"LEDGER_SUPABASE_URL": f"http://127.0.0.1:{server.server_port}", "LEDGER_SUPABASE_KEY": "sb_test",
                   "LEDGER_TOKEN": "t", "LEDGER_PROJECT": "race", "NO_PROXY": "127.0.0.1,localhost",
                   "LEDGER_TEST_PAUSE": "0.3"})  # widen the gap where items used to vanish (7 of 8 did, before)
tmp = tempfile.mkdtemp(prefix="ledger_race_")
try:
    N = 8
    shared = machine(os.path.join(tmp, "one-computer"))
    outs = writers([shared], N, "same machine")
    titles = sorted(i["title"] for i in STORE.items.values() if i["title"].startswith("same machine"))
    check(f"{N} sessions on one machine adding at once: all {N} items arrive, none twice",
          titles == sorted(f"same machine {i}" for i in range(N)), (titles, outs))
    check("every one of them reports success, and none reports a failure",
          all("added T" in o and "Traceback" not in o for o in outs), outs)

    own = [machine(os.path.join(tmp, f"cloud{i}")) for i in range(N)]
    outs = writers(own, N, "own machine")
    titles = sorted(i["title"] for i in STORE.items.values() if i["title"].startswith("own machine"))
    check(f"{N} sessions on {N} machines (all picking the same next ID) at once: all {N} arrive, none twice",
          titles == sorted(f"own machine {i}" for i in range(N)), (titles, outs))
    check("the ID clashes were renumbered, and each session's last word is the correct ID",
          sum("CORRECTION: the new item is T" in o for o in outs) >= 1
          and all(o.index("CORRECTION") > o.index("added T") for o in outs if "CORRECTION" in o), outs)
    ids = [i["id"] for i in STORE.items.values()]
    check("no two items share an ID", len(ids) == len(set(ids)))
finally:
    server.shutdown()
    shutil.rmtree(tmp, ignore_errors=True)

print("\nall passed" if not fails else f"\n{fails} FAILED")
sys.exit(1 if fails else 0)
