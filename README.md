# ledger

A project ledger for Claude Code. It keeps your instructions, decisions and rules in your own words, inside the
repository, so new sessions and compacted ones don't lose track of what you asked for.

## Why

Long AI coding sessions drift. Compaction summaries and markdown handoffs keep the recent work and drop the intent: a
rule you set last week, a decision you made between two options, the reason a thing exists. You end up restating your
goals every few days.

The ledger records each instruction, decision or answer verbatim when you give it. Claude Code hooks then make sure
every session sees it:

- **At session start and after compaction**, a brief is injected: the current focus, open conflicts, tasks, and your
  standing goals, decisions and rules.
- **On every message you send**, the message is checked against those standing items. If it seems to change one, the
  session has to name the earlier item, quote what you said and when, and ask: change it for good, an exception just
  this once, or keep it?
- **Before compaction**, a handoff is written from the ledger.

You don't edit the ledger. You talk to Claude, and Claude records and reads it. `.ledger/ledger.html` shows it all.

## Setup

Requires Python 3.10+ (with SQLite's FTS5, as in the standard python.org and most Linux builds) and git.

Add it to a repository as a submodule and run `init` from the repository root:

```bash
git submodule add <this repository's URL> tools/ledger
python tools/ledger/ledger.py init --owner "Your name"
git add .gitmodules tools/ledger .ledger CLAUDE.md
git commit -m "Add the project ledger"
```

`init`:

- creates `.ledger/` with an empty record and your name;
- adds the three hooks to `.claude/settings.local.json`;
- adds an import of [`LEDGER.md`](LEDGER.md), the instructions sessions follow, to `CLAUDE.md`.

The hooks name this machine's Python, so they live in the uncommitted local settings. After cloning on another
machine, run `git submodule update --init` and then `init` once there. It's safe to re-run at any time.

## What's in `.ledger/`

| File | Committed | What it is |
|---|---|---|
| `ledger.jsonl` | yes | The record: every item, link, event and setting, one JSON object per line |
| `config.json` | yes | The owner's name |
| `ledger.db` | no | A local SQLite cache for search. It's rebuilt from `ledger.jsonl` whenever that file changes, after a pull say |
| `BRIEF.md`, `ledger.html`, `handoffs/` | no | Generated |

Commit `ledger.jsonl` along with the work it describes. Two machines can add to the ledger on separate branches:
the file merges with git's union driver (set in `.ledger/.gitattributes`). Duplicate lines collapse, the later edit
of an item wins, and two new items that got the same ID are both kept, with the later one renumbered and noted in the
audit.

**Privacy:** the ledger holds your words verbatim. In a public repository, everyone can read it. To use the ledger
there without committing it, run `init --private`.

## Commands

`python tools/ledger/ledger.py help` lists them all. The ones sessions use most:

| Command | What it does |
|---|---|
| `add KIND "title" --quote "..." --basis owner-words --tags ...` | Record a goal, ask, rule, decision, question, task... |
| `check <topic words>` | Everything in force that touches a topic. Sessions run this before planning |
| `override ID "new version" --quote "..." [--once]` | You changed a standing item, for good or just once |
| `focus ID` | What you chose to work on; it heads the brief |
| `set ID status=done` | Close or change an item |
| `brief`, `handoff`, `audit` | Read the state |

## Moving from a shared ledger

`import OLD.db --project NAME` copies one project's items (and items marked `all`) from an older ledger database into
an empty per-repository ledger. The old database is opened read-only. `--as NAME` names the person the old ledger
treated as owner, so their items become the new owner's.

## Tests

```bash
python tools/ledger/test_ledger.py
```

The tests use throwaway folders next to the tool, including a real git merge from two branches, and never open a
real ledger.
