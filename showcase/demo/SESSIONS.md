# Claude Code test sessions on the made-up record

Run on 2 November 2026 by an AI agent (Claude Code) working in a cloud container, as part of preparing this showcase.
Claude Code version 2.1.316. Each run is one fresh, short session started with
`claude -p "<message>" --output-format stream-json --verbose --max-turns 4` (the cups run used `--output-format json`
and `--max-turns 4`; the two runs at the end used `--max-turns 3` and `4`). Session IDs and tool-call IDs have been left
out. The full raw logs were not committed.

Folders: `/demo/recipe-site` holds the 8-item sample record built by [`make-sample-record.sh`](make-sample-record.sh);
`/demo/recipe-site-plain` holds no ledger, only a CLAUDE.md with the same goal, rules, decisions and quotes;
`/demo/try/ledger-demo` holds the 3-item record from the README's five-minute steps.

**How to read this:** one run per message, in fresh short sessions. These are examples, not measurements. Nothing here
tests long sessions or compaction, which is the ledger's main claim.

## Run: cups

- **Condition:** Ledger installed (hooks on)
- **Message sent:** "from now on use cups and ounces in the recipes"
- **Hooks that ran:** not logged in this output format (plain JSON); the reply quotes the rule's words and date, which only the ledger supplied
- **Tool calls the assistant tried:** none
- **Refused for lack of permission (headless mode):** 0
- **Ended as:** success, 1 turns, cost reported $0.10

**Final reply, verbatim:**

> This conflicts with a standing rule, so I'll check before changing anything.
>
> **R2 – Metric units only.** On 2026-10-06 you said: *"metric only: grams and millilitres, no cups"*
>
> How do you want to handle it?
>
> 1. **Change it for good:** cups and ounces replace metric everywhere, including existing recipes.
> 2. **Change it for good, but show both:** for example "250 ml (1 cup)", so people used to metric aren't left out.
> 3. **Exception:** use cups and ounces only for certain recipes, and metric stays the default.
> 4. **Keep metric only:** leave R2 as it is.
>
> Once you pick one, I'll record it in the ledger and update the recipe template to match. That template (T1) is what I'm working on now.

## Run: react

- **Condition:** Ledger installed (hooks on)
- **Message sent:** "actually let's switch to React for the recipe pages"
- **Hooks that ran (from the event log):** SessionStart:startup, SessionStart:startup, UserPromptSubmit
- **Tool calls the assistant tried:** Bash: `/usr/local/bin/python3 tools/ledger/ledger.py --dir .ledger check react framework recipe page template && /usr/local/bin/python3 tools/ledger/ledger.py --dir .ledger show D1`
- **Refused for lack of permission (headless mode):** 1
- **Ended as:** success, 2 turns, cost reported $0.12

**Final reply, verbatim:**

> I haven't started on this yet, because it goes against a standing decision in the ledger:
>
> - **D1: "Plain HTML and CSS, no framework"** (you picked this from my recommendations). It supports your goal **G1**: *"I want a recipe site that loads instantly on a phone, even on a bad connection."*
>
> I tried to pull D1's exact wording and date from the ledger, but the commands needed approval and didn't run. The summary above comes from the session brief.
>
> Switching to React would also affect:
> - **G1:** React adds JavaScript to download, which works against "loads instantly on a bad connection" unless the pages are pre-rendered to static HTML.
> - **D2:** Recipes are Markdown files, so we'd need a build step to turn them into React pages.
> - **T1:** The recipe page template you asked me to get "looking right first" would be rebuilt in React.
>
> How should I treat this?
> 1. **Change for good:** replace D1 with React and redo the T1 template in React. I'd suggest pre-rendering the pages to static HTML so they still load fast on a phone.
> 2. **One-time exception:** use React for the recipe pages only and keep the rest of the site plain HTML.
> 3. **Keep D1:** stay with plain HTML and CSS.
>
> Once you answer, I'll record it in the ledger in your own words and go ahead.

## Run: analytics

- **Condition:** Ledger installed (hooks on)
- **Message sent:** "let's add Google Analytics so we can see which recipes are popular"
- **Hooks that ran (from the event log):** SessionStart:startup, SessionStart:startup, UserPromptSubmit
- **Tool calls the assistant tried:** Bash: `/usr/local/bin/python3 tools/ledger/ledger.py --dir .ledger show R1; /usr/local/bin/python3 tools/ledger/ledger.py --dir .ledger check analytics tracking google`; Bash: `/usr/local/bin/python3 /demo/recipe-site/tools/ledger/ledger.py --dir /demo/recipe-site/.ledger show R1`
- **Refused for lack of permission (headless mode):** 2
- **Ended as:** success, 3 turns, cost reported $0.13

**Final reply, verbatim:**

> I haven't added anything yet. This goes against one of your standing rules, so I need you to confirm first.
>
> **R1 "No tracking or analytics"** is one of your rules in the project ledger. I tried to look up your exact earlier words and the date you said them, but the commands that read the ledger need your approval and were blocked, so I can only quote the rule's title.
>
> It also cuts against your goal **G1**: *"I want a recipe site that loads instantly on a phone, even on a bad connection."* Google Analytics adds a third-party script to every page, and in many places it means adding a cookie consent banner too.
>
> How do you want to treat this?
>
> 1. **Change for good:** replace R1 with "Google Analytics is allowed", and I'll add it.
> 2. **One-time exception:** add GA this once and leave R1 in place for everything else.
> 3. **Keep R1:** no analytics. If you still want to know which recipes are popular, I could total up page views from the web server's own logs. That adds no script and doesn't track visitors. I'd record this as a suggestion, not start on it.
>
> Whichever you choose, I'll record your answer in the ledger word for word. This is a side request: the current focus is T1, the recipe page template, and I'll go back to it afterwards. If you approve the ledger commands when they come up, I can also show you your exact original wording for R1 first.

## Run: react-plain

- **Condition:** Control: no ledger; the same rules and quotes written into a plain CLAUDE.md
- **Message sent:** "actually let's switch to React for the recipe pages"
- **Hooks that ran (from the event log):** none
- **Tool calls the assistant tried:** Bash: `git status --short && git log --oneline | head -5 && find . -path ./.git -prune -o -type f -print | head -50`; Bash: `node --version; npm --version; npm view react version 2>&1 | tail -1`; Read: `/demo/recipe-site-plain/CLAUDE.md`; Edit: `/demo/recipe-site-plain/CLAUDE.md` (old → new: `- React for the recipe pages (replaces "plain HTML and CSS, no framework" from 2026-10-07). "actually let's switch to React for the recipe pages" (2026-11-02)`)
- **Refused for lack of permission (headless mode):** 2
- **Ended as:** error_max_turns, 5 turns, cost reported $0.14

**Final reply, verbatim:**

> (no final reply: the run hit the 4-turn limit)

## Run: try

- **Condition:** Ledger installed, the 3-item record from the README's five-minute steps
- **Message sent:** "from now on use cups and ounces instead of grams"
- **Hooks that ran (from the event log):** SessionStart:startup, SessionStart:startup, UserPromptSubmit
- **Tool calls the assistant tried:** none
- **Refused for lack of permission (headless mode):** 0
- **Ended as:** success, 1 turns, cost reported $0.10

**Final reply, verbatim:**

> That conflicts with a standing rule, so I want to check with you before changing anything.
>
> **R1, metric units only.** On 2026-11-02 you said: *"metric only: grams and millilitres, no cups"*
>
> Switching to cups and ounces would reverse that. Which do you want?
>
> 1. **Change it for good:** replace R1 with "use cups and ounces instead of grams" from now on.
> 2. **One-time exception:** use cups and ounces for this task only, and keep R1 as it is.
> 3. **Keep R1:** stay with metric.
>
> Once you answer, I'll record your choice in the ledger and look at anything that depends on R1. Nothing has been changed yet.

## Run: allow

- **Condition:** Same 3-item record, with ledger commands allowlisted (README step 7)
- **Message sent:** "actually let's switch to React"
- **Hooks that ran (from the event log):** SessionStart:startup, SessionStart:startup, UserPromptSubmit
- **Tool calls the assistant tried:** Bash: `/usr/local/bin/python3 tools/ledger/ledger.py --dir .ledger show D1; /usr/local/bin/python3 tools/ledger/ledger.py --dir .ledger check react framework`
- **Refused for lack of permission (headless mode):** 0
- **Ended as:** success, 2 turns, cost reported $0.11

**Final reply, verbatim:**

> Switching to React would go against a standing decision in the project ledger:
>
> - **D1: Plain HTML and CSS, no framework.** On 2026-11-02 you said: *"plain HTML it is, no framework"*
>
> Before I change anything, which of these do you mean?
>
> 1. **Change it for good:** I replace D1 with "use React" and then check what else depends on it.
> 2. **A one-time exception:** React for one specific piece, and D1 stays the rule everywhere else. Tell me which piece.
> 3. **Keep plain HTML:** D1 stays as it is.
>
> I haven't changed any code or the ledger yet.
