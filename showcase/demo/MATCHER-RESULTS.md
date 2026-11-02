# Override check on the sample record

Run on 2 November 2026 with `python3 tools/ledger/ledger.py match "<message>"` in `/demo/recipe-site`, after
[`make-sample-record.sh`](make-sample-record.sh). The record has 8 standing items (1 goal, 3 rules, 3 decisions, 1
question waiting on the owner).

| Message | Contradicts | Flagged? |
|---|---|---|
| actually let's switch to React for the recipe pages | D1 Plain HTML and CSS, no framework | No |
| I know I said no framework, but let's use React for the search page | D1 | No |
| from now on use cups and ounces in the recipes | R2 Metric units only | **Yes, R2** |
| let's add Google Analytics so we can see which recipes are popular | R1 No tracking or analytics | No |
| add a tracker pixel to the footer | R1 | No (even with `tracker` added to R1's tags) |
| skip the tests for this one, we're in a hurry | R3 Every change ships with a test | No |
| let's move the recipes into WordPress | D2 Each recipe is a Markdown file | No |
| make the hero images bigger on the cards | Nothing; it answers Q1 | Flagged as a possible answer to Q1 (correct) |
| thanks, looks good | Nothing | No (correct) |

**Result:** 1 of 7 contradicting messages flagged; no false alarms.

**Why so few:** a message's score against an item is the sum, over the item's tags that appear in the message, of
log(standing items ÷ items with that tag). With 8 items, one unique tag scores about 2.08. The lowest threshold in
the code is 2.5 (and that one also needs a "change" word such as "actually" or "from now on"). So one matching tag can
never trigger a warning on this record; "cups" plus "ounces" (two tags) did. [`ledger.py`, `match_prompt`]

**What happened in real sessions anyway:** in the test sessions ([SESSIONS.md](SESSIONS.md)), the assistant still
stopped and asked about React and about Google Analytics, because the session-start brief lists every rule and
decision. One run each.
