# Media for the ledger page

Josh picked "the two in the draft" (Nov 1–2). His note: "they look organized but bland. They're fine as-is but should
be upgraded in the future." So these are the same two pictures, only resized; nothing was redrawn or retouched.

Each file is 1600 px wide: sharp on high-density screens when shown at up to 800 px wide. Use the `.webp`; the `.png`
is a fallback for anything that can't show WebP. No metadata (EXIF) in any file.

| File | Size | Show it at | Source |
|---|---|---|---|
| `media/ledger-reply-react.webp` (132 KB) / `.png` (486 KB) | 1600 × 1395 | up to 800 px wide | `showcase/demo/screenshots/4-reply-react.png` in this repository (on `main` and this branch; git blob `55c4c81`), 2000 × 1744 |
| `media/ledger-owner-view.webp` (154 KB) / `.png` (571 KB) | 1600 × 2333 | up to 800 px wide | `showcase/demo/screenshots/6-ledger-page.png` (git blob `fb3cfcf`), 2400 × 3500 |

How the sources were made (from `showcase/demo/README.md`): an agent ran Claude Code 2.1.316 on 2 November 2026 on a
**made-up** recipe-website record, in a throwaway cloud container. Picture 1 is a capture of the interactive terminal;
picture 2 is the ledger's own generated web page. Both were photographed with headless Chromium. How they were
resized: Python Pillow, Lanczos resampling, WebP quality 88.

The second picture is tall (about 1.5 screens on a laptop). If the page builder wants it shorter, crop from the
bottom only after the "D4 … Replaces D1" card, so the "what replaced what" part stays in. That's a look choice for
Josh (R5).

## Alt text and captions

**ledger-reply-react**
- Alt: An AI coding assistant, asked to switch to React, stops, quotes the earlier "plain HTML" decision with its
  date, and asks whether to change it for good, make a one-time exception, or keep it.
- Caption: Asked to "switch to React", the agent stops, quotes the earlier decision with its date, and asks before
  changing anything.

**ledger-owner-view**
- Alt: The ledger's web page for a made-up recipe-website project: current focus, open questions, a drift audit, then
  goals, rules and decisions, each with the owner's exact words. A newer React decision is shown replacing the earlier
  plain-HTML one.
- Caption: My view of the record: every rule and decision, whose words they were, and what replaced what.

## Not here yet

- **A video.** Josh said yes, and "I get to direct how the video is made and what it looks like." Not made; what's
  needed from him is in `HANDBACK-NOV4.md`.
