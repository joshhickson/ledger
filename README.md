# ledger

A project ledger for Claude Code. It records the instructions, decisions and rules you give Claude Code, in your own
words, inside the repository. Hooks then show that record to every new session and to sessions that have been
compacted (summarised to save space), and flag a message that seems to change an earlier rule.

## How this was made

AI coding agents (Claude Code) designed and wrote all of the code, tests and documentation in this repository, under
the direction of Joshua Hickson. The repository's history is one squashed commit, so
it doesn't record who proposed which idea.

## Status, read this first

- **Tests:** the 55 checks in `test_ledger.py` pass (Python 3.13, about 1.3 seconds). The shared ledger adds 40
  checks in `test_shared.py` (no network: a stand-in plays the database) and 10 in `test_shared_live.py` against a
  real Supabase project; all pass (Python 3.10 on Windows).
- **Real Claude Code sessions:** until 2 November 2026 this published version had never run in a real Claude Code
  session. On that day it was run in short test sessions only (Claude Code 2.1.316: five headless runs and one
  interactive session) on a made-up sample record, in a throwaway container. The hooks fired each time.
  [`showcase/demo/`](showcase/demo/) has the transcripts and screenshots.
- **Shared ledger, 2 November 2026:** one headless Claude Code session on Windows (2.1.296) and one cloud session
  were run against a real Supabase project. Both got the brief from the database at session start. The cloud session
  read an item recorded on the Windows machine and wrote a note that the Windows machine then read. The cloud
  session's token was added by the cloud environment's network secret and never reached the session.
- **Day-to-day use:** none yet for this version. The owner's daily use was of an earlier, multi-project version that
  isn't published here.

## Known limits

- **The override warning is a word matcher.** It compares your message with the tags each rule was saved with. It
  misses synonyms and paraphrases ("Google Analytics" against a rule tagged `analytics` was not flagged on the sample
  record; nor was "add a tracker pixel" against a rule tagged `tracking`).
- **On a small ledger it rarely fires.** One matching tag isn't enough until a ledger holds about a dozen standing
  items. On the 8-item sample record, 1 of 7 messages that contradict a rule or decision was flagged ("from now on use
  cups and ounces"). Only 2 of the 55 tests cover the warning.
- **The brief does most of the work.** In the test sessions the assistant still stopped and asked about React and
  Google Analytics, which the matcher missed, because the session-start brief lists every rule. Each of those
  observations is one run, so treat them as examples, not results.
- **Permission prompts.** Every ledger command the assistant runs (`check`, `show`, `override`) needs your approval
  unless you allowlist it. In headless mode (`claude -p`) unapproved commands are refused. See step 7 below.
- **You can't see the hook output.** The brief and the "LEDGER CHECK" note go to the assistant; Claude Code 2.1.316
  doesn't show them on screen, even in its transcript view. Run `ledger.py brief` to read the brief yourself.
- **Paths.** The hooks, brief and LEDGER CHECK note contain absolute paths on your machine, including your home
  folder. Check before you share a screenshot.
- **Not tested at all:** long sessions, a real `/compact`, Windows, `import` from a real older ledger, and use over
  weeks.
- **Small things:** `add --created` accepts any text without checking it's a date in the tool's format
  (`YYYY-MM-DD HH:MM`); the note `init` adds to CLAUDE.md says `python`, which some systems call `python3`.
- **Privacy:** the ledger keeps your words verbatim. In a public repository anyone can read them; use `init --private`.

Shared ledger only:

- **Tried once each.** One local and one cloud session, a few minutes each, on test items. Not tried: the per-message
  override check or a compaction in a cloud session, two sessions writing at the same moment for real (only
  simulated), a long outage, and macOS or Linux machines.
- **Every hook waits for the network.** Each session start and each message you send pulls the record from Supabase:
  about 0.2 seconds in the tests. If Supabase is slow or down, a hook waits up to 6 seconds, then uses the last copy.
- **One record for everything.** Item IDs are shared across all projects, so a new repository's first rule may be
  R14. A session sees its own project plus `all`; the brief only counts the items of other projects.
- **Last edit wins, field by field.** If two sessions change the same field of the same item, the later one wins with
  no warning.
- **Repositories need a committed file for cloud sessions.** `shared-repo` writes the hooks into
  `.claude/settings.json`. The file holds no secrets, but in a public repository it shows that you use this tool.
- **The cloud copy of the tool is fixed at the session's start** (the setup script downloads it, and cloud
  environments cache the script's result). After the tool changes, the cache may keep the old copy for a while.
- **Supabase's free plan pauses a project after a week without use.** Sessions then report a "SHARED LEDGER PROBLEM"
  until you restore the project in the Supabase dashboard.
- **Moving an existing per-repository ledger into the shared one** isn't built yet.

## Try it in five minutes

Needs git, Python 3.10 or later with SQLite's FTS5 (standard in python.org builds and most Linux builds) and, for step
6, Claude Code. Every step below was run as written on 2 November 2026 in a Linux container; the whole command part
took under two seconds.

1. Make a throwaway project and add the ledger to it:

   ```bash
   mkdir ledger-demo && cd ledger-demo && git init
   git submodule add https://github.com/joshhickson/ledger tools/ledger
   python3 tools/ledger/ledger.py init --owner "Your name"
   ```

   `init` creates `.ledger/`, adds three hooks to `.claude/settings.local.json` and adds a short section to `CLAUDE.md`.

2. Record two rules and a decision. In normal use Claude does this while you talk; here you type them:

   ```bash
   python3 tools/ledger/ledger.py add rule "Metric units only" --quote "metric only: grams and millilitres, no cups" --basis owner-words --tags metric,units,grams,cups,ounces
   python3 tools/ledger/ledger.py add decision "Plain HTML and CSS, no framework" --quote "plain HTML it is, no framework" --basis owner-words --tags framework,react,vue,html,css
   python3 tools/ledger/ledger.py add rule "No tracking or analytics" --quote "no tracking, no analytics" --basis owner-words --tags tracking,analytics,cookies
   ```

3. See the brief each new session will be given:

   ```bash
   python3 tools/ledger/ledger.py brief
   ```

4. Test the override check without Claude:

   ```bash
   python3 tools/ledger/ledger.py match "from now on use cups and ounces instead of grams"
   python3 tools/ledger/ledger.py match "actually let's switch to React"
   ```

   The first prints a "LEDGER CHECK" note naming R1 and quoting your words. The second prints `(nothing flagged)`:
   with only three items, one matching tag isn't enough (see Known limits).

5. Open `.ledger/ledger.html` in a browser. That's your view of the record.

6. Start Claude Code in the folder (`claude`), and send `actually let's switch to React`. In the test run the
   assistant named D1, quoted "plain HTML it is, no framework" with its date, and asked whether to change it for good,
   make a one-time exception or keep it, before changing anything.

7. Optional: stop the permission prompts for ledger commands. Add a `permissions` entry to
   `.claude/settings.local.json`, next to the `hooks` entry `init` wrote. Use the Python path that appears in the
   brief's `check` command:

   ```json
   "permissions": {
     "allow": [
       "Bash(/path/to/python3 tools/ledger/ledger.py:*)",
       "Bash(python3 tools/ledger/ledger.py:*)"
     ]
   }
   ```

   With this in place, a headless run had no refused commands. If the assistant uses another form of the command,
   add that too.

When you're done, delete the `ledger-demo` folder.

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
git submodule add https://github.com/joshhickson/ledger tools/ledger
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
| `match "text"` | What the override check would flag for a message (for testing) |
| `brief`, `handoff`, `audit` | Read the state |

## Shared ledger: one record for every session, local and cloud

A repository's ledger only reaches sessions that have that repository. A Claude Code cloud session sees only the
repository it was started on, so it can't see rules you set while working somewhere else. The shared ledger keeps one
record in a Supabase database (a hosted Postgres) instead. Every session on your machine, and every cloud session you
set up for it, reads and writes the same record:

- each session sees the items for its own project (the repository's name) plus anything marked `all`;
- items, edits and links go straight to the database; the local `ledger.db` is just a cache;
- if the database can't be reached, the session works from the last copy, says so in the brief, and sends what it
  recorded when the connection is back.

### Who can read it

Your words are personal data, so access is closed by default:

- The tables sit in a database schema that Supabase's public API doesn't serve, with row-level security on and no
  policies. The project's public key opens nothing by itself.
- The only way in is two database functions, `ledger_pull` and `ledger_push`. Each one first checks a **ledger
  token**: a random 43-character secret. The database stores only its SHA-256 hash.
- Give each machine or cloud environment its own token, so you can cut one off (`update ledger.tokens set revoked_at
  = now() where label = '...'`) without touching the others.
- In a cloud session the token doesn't have to be in the session at all: a cloud environment's *network secret* adds
  it to each request as an `x-ledger-token` header, outside the session.
- Nothing about the database goes into a repository. The URL, key and token live in environment variables or in
  `~/.ledger/credentials.json`, outside every repository.

`test_shared_live.py` checks this against a real project: with only the public key, both functions refuse, the
tables can't be read, and a wrong token is refused.

### Set it up

1. Make a Supabase project and run [`supabase/schema.sql`](supabase/schema.sql) in its SQL editor.
2. Point this machine at it and make a token:

   ```bash
   python tools/ledger/ledger.py shared-setup --owner "Your name" --url https://YOURPROJECT.supabase.co --key sb_publishable_... --no-hooks
   python tools/ledger/ledger.py new-token laptop --save
   ```

   `new-token` prints a line of SQL holding the token's hash. Run it in the SQL editor. The token itself is saved in
   `~/.ledger/credentials.json` and never printed.
3. Run `python tools/ledger/ledger.py shared-setup` again, without `--no-hooks`. It checks the connection and adds
   the hooks to `~/.claude/settings.json`, so **every** Claude Code session on this machine gets the brief for its
   project.

### Cloud sessions

Cloud sessions don't read `~/.claude/settings.json`, so they need three things:

1. **The cloud environment** (claude.ai/code → environment settings):
   - Environment variables: `LEDGER_SUPABASE_URL=https://YOURPROJECT.supabase.co`,
     `LEDGER_SUPABASE_KEY=sb_publishable_...`, and `TZ=` your time zone (for example `America/Los_Angeles`), so the
     times cloud sessions record match yours.
   - A network secret: allowed website `YOURPROJECT.supabase.co`, header name `x-ledger-token`, no prefix, value: a
     token made with `new-token cloud` (it's written to `~/.ledger/token-cloud.txt`; delete that file afterwards).
     This also lets the session reach the database.
   - A setup script that installs the tool:

     ```bash
     ( mkdir -p ~/.ledger/tool \
       && curl -fsSL https://raw.githubusercontent.com/joshhickson/ledger/main/ledger.py -o ~/.ledger/tool/ledger.py \
       && curl -fsSL https://raw.githubusercontent.com/joshhickson/ledger/main/LEDGER.md -o ~/.ledger/tool/LEDGER.md \
       && python3 ~/.ledger/tool/ledger.py shared-setup --owner "Your name" --no-hooks --no-check ) \
       || echo "shared ledger: install failed; this session runs without it"
     ```

2. **Each repository** you start cloud sessions on gets the hooks in its committed `.claude/settings.json`:

   ```bash
   python tools/ledger/ledger.py shared-repo
   git add .claude/settings.json && git commit -m "Shared ledger hooks for cloud sessions"
   ```

   They only run when `CLAUDE_CODE_REMOTE` is `true` and the tool is installed, and they never fail a session. On
   your own machine they do nothing, so the machine-wide hooks don't run twice. The file holds no secrets.

## Moving from an older ledger

`import OLD.db --project NAME` copies one project's items (and items marked `all`) from an older ledger database into
an empty per-repository ledger. The old database is opened read-only. `--as NAME` names the person the old ledger
treated as owner, so their items become the new owner's. This command hasn't been tried on a real older ledger.

## Tests

```bash
python tools/ledger/test_ledger.py
python tools/ledger/test_shared.py
```

The tests use throwaway folders next to the tool, including a real git merge from two branches, and never open a
real ledger.

## Licence

MIT. See [LICENSE](LICENSE).
