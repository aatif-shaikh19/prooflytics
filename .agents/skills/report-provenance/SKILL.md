---
name: report-provenance
description: Use when adding aggregations, report filters, chart/table computations or 'How was this calculated?' explanations.
---
# Report provenance skill
1. Define validated canonical aggregation AST: operation, fields, filters, grouping, ordering, limit, null policy.
2. Compute value, included/excluded counts, grouping breakdown, and narrative in ONE server service call.
3. Never claim generated sample SQL was executed; describe actual Polars expression and exact AST.
4. Use a disjoint row-accounting scheme, separately treating parse errors.
5. Test nulls, all-filtered-out, negatives, grouped totals, non-numeric fields, chart point values, top-N ordering.
6. Confirm public and owner views call same analytics service.
