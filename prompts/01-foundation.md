# Phase 1: Bootstrap Python service and owner-secure authentication

## Paste into Antigravity agent chat (Gemini 3.8 Flash)

You are implementing **only Phase 1** of Prooflytics for ByteVox's Full Stack Intern assignment. Read `AGENTS.md`, `PRD.md`, `architecture.md`, `docs/ACCEPTANCE.md`, `docs/SECURITY.md`, and the prior phase output. Read relevant installed skill instructions, including local `.agents/skills` when appropriate. Maintain actual elapsed time in `docs/BUILD_LOG.md`. Strict 5.5-hour total hard stop. Do not skip tests, do not fabricate output, do not build unrelated features.

## Tasks
Implement Python 3.12+ FastAPI + SQLAlchemy SQLite + Pydantic + Jinja2/HTMX skeleton. Create requirements or pyproject with verified compatible pinned dependency versions and concise Windows PowerShell/Linux setup. Create DB tables, documented migrations/schema initialization, two seed users with secure password hashes, login/logout, opaque sessions and CSRF for state-changing authenticated requests. Ensure dataset/report GET endpoints are owner-scoped server-side from the beginning. Add tests using pytest/HTTPX proving login and another user cannot access private records. Do not claim security without tests.

Use secure-sharing skill. Write `README.md` runnable verified commands and `.env.example` placeholders. Keep HTML minimal; no charts yet.

Exit gate: fresh database seed, login/logout works, targeted tests pass, docs/BUILD_LOG updated.

## Required reply
Summarize (1) files created/changed; (2) exact commands executed and results; (3) tests added and passing/failing; (4) remaining limitations; (5) actual elapsed time; (6) whether exit gate is met. Do not silently proceed into the next phase.
