# Prooflytics agent contract (Antigravity / Gemini)

Read `PRD.md`, `architecture.md`, `docs/ACCEPTANCE.md`, `docs/SECURITY.md`, and current phase prompt before changing code. Source of truth is ByteVox's assignment; when a suggestion conflicts, obey the assignment. **Do not build beyond required scope until all core checks pass.**

## Non-negotiable rules
1. Use Python 3.12+, FastAPI, SQLAlchemy/SQLite, Pydantic, Polars, Jinja2, HTMX, Chart.js, pytest. Pin compatible versions after validating them; do not invent installed dependencies.
2. Keep reporting calculations, filters and provenance server-side, derived in the same service call. NEVER compute an authoritative number in JavaScript.
3. Every private query must enforce owner identity on server. Never assume hidden buttons are security controls.
4. Each public share request revalidates token, expiry and revocation; never expose dataset/source endpoints through share.
5. No silent CSV row drops, coercions or exclusions; preserve original values and report reasons and source row number. If recovery is impossible, clearly reject and explain rather than faking recovered rows.
6. Do not interpolate user input into SQL/HTML/JS. Use ORM parameterization, escaping, Pydantic allowlists, CSRF defenses, secure sessions and bounded uploads.
7. Make UX functional at 375px, accessible by keyboard and clear on empty/loading/error states.
8. Write small composable functions, type hints, docstrings on nonobvious logic and tests for tricky behavior. Explain each nontrivial decision in simple language.
9. Check relevant existing skills in `.agents/skills/`, plus any environment-discovered installed skills, and follow their actual `SKILL.md` instructions. Never claim a skill exists without checking.
10. Run tests and show actual command output before claiming success. No invented screenshots, coverage numbers, benchmark or hours spent.
11. Record genuine AI mistakes and corrections in `docs/AI_USAGE.md`. Do not fabricate a failure for the application.
12. Keep a session log: phase, touched files, verified commands, open risks, minutes spent. Do not advance to next phase if P0 tests fail.
13. Budget strictly 4–5h, hard-stop 5.5h; cut optional chart suggestions and visual flourishes before required behaviors/tests/demo.
14. Do not delete existing user code without explicit reason. Inspect before edit; favor smallest functional diffs.

## Working routine
- Inspect repository and README before implementing.
- Present short plan and confirm relevant skill(s).
- Implement only current phase; add/change associated tests.
- Run targeted pytest + overall tests as practical; inspect test failures instead of hiding them.
- Update `docs/BUILD_LOG.md`, checklist and known limitations.
- Summarize files changed and exact next phase; stop on block.

## Required delivery
Runnable app; synthetic messy CSV with expected-results fixture; tests; setup/env example; README including <=2-page 'How my report builder works', trade-offs, cuts, time and truthful AI usage; 3–4 min recorded demo plan and submission checklist.
