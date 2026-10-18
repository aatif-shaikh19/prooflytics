# Acceptance and test plan

## P0 demonstrations
- User A and User B sign in independently; A cannot list/open/edit B's dataset, report or blocks, even by direct HTTP request.
- Upload a valid 2k–5k row messy CSV: profile shows types, blank counts, row issues and totals that reconcile; bad date and numeric examples are visible; malformed/oversize/non-UTF8/non-CSV each display suitable error.
- Build report with metric sum/avg/count/min/max optionally grouped, bar, line, top-N and note. Add, delete, reorder; filter by category/date range, persist, reload.
- Open provenance for one metric, one chart data point and one table: expression/spec matches actual operation and counts reconcile.
- Share anonymously via expiring token; verify not signed in; attempt raw dataset endpoint, blocked; revoke then refresh public link, blocked; expired link blocked.
- Check 375px wide and keyboard-only navigation, empty and error states.
- Run fresh-clone startup instructions and tests; demonstrate 3–4 min scenario.

## Required pytest outline
- `test_metrics.py`: known SUM/AVG/MIN/MAX/COUNT, grouped results, empty selections, missing and invalid values, negative number.
- `test_filtering.py`: global category/date filters affect all relevant blocks and provenance, count invariant.
- `test_csv_ingest.py`: invalid UTF-8, ragged row, bad date, malformed quote, file size.
- `test_authz.py`: A's guessed IDs rejected by B endpoints; nested report/dataset mismatch rejected.
- `test_shares.py`: anonymous valid read, expired and revoked denied, write denied, raw data denied, accidental content leakage denied.

## Count invariant
For each block, `total_rows = structurally_rejected + filtered_out + invalid_for_operation + included` using disjoint partitions; raw CSV parse errors outside recoverable rows are separately stated. Group per-value inclusions reconcile with included count except where multiple grouped points intentionally overlap (such overlap prohibited for this MVP).

## Final gates
No failures, no invented evidence, local startup verified, limitation list honest, README/how-it-works <=2 pages, demo script complete, one listed optional maximum, elapsed time truthfully reported.
