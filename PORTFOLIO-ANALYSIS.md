# ledger: portfolio analysis (2 November 2026)

An independent review written for the owner. How claims are marked:
**[Checked: source]** means I opened the file or page, or ran the command, myself. **[Inferred]** means it's my judgment. **[Unknown]** means the repository and web can't settle it.
"The repo" means commit `db6aa1a` on `main`, the only commit. [Checked: `git log`]

---

## 1. What it is

- When you work with an AI coding assistant over many days, it forgets the rules and decisions you gave it earlier. ledger writes them down word for word, in a file kept with the project. [Checked: README.md]
- Each time a new assistant session starts, or an old one gets summarised to save space, the tool hands the assistant a short brief of your goals, rules and decisions. [Checked: ledger.py `make_brief`, `cmd_init` hook setup]
- When a new message from you seems to change one of those rules, the assistant gets a warning. It is then told to quote your earlier words and ask whether the change is for good, just this once, or a mistake. [Checked: ledger.py `prompt_report`; LEDGER.md]

## 2. What actually works today

**What I ran:**

1. **The test suite.** I ran `python3 test_ledger.py` (Python 3.13). All 55 checks passed in about 1.7 seconds. [Checked: ran it]
   - The checks include a real two-branch git merge of the record, rebuilding the cache after deletion, and refusing to load a file with merge-conflict markers. [Checked: test_ledger.py]
   - Only 2 of the 55 checks test the override warning itself: one rule that should be flagged, and "thanks, looks good" not being flagged. [Checked: test_ledger.py lines 116–119]
2. **A demo record.** In a throwaway git repository I ran `init`, then recorded a fictional recipe-website project: 1 goal, 3 rules, 2 decisions, 1 question and 1 task, with no personal data. `init` wrote the three hooks, the CLAUDE.md import and the .gitignore entries as the README says. [Checked: ran it]
3. **The override warning, tested with 13 messages.** I ran `match` on 13 test messages, first against that 7-item record, then after adding 20 more fictional rules.
   - **On the small record, nothing was flagged, including "actually let's switch to React" against the decision "no framework".** [Checked: ran it] The reason is arithmetic. The score for one matching tag is the logarithm of the number of standing items. With 7 items that is 1.95, which is below every threshold in the code (2.5, 4.0, 5.0). A single tag can't trigger a warning until there are about 13 standing items. [Checked: ledger.py `match_prompt`, lines 826–852]
   - **On the 27-item record, 6 of the 13 messages were flagged.** [Checked: ran it]
     - It caught "switch to React", "imperial only", "skip the tests" and "I know I said no frameworks, but…".
     - It missed "add Google Analytics" (against the rule "no tracking or analytics"), "add a tracker pixel" ("tracker" doesn't match the tag "tracking"), "put the recipes on WordPress" and "make the hero images bigger".
     - "From now on use cups and ounces" flagged the *website goal*, not the *metric-units rule* it actually contradicts.
   - The warning is a word and tag matcher, so it is only as good as the tags the assistant picked when it recorded the rule. [Checked: ledger.py `toks`, `TRIGGERS`] [Inferred]
4. **Real Claude Code sessions.** I ran Claude Code 2.1.316 in headless mode (`claude -p`) in the demo repository, one run per condition. The hooks fired: the session-start brief and the LEDGER CHECK note both reached the model. [Checked: ran it; output saved during the session, not committed]

| Message | With ledger | Same rules pasted into a plain CLAUDE.md, no hooks | Nothing (rules not given) |
|---|---|---|---|
| "actually let's switch to React…" | Named D1, quoted "plain HTML it is" with the date, asked change / exception / keep before planning | Flagged D1, asked to confirm, gave a React plan in the same reply | Planned the React migration |
| "from now on use cups and ounces…" | Named R3 and asked the three-way question, though the word-matcher had pointed at the wrong item | Flagged R3, gave a plan, asked "Should I go ahead?" | Hit the turn limit, no answer |

- **What the table shows:** with the ledger, the assistant asked before acting. With a plain rules list, it noticed the conflicts but leaned towards carrying on. [Checked: runs above] One run per cell, on a tiny project, in fresh short sessions, is an anecdote, not a result. [Inferred]
- **The ledger's main claim isn't tested here.** That claim is that rules survive long sessions and summarising. I did not test either. [Checked: what I ran]
- **In the cups case, the brief did the work.** The assistant found R3 because the session-start brief lists every rule, not because of the warning. [Inferred, from the hook output and the reply]
- **Friction found:** in headless mode, the assistant's attempts to run `ledger.py check` were refused for lack of permission. In interactive use you would be asked each time unless the command is allowlisted, and the README doesn't mention this. [Checked: `permission_denials` in the run output; README.md]

**Not run:** the `import` command against a real older ledger, Windows, a live `/compact`, and multi-week use. [Checked: what I ran]

## 3. Prior art

| Project | How ledger differs, or doesn't |
|---|---|
| [Claude Code's built-in memory: CLAUDE.md, `.claude/rules/`, auto memory](https://code.claude.com/docs/en/memory) | Already loads your rules into every session, and the project-root CLAUDE.md is re-read after `/compact`. There is also a `/doctor prompt-audit` that finds contradictions *between instruction files*. ledger adds verbatim quotes with dates, a status history (superseded, one-time exception) and a check on each message. It does not add persistence that CLAUDE.md lacks. [Checked: that page] |
| [claude-mem](https://github.com/thedotmack/claude-mem) | A very popular hooks-based memory plugin (about 110k stars, Apache-2.0). It records *what the agent did* and compresses it with AI. ledger records *what you said*, without AI, and treats your words as outranking everything else. The page describes no contradiction warning. [Checked: that page] |
| [beads](https://github.com/steveyegge/beads) | A git-friendly issue graph for agents (MIT, about 28k stars), with `supersedes` links, merge-safe IDs and Claude Code hooks. It is close to ledger in structure (it once used JSONL in the repo) but is about tasks, not your rules. [Checked: that page] |
| [Cline Memory Bank](https://docs.cline.bot/prompting/cline-memory-bank) | Markdown files the agent keeps up to date by convention. It has no decision log and no conflict detection. [Checked: that page] |
| [cc-compact](https://pypi.org/pypi/cc-compact/json) | Two hooks that save task state before compaction and point to it afterwards. Preferences are written by the agent. It covers the same compaction problem, but has no rules model. [Checked: PyPI JSON metadata] |
| [CtxGov](https://pypi.org/pypi/ctxgov/json) | Maps conflicts *between instruction files* before an agent runs. It is static, not checked on each message. [Checked: PyPI JSON metadata] |
| claude-brain ([a developer's write-up](https://dev.to/mikeadolan/i-wrote-500-lines-of-rules-for-claude-code-heres-how-i-made-it-actually-follow-them-3c8)) | Six hooks with a SQLite store. Its UserPromptSubmit hook searches memory on every prompt and injects reminders for specific rules, and it re-injects decisions after compaction. **This is the closest match to ledger's design.** The author reports before-and-after counts over 1,300+ sessions, which ledger has nothing like. [Checked: that page] |
| [Research: stale instruction files in coding agents (arXiv 2610.30571, October 2026)](https://www.emergentmind.com/papers/2610.30571) | Found that Claude Code *noticed* a conflict in 79 of 80 runs and still followed the stale file. One precedence sentence fixed most of it. This bears directly on ledger: noticing is not the hard part; precedence is. [Checked: summary page, not the PDF] |

**Is the override warning unusual?** Somewhat, but not unique.

- Prompt-time keyword checks against stored rules already exist; claude-brain's hook is one example. [Checked: dev.to write-up]
- The search engine also surfaced Reddit-described tools ("Claude Engram", "AutoDream") that re-inject rules through hooks. [Inferred: snippet only]
- **What I did not find elsewhere** is the specific protocol: quote the owner's own earlier words with the date, then force a three-way choice (change for good, one-time exception, keep). The choice is recorded either as a superseding item or as an exception note. [Inferred: no match in my searches, which is not proof none exists]

## 4. What's novel, nicely done, or common

**Novel (modest, and stated with care):**

- **The owner-words protocol.**
  - Every item records whose call it was: owner's words, owner picked my recommendation, my own unconfirmed call, and so on. [Checked: ledger.py `BASES`]
  - Unconfirmed agent decisions are flagged in an audit. [Checked: ledger.py `audit`]
  - Overrides are split into permanent changes and one-time exceptions, which leaves a reviewable trail. [Checked: `cmd_override`]
  - I found no tool that frames itself around *the human's verbatim words as the authority*. [Inferred]
- **"Don't silently comply, don't silently refuse."** The idea is clear and transferable, and the arXiv result above suggests it addresses a real failure mode. [Inferred]

**Nicely done:**

- **Git handling.** The committed JSONL record merges with git's union driver; on the same item, the later edit wins; colliding IDs are renumbered and noted in the audit; and conflict markers make the tool refuse to load rather than guess. All of this is tested with a real merge. [Checked: ledger.py `read_jsonl`; test_ledger.py]
- **Small footprint.** A single 1,231-line file, standard library only, with no AI calls and no network. [Checked: ledger.py imports]
- **Plain-language docs** that state the privacy risk of a public repository. [Checked: README.md]

**Common:**

- Hooks at session start, before compaction and on each prompt; a SQLite cache; full-text search; an HTML viewer; handoff files. Many tools above do the same. [Checked: prior-art pages] [Inferred]

**Weak:**

- **The matcher.** It does no stemming beyond a trailing "s", has hard thresholds that don't work on small ledgers, and has almost no tests. [Checked: section 2 runs]

## 5. Your part vs the agents' part

- **What the repo shows:**
  - There is one squashed commit, authored under your GitHub account and co-authored by Claude. [Checked: `git log`]
  - The LICENSE names you. [Checked: LICENSE]
  - No document says who designed what. [Checked: README.md, LEDGER.md]
- **Traces of an earlier history:**
  - The `import` command moves items from an "older shared ledger" that held several projects. [Checked: README.md "Moving from a shared ledger"; ledger.py `cmd_import`]
  - The code converts an older `<name>-words` label into `owner-words`, and the tests use that older first name and invented project topics. [Checked: ledger.py line 390; test_ledger.py lines 63–99, 206–208]
  - That suggests the "daily use" you judged it from was mostly an *earlier, multi-project version*, and this repo is a rewrite. [Inferred]
- **What can't be told:**
  - Which design ideas were yours. The owner-words protocol and the three-way override question read like the product of someone repeatedly burned by drift. [Unknown]
  - How many iterations there were, or what you rejected. [Unknown]
  - Whether the old version ever caught a real override that mattered. [Unknown]
  - Your brief says agents designed and wrote all the code, tests and docs. Nothing in the repo contradicts that. [Checked: repo] [Inferred]
- **Privacy note:** check whether that older first name is a real person, and whether the test topics mirror a real project. If either is real, rename them before showing the repo. [Unknown]

## 6. How it could be shown

**Option A: one portfolio page with a side-by-side** [Inferred]

- **What it is:** the React example from section 2, shown as "with the ledger" next to "plain CLAUDE.md", plus a screenshot of `ledger.html` using the fictional recipe record.
- **What it needs:**
  - A clean demo record. The fictional one I built is safe; regenerate it on your machine.
  - Screenshots that show no machine paths. The brief and the LEDGER CHECK note embed absolute paths, including your home folder. [Checked: hook output, `tool_cmd`]
  - The honest caveats from section 2.

**Option B: a 60–90 second recording** [Inferred]

- **What it is:** a terminal session where you send "actually let's switch to React" and the assistant stops and quotes you.
- **What it needs:**
  - A fresh user account or a renamed home folder, so paths don't leak.
  - The demo record only, never your real one.
  - The ledger commands allowlisted, so there are no permission prompts. [Checked: permission denials in section 2]

**Option C: a write-up on directing agents** [Inferred]

- **What it is:** "What I learned making agents keep my word", with the tool as the evidence.
- **What it needs:**
  - Real but redacted examples from your own ledger: counts of overrides, superseded decisions, and unconfirmed agent calls caught. Strip all quotes that mention people, clients or credentials.
  - The README wording below.

**Draft README wording (for you to paste; I have not edited README.md):**

> ### How this was made
> I designed the problem, not the code. Claude Code (Anthropic's AI coding assistant) wrote all of the code, tests and documentation in this repository under my direction. I decided what it should do, judged it by using an earlier version every day, and chose the name and licence.
>
> ### Status
> This published version is new. It passes its own test suite and has been run in short automated Claude Code sessions, but it has not yet been used day to day. The override warning matches words and tags, so it misses paraphrases, and it rarely fires until a ledger holds a dozen or more standing items.

(The second paragraph reflects my runs; adjust it if you've since used it for real.) [Checked: section 2] [Inferred: wording]

## 7. What could make it portfolio-worthy

The project as it stands is a competent, small instance of a crowded category. [Inferred] What would make someone stop and look is **evidence**: almost nobody in this space measures anything. claude-brain stands out mainly for its before-and-after counts, and the arXiv paper is cited because it measured. [Checked: those pages] [Inferred] Ideas, each with a rough cost in your time (agents doing the work):

1. **A drift benchmark: ledger vs plain CLAUDE.md vs nothing.** [Inferred]
   - Script 20 rules, run long sessions with forced `/compact`, then send 30 override and paraphrase messages.
   - Count how often the assistant asks first, complies silently or refuses silently.
   - Publish the table, even if the ledger loses.
   - **Cost:** about 1–2 days of directing, plus roughly $20–60 in API usage. The two short runs whose cost I checked came to $0.08 and $0.14; long sessions would cost more. [Checked: cost fields in two of my runs] [Inferred: estimate]
   - This is the single strongest move; it turns "I built a tool" into "I tested a claim".
2. **Score the warning honestly.** [Inferred]
   - Build 50 labelled messages, then report how many real overrides it catches and how many false alarms it raises.
   - Optionally compare against one call to a small, cheap model.
   - **Cost:** half a day.
   - Pairs well with the measurement in idea 1.
3. **Your own usage numbers.** [Inferred]
   - From your real (older) ledger: how many items, overrides, one-time exceptions and unconfirmed agent calls caught, over how many weeks.
   - **Cost:** 1–2 hours, plus careful redaction.
   - This is the only evidence that is uniquely yours.
4. **Reframe the audience.** [Inferred]
   - Pitch it as a governance tool for non-programmers who direct agents ("the owner's words outrank the agent's plans"), rather than as yet another memory tool.
   - That is a less crowded framing, and it matches your actual situation.
   - **Cost:** an hour of rewriting.
5. **A one-page honest comparison table** linking claude-mem, beads, Cline Memory Bank and CLAUDE.md, saying where each is better. [Inferred]
   - **Cost:** 1–2 hours.
   - Reviewers trust people who say where they lose.
6. **Unconventional: publish the ledger *of building the ledger*.** [Inferred]
   - A redacted record of your instructions to the agents while making this tool would show your directing directly, which no code review can.
   - **Cost:** 2–4 hours of redaction. **Risk:** privacy; skip it if in doubt.

With 2 days to 4 November, 3 + 4 + the README wording is realistic. Idea 1 is better scheduled after. [Inferred]

## 8. Meta-analysis of this assignment

- **"Is it novel?" is the wrong main question.** Memory tools for coding agents are a crowded field, and a hiring manager won't expect novelty from a small solo project. The better question is: *does this beat a well-kept CLAUDE.md, and when?* My small runs suggest the gap is narrower than the README implies. [Checked: section 2] [Inferred]
- **"Never run in a real session" was partly wrong by today.** It ran in headless Claude Code sessions here, and its hooks worked. What it lacks is *sustained* use of this version. [Checked: section 2]
- **"Judged it from daily use" is ambiguous.** The evidence points to daily use of an older version. Your strongest material, real examples from that use, is outside the repo and outside what you asked me to look at. [Inferred]
- **The brief doesn't say which job or audience the portfolio targets.** "Show it" lands very differently for a hiring manager in engineering, product, operations, or AI tooling. [Unknown]
- **Treating "agents wrote it" as a disclosure undersells it.** For your portfolio it is the point. The interesting artefact is the specification you held agents to, and that is what ledger encodes. [Inferred]
- **What I'd have asked instead:** "Using a fixed test, does ledger keep an assistant to my rules better than CLAUDE.md alone, and what does my own usage history show it caught?" [Inferred]

## 9. Questions only you can answer

1. What kind of role or reader is the portfolio aimed at? [Unknown]
2. Does the older ledger still exist? How many items, and over how long? Can a redacted excerpt be shown? [Unknown]
3. Can you recall a time the override warning or the brief stopped an assistant from doing something you'd ruled out? What was it? [Unknown]
4. The older first name in the code and tests: is it a real person who should be renamed? [Unknown]
5. Why the rewrite from a shared ledger to one per repository? That decision is a good story if it came from you. [Unknown]
6. Which design ideas were yours? For example, the three-way override question, "my own call, unconfirmed", or "don't silently refuse". [Unknown]
7. Are you willing to publish results if a fair test shows plain CLAUDE.md does about as well? [Unknown]
