# Phase 4: Build complete report composer and responsive frontend

## Paste into Antigravity agent chat (Gemini 3.8 Flash)

You are implementing **only Phase 4** of Prooflytics for ByteVox's Full Stack Intern assignment. Read `AGENTS.md`, `PRD.md`, `architecture.md`, `docs/ACCEPTANCE.md`, `docs/SECURITY.md`, and the prior phase output. Read relevant installed skill instructions, including local `.agents/skills` when appropriate. Maintain actual elapsed time in `docs/BUILD_LOG.md`. Strict 5.5-hour total hard stop. Do not skip tests, do not fabricate output, do not build unrelated features.

## Tasks
Using Jinja2 + HTMX + small scoped vanilla JS + Chart.js, implement owner report list/create/edit/delete, block add/remove/reorder (Up/Down buttons mandatory for keyboard), metric (all required ops with optional group), bar chart, line chart, top-N table and text note. Apply report-level category/date filter to all data blocks. For each metric/chart/table render a How-calculated dialog/panel sourced from backend calculation result including exact spec, included/excluded counts and formula. Validate block/filter configuration server-side; notes and CSV text autoescaped. Provide clear empty/loading/errors, 375px responsive layout, accessible focus/labels. Keep UI polished yet simple; avoid dependency-heavy component library.

Use report-provenance skill. Add report CRUD/filters tests and manual UI checklist. Do not add optional extras.

Exit gate: compose, reorder, filter and reload report successfully; no browser-side authoritative arithmetic; time log.

## Required reply
Summarize (1) files created/changed; (2) exact commands executed and results; (3) tests added and passing/failing; (4) remaining limitations; (5) actual elapsed time; (6) whether exit gate is met. Do not silently proceed into the next phase.
