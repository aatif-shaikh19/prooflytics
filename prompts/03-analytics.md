# Phase 3: Implement exact backend calculation engine and provenance

## Paste into Antigravity agent chat (Gemini 3.8 Flash)

You are implementing **only Phase 3** of Prooflytics for ByteVox's Full Stack Intern assignment. Read `AGENTS.md`, `PRD.md`, `architecture.md`, `docs/ACCEPTANCE.md`, `docs/SECURITY.md`, and the prior phase output. Read relevant installed skill instructions, including local `.agents/skills` when appropriate. Maintain actual elapsed time in `docs/BUILD_LOG.md`. Strict 5.5-hour total hard stop. Do not skip tests, do not fabricate output, do not build unrelated features.

## Tasks
Create validated `AggregationSpec` and `CalculationResult`: operation, selected column, optional category split, optional date/category report-level filter, sort/top-N. Implement sum/average/count/min/max, group by category, bar/line data shape, top rows, null handling. For count of column count non-null valid values; explicitly document. Track disjoint excluded reasons and included counts per block; same result object contains exact canonical AST of executed computation, textual explanation, row counts and output. Do not fabricate raw SQL if operations are executed in Polars. Serialize results deterministically, handle empty/all-invalid cases. Keep JavaScript free of calculations.

Use report-provenance skill. Tests for known fixture results, negative values, nulls, filters, grouping and counts invariants.

Exit gate: all tests pass and calculated values match independent fixture; update log.

## Required reply
Summarize (1) files created/changed; (2) exact commands executed and results; (3) tests added and passing/failing; (4) remaining limitations; (5) actual elapsed time; (6) whether exit gate is met. Do not silently proceed into the next phase.
