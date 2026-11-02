"""Renders the showcase screenshots from captured text.

Run with:  python3 -I showcase/demo/render.py   (from the repository root)
Needs: the ansi2html Python package. Then take the screenshots with Node Playwright:  node showcase/demo/shoot.js

Inputs (all in showcase/demo/):
  raw/*.ansi            tmux captures (with colour codes) of an interactive Claude Code session
  raw/ledger.html       the page the tool generated for the sample record, copied unchanged
  output/hook-*.json    what the ledger's hooks printed when fed sample hook input
Outputs: showcase/demo/pages/*.html (then shoot.js turns them into showcase/demo/screenshots/*.png)
"""
import html
import json
import pathlib

from ansi2html import Ansi2HTMLConverter
import re

D = pathlib.Path(__file__).resolve().parent
OUT = D / "pages"
OUT.mkdir(exist_ok=True)


def page(title, body_html, note):
    return f"""<!doctype html><meta charset="utf-8"><style>
body{{margin:0;background:#1e1e1e;font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif}}
.cap{{background:#2d2d2d;color:#ddd;padding:10px 16px;font-size:14px;border-bottom:1px solid #444}}
.cap b{{color:#fff}} .note{{color:#aaa;font-size:12px;margin-top:4px}}
pre{{margin:0;padding:14px 16px;color:#ddd;font:13px/1.35 'DejaVu Sans Mono',Menlo,monospace;white-space:pre-wrap}}
</style><div class="cap"><b>{html.escape(title)}</b><div class="note">{html.escape(note)}</div></div>{body_html}"""


def ansi_page(src, title, note, keep_from=None):
    text = (D / "raw" / src).read_text(encoding="utf-8")
    lines = [ln.rstrip() for ln in text.splitlines()]
    if keep_from:
        def strip(s):
            return re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", s)
        idx = next((i for i, ln in enumerate(lines) if keep_from in strip(ln)), 0)
        lines = lines[idx:]
    while lines and not lines[-1].strip():
        lines.pop()
    conv = Ansi2HTMLConverter(inline=True, scheme="xterm", dark_bg=True)
    return page(title, "<pre>" + conv.convert("\n".join(lines), full=False) + "</pre>", note)


def text_page(json_file, title, note):
    ctx = json.loads((D / "output" / json_file).read_text())["hookSpecificOutput"]["additionalContext"]
    return page(title, "<pre>" + html.escape(ctx) + "</pre>", note)


shots = {
    "1-session-start-brief.png": page(
        "Session start: the brief the ledger hands the assistant (parts a and b)",
        "<pre>" + html.escape(
            json.loads((D / "output/hook-start-a.json").read_text())["hookSpecificOutput"]["additionalContext"]
            + "\n\n" + json.loads((D / "output/hook-start-b.json").read_text())["hookSpecificOutput"]["additionalContext"]
        ) + "</pre>",
        "Text printed by `ledger.py hook-start a` and `hook-start b` for the made-up sample record. Claude Code "
        "passes it to the assistant; it is not shown on screen in Claude Code 2.1.316."),
    "2-override-warning.png": text_page(
        "hook-prompt-cups.json", "Override warning: the LEDGER CHECK note for \"from now on use cups and ounces in the recipes\"",
        "Text printed by `ledger.py hook-prompt`. Claude Code passes it to the assistant with the message; it is "
        "not shown on screen."),
    "3-permission-prompt.png": ansi_page(
        "02-permission-prompt.ansi", "Interactive Claude Code: the assistant asks to look up the ledger",
        "tmux capture of Claude Code 2.1.316 in the demo folder. Every ledger command needs approval unless allowlisted."),
    "4-reply-react.png": ansi_page(
        "03-reply-react.ansi", "Interactive Claude Code: reply to \"actually let's switch to React for the recipe pages\"",
        "tmux capture. The word-matcher did not flag this message; the assistant found D1 from the session brief and "
        "its own ledger lookup. The text in the input box at the bottom is Claude Code's suggestion, not typed."),
    "5-override-recorded.png": ansi_page(
        "04-override-recorded.ansi", "Interactive Claude Code: the answer is recorded as a superseding decision",
        "tmux capture after answering \"change it for good, built to static pages ahead of time\" and approving the "
        "ledger command. The text in the input box is Claude Code's suggestion, not typed.",
        keep_from="change it for good, built"),
}

for name, doc in shots.items():
    (OUT / name.replace(".png", ".html")).write_text(doc, encoding="utf-8")
print("\n".join(sorted(x.name for x in OUT.iterdir())))
