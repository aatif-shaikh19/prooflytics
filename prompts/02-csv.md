# Phase 2: Build auditable CSV ingestion and data profiling

## Paste into Antigravity agent chat (Gemini 3.8 Flash)

You are implementing **only Phase 2** of Prooflytics for ByteVox's Full Stack Intern assignment. Read `AGENTS.md`, `PRD.md`, `architecture.md`, `docs/ACCEPTANCE.md`, `docs/SECURITY.md`, and the prior phase output. Read relevant installed skill instructions, including local `.agents/skills` when appropriate. Maintain actual elapsed time in `docs/BUILD_LOG.md`. Strict 5.5-hour total hard stop. Do not skip tests, do not fabricate output, do not build unrelated features.

## Tasks
Implement bounded upload max 5MiB, strict UTF-8 handling (BOM optional), CSV validation independent of extension, header checks, strict parsing, transparent structural parser errors, original source row number/raw field preservation and typed row conversion. Explicitly diagnose ragged lines, invalid dates, invalid numeric cells, blank cells and odd category values. Infer number/date/category/text conservatively with documented deterministic rules and counts. No silent drops; if unrecoverable bad quoting prevents trustworthy recovery, reject entire file and explain diagnostic. Persist profile and error records associated only with owner. Build profile UI with issues/row details and empty/loading/error states. Generate synthetic 2k–5k row CSV with deterministic expected results and no real personal data.

Use csv-integrity skill. Add ingestion tests incl wrong file, >limit, UTF-8 error, bad quote, quoted comma, blank, ragged.

Exit gate: sample upload works, counts reconcile, actual pytest output, time log.

## Required reply
Summarize (1) files created/changed; (2) exact commands executed and results; (3) tests added and passing/failing; (4) remaining limitations; (5) actual elapsed time; (6) whether exit gate is met. Do not silently proceed into the next phase.
