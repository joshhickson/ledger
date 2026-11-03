# Privacy note: what was checked, and how

Checked on 2 November 2026 by the agent that wrote this folder, on branch `portfolio/nov4`. The repository is public,
so this branch is too.

## Files checked

`README.md` (changed), `handoff/PAGE.md`, `handoff/MEDIA.md`, `handoff/LINKS.md`, `HANDBACK-NOV4.md`, and the four
images in `handoff/media/`.

## How

1. **Text search** (`grep`, case-insensitive) of every file above for: email addresses, IP addresses, home-folder
   paths (`/home/`, `/Users/`, `/root`), key and token shapes (`sk-`, `sb_secret`, `eyJ`), the database address
   (`supabase.co`; only the `YOURPROJECT` placeholder appears), pay figures, health words, relatives, the R6 wording
   about coding, and the names R20 keeps off Josh's materials. **Result:** no hits in the new text. The README's
   existing mentions of `~/.ledger/credentials.json` and `token-cloud.txt` are setup instructions naming those files,
   not their contents.
2. **The older first name** the audit flagged (C12): counted, not printed. It appears 0 times in anything this
   session wrote. It's still in `ledger.py` (1), `test_ledger.py` (15) and `test_shared.py` (4), as before.
3. **People:** no one but Josh is named. No relatives. No clients.
4. **The shared-ledger numbers** on the page (86 items, 14 projects; 40 items across 5 projects added 23:41–23:45
   Pacific on 2 November) are counts only, read with SQL `count(*)` from this session's local copy of the record. No project names, item text or quotes from the record were copied anywhere.
5. **Images:** viewed both source screenshots and the resized copies. They show only the made-up recipe project, the
   placeholder owner name "Owner", `/demo/...` paths and Claude Code's version line. Resizing with Pillow drops
   metadata; checked that no EXIF block is present.
6. **Josh's words:** the page quotes only his answer to "Why did you build ledger?", which he gave for the page. No
   messages he typed to agents are quoted (he said "Decide later" on that).
7. **Not opened:** no `.env` or credential file was opened, printed or copied. `~/.ledger/config.json` was not
   opened either.

## Not checked

- The rest of the repository's history and other branches: the audit did that on 2 November.
- Whether the live database matches `supabase/schema.sql`.
