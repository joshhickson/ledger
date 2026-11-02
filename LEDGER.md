# Project ledger: how sessions use it

This repository keeps its owner's instructions, decisions and rules in a ledger at `.ledger/`. The record is
`.ledger/ledger.jsonl`, committed with the code. The owner is named in `.ledger/config.json` and in the brief.

Hooks inject the brief ("Ledger brief a/b") at session start and after compaction, check each of the owner's messages
for overrides, and save a handoff before compaction. The brief shows the exact command to run the tool on this
machine. If you can't see a brief, see the note in CLAUDE.md under "Project ledger".

- **Focus:** work on the current focus shown in the brief.
  - Side requests from the owner are fine: say they're side requests, record them, and return to the focus.
  - Your own ideas become `proposed` tasks, not work.
  - With no focus set, don't start a new work stream; put the waiting questions to the owner.
- **Before** offering options, planning or starting a stage, writing a handoff or preparing for compaction:
  - run `check <topic words>`;
  - resolve any conflict it shows, or ask the owner.
- **Recording:** when the owner gives an instruction, decision or answer, record it at once and verbatim with `add`.
  - Use `--quote` and `--source`, plus `--basis owner-words`, or `owner-overrode` / `owner-picked-rec` when they chose
    between your options.
  - Tag it with the everyday words they'd use to change it later.
  - Your own calls get `--basis my-call`.
  - `--project` is optional: items go to `main` by default, and `all` marks items that apply everywhere.
- **Overrides:** a "LEDGER CHECK" note appears when the owner's message touches a standing rule, goal or decision. If
  the message changes one:
  - name the item and quote their earlier words with the date;
  - before acting, ask whether it's a change for good, a one-time exception, or a keep. Only when their message
    itself refers to the earlier rule ("I know I said X, but...") may you confirm in one line and go ahead; "from now
    on" alone doesn't show they remember it;
  - record it: `override <ID> "<new version>" --quote "<their words>"`, adding `--once` for an exception;
  - review the dependants it lists.

  Never follow such a change silently, and never refuse it silently: the owner is in charge, and the point is that
  both of you see it.
- **Closing:** close items as they finish (`set ID status=done`). Handoffs start from `handoff`.
- **The owner's view:** the owner reads `.ledger/ledger.html`. They don't edit the ledger; they tell you.
- **Shared ledger:** if the brief says "the shared ledger (Supabase)", one record serves all of the owner's sessions,
  on every machine and in the cloud. Items you add go to this session's project (the repository's name, shown in the
  brief); `--project all` is for things that apply everywhere. Other sessions may be writing at the same time: if the
  tool says a new item's ID was taken and renumbers it, use the new ID. If the brief shows a "SHARED LEDGER
  PROBLEM", keep working from the copy shown, and tell the owner. There is no `ledger.jsonl` to commit.
- **Git:** `.ledger/ledger.jsonl` changes with every write. Commit it along with the work it describes. If a merge
  leaves conflict markers in it, the brief says so: remove the markers, keeping both sides' lines (the tool sorts out
  duplicates), and run `brief`.
