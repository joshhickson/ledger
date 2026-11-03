# Links for the ledger page

| Link text | URL | Works today? |
|---|---|---|
| The code and README | https://github.com/joshhickson/ledger | Yes. Today it shows `main`'s README, the per-repository version. After Josh says yes to the new README and it moves to `main`, the same link shows the shared-ledger version this page describes. |
| How the screenshots and test sessions were made | https://github.com/joshhickson/ledger/tree/main/showcase/demo | Yes: `showcase/demo/` is on `main` already. |

## Don't link (yet)

- **Branch links** (`portfolio/nov4`, `supabase-shared`, `audit/2026-11`, `analysis/portfolio-2026-11`,
  `portfolio/showcase`): they're working branches. Link to `main` only, so the page doesn't break when branches are
  tidied.
- **`raw.githubusercontent.com/.../main/ledger.py`** (the README's cloud setup script uses it): it only has the
  shared-ledger code once this branch's README and code are on `main`.
- **Anything on Supabase.** The database address stays out of every page and repository.

## Order of steps that affects the links

1. Josh reads the final README on `portfolio/nov4` and says yes or asks for changes.
2. Then `supabase-shared` plus this branch's README fixes go onto `main` (a separate step, after his yes).
3. Only after step 2 does the page's "Where it is now" section match what visitors see at the first link. If the page
   goes up before step 2, either wait, or add one line under the link: "The shared version is on the
   `supabase-shared` branch until it's merged."
