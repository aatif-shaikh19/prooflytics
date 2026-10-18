# Live modification practice

## Drill A: add median
1. Find operator enum and validated block schema.
2. Add median implementation in analytics engine, with explicit empty/null treatment.
3. Ensure provenance AST and narrative names median accurately.
4. Add unit tests including odd/even count, blanks, filters and grouped case.
5. Add UI operator option; rerun tests and demonstrate.

## Drill B: new filter
1. Define validated data type and allowed operator.
2. Integrate filter into one shared filter compiler.
3. Confirm metric/chart/table and provenance use it identically.
4. Test both owner and public sharing.

## Questions to answer
Why does count exclude nulls? Where are row parse problems saved? How can public pages not download CSV? What happens at 100x dataset size? Why is spec the exact executed operation rather than illustrative SQL? Where is authorization enforced? What fails first?
