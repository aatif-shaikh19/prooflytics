# Phase 6: Final risk-focused QA and one optional feature decision

## Paste into Antigravity agent chat (Gemini 3.8 Flash)

You are implementing **only Phase 6** of Prooflytics for ByteVox's Full Stack Intern assignment. Read `AGENTS.md`, `PRD.md`, `architecture.md`, `docs/ACCEPTANCE.md`, `docs/SECURITY.md`, and the prior phase output. Read relevant installed skill instructions, including local `.agents/skills` when appropriate. Maintain actual elapsed time in `docs/BUILD_LOG.md`. Strict 5.5-hour total hard stop. Do not skip tests, do not fabricate output, do not build unrelated features.

## Tasks
Use csv-integrity, secure-sharing, report-provenance and release-audit skills. Run the full test suite, perform security review for IDOR, CSRF, injection, script injection from CSV/notes, oversize inputs, token leaks. Inspect real 375px layout and keyboard focus, empty/loading/error states. Fix P0 issues first. If AND ONLY IF all mandatory acceptance gates pass and meaningful time remains: add **one optional feature**: deterministic suggested charts after upload (based on column types), with tests. No PDF export/comments/change tracking. Record actual findings/failures, commands, screenshots only if they are real, and time in BUILD_LOG.

Exit gate: all mandatory criteria verified; optional feature either functioning with tests or explicitly cut.

## Required reply
Summarize (1) files created/changed; (2) exact commands executed and results; (3) tests added and passing/failing; (4) remaining limitations; (5) actual elapsed time; (6) whether exit gate is met. Do not silently proceed into the next phase.
