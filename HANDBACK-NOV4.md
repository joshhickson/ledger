# Handback, 2 November 2026 (late evening): ledger, for the Nov 4 portfolio

Written by an AI agent (Claude Code) on branch `portfolio/nov4`, made from `supabase-shared` (`f6e0be8`), which the
audit (`AUDIT-2026-11.md` on `audit/2026-11`) names as the newest work. Nothing was published, merged, posted or
sent. `main` is unchanged.

## Waiting on you, most important first

1. **Read the final README and say yes or ask for changes.** It's `README.md` on this branch. Only the top part
   changed: "How this was made", "Status", two lines in "Known limits" and step 6. After your yes, moving it to `main`
   is a separate step. What should move: `supabase-shared` plus this branch's README commit, *not* `handoff/` or
   this file (they're notes for the site session, and would clutter the public repo). It's a fast-forward, no merge
   conflicts. Until it moves, the README's cloud setup script points at `main`, which doesn't have the shared-ledger
   code yet (audit C5); moving it fixes that.
2. **Q1. Lessons, in your own words.** One question: *What did building ledger teach you about directing AI
   agents?* A few sentences is plenty. The page has a marked slot for it; the site session will leave the section
   out until you answer.
3. **Q2. Rough cost.** You said yes to rough numbers. *About how much money and how many hours did ledger take,
   across all its versions?* The only figure in the repository is about $0.70 of API use for six short test
   sessions. The page leaves this out until you answer.
4. **The video.** You said yes, and "I get to direct how the video is made and what it looks like." Not made. What
   I'd need from you:
   - **What it should show:** the made-up recipe project's "switch to React" exchange (safe, already in the
     screenshots), or your real shared ledger (more honest about real use, but it shows your real words and
     project names, so it would need a privacy pass and your yes on every frame).
   - **Length and shape:** for example 30, 60 or 90 seconds; wide (16:9) for the page or tall for a phone.
   - **Sound:** silent with captions, your voice-over, or music.
   - **Who records it:** an agent in a cloud container (terminal recording; can hide the permission prompts with the
     README's step 7), or you on your own machine with a screen recorder. If it's your machine, use a folder whose
     path doesn't show your username.
   - **Look:** terminal colours and font, whether to show the ledger's web page too, title card or none (R5: your
     call).
   - **Where it lives:** a file on your site, or a video host (posting it is your step, not an agent's).
   - **When:** before Nov 4, or after.
5. **The older first name in the code** (audit C12; not repeated here). Still open: is it a real person? It appears
   in `ledger.py` once, `test_ledger.py` 15 times, `test_shared.py` 4 times. If yes, an agent can replace it with a
   placeholder and re-run both test files.
6. **Confirm one quote is fine on the page.** The page quotes your answer to "Why did you build ledger?". You gave it
   for the page, so I've used it. Your broader "may things I typed to agents be quoted" answer is still "Decide
   later", so nothing else of yours is quoted.
7. **Decide-later items, unchanged:** deleting `supabase-shared-e2e`; keeping `analysis/portfolio-2026-11` public; the
   fair long-session test after Nov 4. The page doesn't promise the test.
8. **Branch tidy-up (when you like):** this session's container also came with a branch named
   `claude/portfolio-nov4-9979pk` on GitHub. It's the same commit as `supabase-shared`, with no work of its own. I
   didn't push to it, because you asked for `portfolio/nov4`. You can delete it.

## What I did

- **README fixes** (all five audit slips, plus your note):
  - History wording (C3): the "one squashed commit" sentence is gone. Per your answer, it now just says agents wrote
    it "under the direction of Joshua Hickson" and leaves it there.
  - Real use (C10, your "Change it"): a new first Status line says the shared ledger is the record your sessions use
    to update your whole portfolio, with several sessions running at once, with tonight's counts, and that it's days of
    use, not months. The old "until 2 November … never ran" line is gone. The per-repository version is still
    described as having no day-to-day use, which is true.
  - Windows (C4): "Not tested" now says *the per-repository version* on Windows, since the shared ledger ran there.
  - Test counts (C6): 55 and 44, re-run tonight. The live-database test (10 checks) is now described as passing on an
    earlier commit, with the three later changes tested offline only (C7).
  - Step 6 (C11): now says what to expect and that the test runs were one headless run on this 3-item record and one
    interactive run on a larger record. Two runs, not a guarantee.
  - "Tried once each" (shared ledger limits) updated: tested once each, then used, and says honestly that in this
    session the brief came from a CLAUDE.md instruction, not the hooks, so the per-message check wasn't running.
- **`handoff/`** for the session that builds your site:
  - `PAGE.md`: the page text, first person, your "why" in your exact words, the shared-ledger story, and **both**
    plain-CLAUDE.md control runs (they disagreed; the page says so). Two marked questions (Q1, Q2 above) with an
    instruction to leave them out until you answer. Nothing else is a blank slot.
  - `media/`: the two screenshots you picked, resized to 1600 px wide, WebP plus PNG fallback, with alt text.
    `MEDIA.md` names each source file.
  - `LINKS.md`: two links, both to `main`, both working today, and what not to link.
  - `PRIVACY.md`: what I searched for and how.
- **Shared ledger:** recorded your answers for this project word for word: D33 (supabase-shared to main after you
  see the README), D34 (README wording, your "concurrent sessions" note), D35 (the two screenshots, your note), D36
  (video, you direct it), plus T5 (your README review) and Q6 (lessons and cost).

## What I checked

- Read in full: the audit, the earlier page draft and handback (`portfolio/showcase`), the analysis's control-run
  section, `showcase/demo/SESSIONS.md` and the current README.
- Ran `test_ledger.py` (55 of 55 pass) and `test_shared.py` (44 of 44 pass), Python 3.13. Didn't run
  `test_shared_live.py` (it calls the real database).
- **Your "concurrent sessions" note:** checked against this session's local copy of the shared record. When this
  session started (23:41 Pacific) it held 46 items; by 23:45 it held 86, across 14 projects. Other sessions added 40
  items across 5 projects in those four minutes. Counts only; no item text copied. That shows several projects being
  updated at once; it doesn't prove how many separate sessions did it, though 5 projects in 4 minutes points that way.
- **The R6 line on `portfolio/showcase` (audit C1) is already fixed:** a commit made after the audit (`1447957`,
  22:13) removed it from that branch's README and page draft. It's still in that branch's history.
- **The plain-CLAUDE.md control runs:** both are on 2 November, one run each. In the analysis run the assistant
  flagged the decision, asked, and gave a React plan in the same reply. In the showcase run it tried to rewrite the
  decision in CLAUDE.md without asking and hit its turn limit. The transcript doesn't say whether that edit went
  through (two of its commands were refused), so the page says "started rewriting".
- Privacy: see `handoff/PRIVACY.md`. Nothing found in the new text. No `.env` or credential file opened.

## Where I disagree with, or add to, the audit

- The audit's C1 is no longer open (fixed in `1447957`, see above).
- Real use is stronger than the audit could show: it saw one session's brief; tonight's counts show many items
  arriving across projects in minutes.
- One new limit worth knowing, now in the README: in this cloud session the brief came from your global CLAUDE.md
  instruction, and the hooks weren't installed. So the per-message override warning, one of ledger's two main
  features, isn't what's doing the work in your portfolio sessions; the brief and the `check` command are.
