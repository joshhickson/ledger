# Demo pieces for ledger

Everything here was made on 2 November 2026 by an AI agent (Claude Code) in a cloud container, on a **made-up sample
record** for a fictional recipe website. The owner in the record is called "Owner". No real data was used.

## What's here and how each piece was made

| Piece | What it shows | How it was made |
|---|---|---|
| [`make-sample-record.sh`](make-sample-record.sh) | The made-up record: 1 goal, 3 rules, 3 decisions (one marked as the agent's own unconfirmed call), 1 question, 1 task, and a focus | Written by hand. Run in `/demo/recipe-site`, a throwaway git repository with the ledger added as a submodule from GitHub and `init --owner "Owner"` already run |
| [`output/hook-start-a.json`](output/hook-start-a.json), [`output/hook-start-b.json`](output/hook-start-b.json) | The exact session-start output: what the two SessionStart hooks print | `echo '{"hook_event_name":"SessionStart","source":"startup","cwd":"/demo/recipe-site"}' \| python3 tools/ledger/ledger.py hook-start a` (and `b`) |
| [`output/hook-prompt-cups.json`](output/hook-prompt-cups.json) | The exact override warning for "from now on use cups and ounces in the recipes" | The same, with `hook-prompt` and a `prompt` field. For "actually let's switch to React for the recipe pages" the hook printed nothing. Run with a `cwd` outside the repository, it also printed nothing, as designed |
| [`MATCHER-RESULTS.md`](MATCHER-RESULTS.md) | Which of 9 test messages the override check flags on the sample record | `python3 tools/ledger/ledger.py match "<message>"` for each |
| [`SESSIONS.md`](SESSIONS.md) | Six short headless Claude Code runs: four with the ledger, one control with the same rules in a plain CLAUDE.md, one with ledger commands allowlisted | `claude -p` in the demo folders; replies copied verbatim from the logs, IDs left out |
| [`screenshots/1-session-start-brief.png`](screenshots/1-session-start-brief.png) | The session-start brief | Text from the two hook files above, laid out as a page by [`render.py`](render.py) and photographed by [`shoot.js`](shoot.js) (headless Chromium via Playwright). This text goes to the assistant; it isn't shown on screen |
| [`screenshots/2-override-warning.png`](screenshots/2-override-warning.png) | The LEDGER CHECK note | The same way, from `hook-prompt-cups.json` |
| [`screenshots/3-permission-prompt.png`](screenshots/3-permission-prompt.png) | Interactive Claude Code asking approval to run a ledger lookup | Claude Code 2.1.316 run interactively inside `tmux` (110×45) in `/demo/recipe-site`. The screen was captured with `tmux capture-pane -e` (saved in [`raw/`](raw/)), converted to HTML with the `ansi2html` package and photographed the same way |
| [`screenshots/4-reply-react.png`](screenshots/4-reply-react.png) | The assistant's reply to "actually let's switch to React for the recipe pages", after one approved lookup | Same tmux session |
| [`screenshots/5-override-recorded.png`](screenshots/5-override-recorded.png) | After answering "change it for good, built to static pages ahead of time" and approving the `override` command | Same tmux session |
| [`screenshots/6-ledger-page.png`](screenshots/6-ledger-page.png), [`6b-ledger-page-phone.png`](screenshots/6b-ledger-page-phone.png) | The web page (`ledger.html`) at desktop and phone width, after that override: D4 supersedes D1 | The generated page was copied unchanged to [`raw/ledger.html`](raw/ledger.html) and photographed by `shoot.js` at 1200 px and 390 px wide |

In screenshots 4 and 5, the text in the input box at the bottom is Claude Code's own suggested next message. Nobody
typed it, and it wasn't sent.

## To remake them

From the repository root, with Python 3, `pip install ansi2html` and Node with Playwright:

```bash
python3 -I showcase/demo/render.py   # writes showcase/demo/pages/*.html
node showcase/demo/shoot.js          # writes showcase/demo/screenshots/*.png
```

## Not made

- **A video or GIF.** The interactive session needed two permission approvals and a typed answer, which were driven by
  `tmux send-keys`. A recording would be possible but would show those pauses. Not attempted.
- **A side-by-side screenshot of the control run.** It's in [`SESSIONS.md`](SESSIONS.md) as text only.

## Privacy check of this folder

Searched every file here for email addresses, IP addresses, home-folder paths (`/home/`, `/Users/`, `/root`), session
and tool IDs, tokens and keys, and real names. Paths that appear are `/demo/...` (made for this demo) and
`/usr/local/bin/python3`. The only name in the record is the placeholder "Owner".
