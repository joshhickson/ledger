# Handback: what's left for you

Written by an AI agent on 2 November 2026, at the end of the showcase work on branch `portfolio/showcase`. Ordered by
what blocks showing the project soonest.

## What was done on this branch

- `README.md` rewritten: who made it, status, known limits, and a tested "try it in five minutes" section. The rest of
  the old README is kept, and LICENSE is unchanged.
- `showcase/PAGE-DRAFT.md`: the portfolio page draft, with `[JOSH: …]` slots.
- `showcase/demo/`: the sample record script, raw hook output, matcher results, six headless session transcripts,
  seven screenshots, and the scripts that made them. `showcase/demo/README.md` says exactly how each was made.
- Privacy scan of everything new on this branch: no emails, IP addresses, home-folder paths, session IDs, keys or real
  names found. The only paths shown are `/demo/...` and `/usr/local/bin/python3`.
- No public-copy branch, as the project block asked.
- Spending: the six headless Claude Code runs reported about $0.70 in total. The interactive session's cost wasn't
  shown.

## Steps I could not do here

### 1. Make the new README the one visitors see
- **What:** the rewrite exists only on `portfolio/showcase`. Anyone opening the repository sees `main`'s old README,
  which doesn't say agents wrote it or list its limits.
- **Why not done:** you told me not to touch `main` or open PRs. **Needs your decision.**
- **Action:** read `README.md` on the branch, then on GitHub open a pull request from `portfolio/showcase` into `main`
  and merge it. If you want only the README on `main` and not the `showcase/` folder, ask an agent to make a branch
  with just that file.

### 2. Fill the `[JOSH: …]` slots in `PAGE-DRAFT.md`
- **What:** four slots: why you built it, what you decided, your lessons, and which links to show.
- **Why not done:** they must be in your words. **Needs you.**
- **Action:** write a few sentences for each. The page body is about 670 words without the marks and slot text; keep
  your additions short to stay near 800.

### 3. Decide about the older first name in the public code
- **What:** `ledger.py` (the `norm_basis` docstring) and `test_ledger.py` use a short first name from the older
  ledger, as an owner label and in test data. `main` is public, so it's visible now. I haven't repeated the name in
  anything I wrote.
- **Why not done:** only you know if it's a real person; changing it means changing `main`. **Needs your decision.**
- **Action:** if it's real, ask an agent to replace it with a neutral placeholder on a branch, run
  `python3 test_ledger.py`, and merge. The old name stays in `main`'s history unless you rewrite history, which you
  ruled out.

### 4. Put the page on joshuahickson.org
- **What:** copy the page text and the screenshots (`showcase/demo/screenshots/4-reply-react.png` and
  `6-ledger-page.png` are the two the draft uses) into the site.
- **Why not done:** needs another repository or your hosting account.
- **Action:** in the site's repository, an agent can add the page and images. Point it at this branch.

### 5. Branches visible on the public repository
- **What:** the public repo now has `portfolio/showcase` (this work) and `analysis/portfolio-2026-11` (the earlier
  analysis, which discusses what you can and can't claim). This session was also given a branch name,
  `claude/portfolio-showcase-ledger-9w3nfx`. It is not on GitHub, and I did not push to it, because you asked for
  `portfolio/showcase`.
- **Why not done:** deleting branches is an account-level action you didn't authorise. **Needs your decision.**
- **Action:** on GitHub, under Branches, delete any you don't want public. Or locally:
  `git push origin --delete analysis/portfolio-2026-11` if you'd rather keep the analysis off the public repo.

### 6. A short screen recording (optional)
- **What:** a 60–90 second video of the React exchange.
- **Why not done:** possible here with tmux and ffmpeg, but it would show the scripted pauses and permission prompts;
  I chose screenshots instead.
- **Action:** ask an agent to record it from the same demo, or record it yourself with the allowlist from README
  step 7 so there are no prompts. Use a folder whose path doesn't contain your username.

### 7. Test the main claim: long sessions and compaction
- **What:** nothing here tests whether rules survive a long session and `/compact`, which is what the ledger is for.
- **Why not done:** it needs a planned test and a larger API budget (the analysis estimated $20–60). **Needs your
  consent to spend.**
- **Action:** ask an agent to script it: about 20 rules, long sessions with forced `/compact`, then 30 override and
  paraphrase messages, comparing ledger, plain CLAUDE.md and nothing. Publish the table whatever it shows.

### 8. Numbers from your own earlier ledger
- **What:** counts of items, overrides, exceptions and unconfirmed agent calls from the version you used daily.
- **Why not done:** that file isn't in this repo.
- **Action:** give an agent the old database (privately) and ask for counts only, no quotes.

## Where I disagree with, or add to, the analysis

- **"Never run in a real Claude Code session."** You asked the README to say this. It's no longer true: the analysis
  ran it headless, and today I ran it in five headless sessions and one interactive one. So the README says it had
  never run in a real session *until 2 November 2026*, and that it has only had short test sessions since.
  [Checked: `showcase/demo/SESSIONS.md`]
- **The analysis's draft README wording is in your voice** ("I designed the problem…"). Your rules say not to write
  in your voice, so I didn't use it. The README speaks about you in the third person.
- **Hook output isn't visible to you.** The analysis showed the brief and warning reaching the assistant. I'd add that
  Claude Code 2.1.316 doesn't show them on screen, even in the transcript view, so a user sees only the assistant's
  reply. [Checked: interactive session, transcript view]
- **The permission friction has a tested fix.** The analysis flagged refused commands. An allowlist entry in
  `.claude/settings.local.json` removed them in a headless run. That's now README step 7. [Checked: run `allow` in
  SESSIONS.md]
- **Agree** with the core finding: the word-matcher is weak on small records (1 of 7 here), and the brief does most of
  the work. [Checked: `showcase/demo/MATCHER-RESULTS.md`]

## Your decisions, as questions

1. Should the rewritten README go onto `main` now, before 4 November?
2. Is the older first name in `ledger.py` and `test_ledger.py` a real person who should be renamed?
3. Which branches should stay public: `portfolio/showcase`, `analysis/portfolio-2026-11`?
4. Does the README's "until 2 November 2026 … only short test sessions since" wording work for you, instead of
   "never run in a real session"?
5. Which screenshots go on the site: the two in the draft, or others from `showcase/demo/screenshots/`?
6. Do you want the long-session and compaction test run after 4 November, at roughly $20–60?
7. Will you share counts from your earlier ledger, and can a redacted example be shown?
8. Do you want a short video as well as the screenshots?
