# Phase 5: Implement anonymous share, expiration, revocation, and tests

## Paste into Antigravity agent chat (Gemini 3.8 Flash)

You are implementing **only Phase 5** of Prooflytics for ByteVox's Full Stack Intern assignment. Read `AGENTS.md`, `PRD.md`, `architecture.md`, `docs/ACCEPTANCE.md`, `docs/SECURITY.md`, and the prior phase output. Read relevant installed skill instructions, including local `.agents/skills` when appropriate. Maintain actual elapsed time in `docs/BUILD_LOG.md`. Strict 5.5-hour total hard stop. Do not skip tests, do not fabricate output, do not build unrelated features.

## Tasks
Implement owner-only create/revoke of expiring share links, cryptographically random token with hash stored in DB, checks for token state on EVERY anonymous report request, strict read-only public projection and no-store/no-referrer headers. Anonymous view must render report blocks and calculation explanations identically to owner using the SAME analytics service, but NEVER expose raw CSV/source, other reports, owner datasets or edit endpoints. Choose live-report semantics documented in architecture.md. Show graceful revoked/expired errors with no token metadata leaks.

Use secure-sharing skill. Test valid anonymous viewing, revoked & expired denial, guessed user IDs across endpoints, unauthorized block mutation and raw-file/data access. Ensure server-side ownership on every private read as well as write.

Exit gate: adversarial tests green, manual anonymous incognito review, time log.

## Required reply
Summarize (1) files created/changed; (2) exact commands executed and results; (3) tests added and passing/failing; (4) remaining limitations; (5) actual elapsed time; (6) whether exit gate is met. Do not silently proceed into the next phase.
