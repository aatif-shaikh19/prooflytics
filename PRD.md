# Prooflytics — Product Requirements Document

Version: 1.0 | Purpose: ByteVox (Aurigen Labs) Full Stack Intern build assignment | Priority: strict timeboxed MVP

## 1. Product thesis
A user uploads a messy CSV, builds a short report, clicks a number to understand its exact computation, and shares a tightly scoped read-only report link. The product competes on **correctness, provenance, clarity, and server-enforced privacy**, not feature quantity.

## 2. Source and constraints
Based on `ByteVox-FullStack-Intern-Build-Assignment.docx` (provided by applicant). ByteVox specifies 4–5 hours, stopping at 5.5 hours, and explicitly permits AI tooling. Must explain every line submitted. No user files are supplied; create a synthetic messy CSV containing no personal information. A live deployment is optional. **At most one** listed optional feature may be selected.

## 3. Personas and journeys
- **Owner:** signs in → sees only owned datasets/reports → uploads CSV → profiles issues → composes/edit/reorders blocks → filters → inspects calculation → creates/revokes expiring read-only link.
- **Anonymous viewer:** opens link → sees only published report and permitted block output, not source CSV or owner workspace → sees unavailable state after expiration/revocation.
- **Evaluator:** runs locally in a few commands; tests malformed upload, unauthorized reads, calculation lineage, token expiry/revocation, phone width, and asks for a live modification.

## 4. Functional acceptance criteria
### FR-01 Accounts, security
- Sign-in and sign-out; test users available by documented seed command. Store salted password hashes (not plaintext). Secure HttpOnly session cookie, SameSite=Lax, configurable Secure for HTTPS, CSRF protection on state-changing session-authenticated form actions.
- Server must authorize every private dataset/report/block query against session owner, including nested references, update/delete and download paths. Unauthorized resources respond with 404 or 403 consistently and do not leak metadata.

### FR-02 Ingest and profile CSV
- Accept `.csv` with a configurable size limit (MVP default 5 MiB); reject wrong content, invalid UTF-8, oversized uploads and invalid CSV syntax with actionable errors. Do not rely on extension alone.
- Parse on server. Handle delimiters/quotes, headers, missing cells, ragged rows, invalid dates and invalid numeric values. Preserve original row number and raw values for audit; show record-level errors with cause. Never silently drop failed rows.
- Infer columns as number/date/category/text using documented deterministic thresholds, conservative fallback when ambiguous; show row count, count missing per column, types and invalid reasons.
- Define row count convention: physical data records seen (including malformed logical records where identifiable); show accepted, rejected, and warning counts distinctly. Explain where malformed quote sequences prevent reliable recovery.

### FR-03 Report builder
- Owner can create report for owned dataset. Ordered editable list of blocks: metric (SUM/AVG/COUNT/MIN/MAX optionally split by category), bar chart, line chart, top-N rows table, text note. Add/remove/reorder and persist. Chart semantics: bar groups by category; line groups by date bucket or ordered numeric/date x-axis. Validate incompatible columns.
- Report-level date range or category filter applies to **all data blocks**; note blocks display unchanged. Config schema validated server-side. Persist filter state.
- Empty data and all-null aggregations have deterministic behavior (e.g., result null rather than misleading zero for min/max/avg; COUNT documented precisely).

### FR-04 Show your work
- Every metric, chart and table exposes a 'How was this calculated?' panel. Include understandable formula, exact normalized *executed* query/aggregation specification, source column(s), active filters, counts of included and excluded rows and reasons. For grouped results show per-group inclusion counts.
- One backend computation service produces the value **and** provenance in the same response for owner and shared rendering. Do not compute report numbers in JavaScript or independently from explanations.
- Count all rows in a mutually exclusive accounting: structurally invalid, rejected by report filter, invalid/null for requested operation, included. Explicitly distinguish dataset-wide issues from block-specific eligibility.

### FR-05 Sharing
- Generate cryptographically random bearer token; store only hash, expiry (UTC), revoked_at. Public read endpoint validates token/expiry/revocation on **each request**, no cache of authorization decisions.
- Anonymous page can only access serialized **rendered report blocks** and relevant explanations. Raw dataset endpoints and report editor are inaccessible. Table contents are explicitly report content; warn owner that displayed table cells are public.
- Shared view shows report as owner built it. Choose **live report semantics** for MVP: when owner edits report, public view reflects new definition, documented clearly; published link still cannot broaden access outside the bound report. For safer semantics consider snapshot only after core is complete, not in MVP.

### FR-06 UX and hardening
- Explicit loading/empty/error states, responsive layout at 375px, keyboard-accessible inputs/dialogs and visible focus; escape dataset-derived text by default. Server-side validation and parameterized ORM queries; never interpolate raw input into SQL.
- Clear file errors, per-block no-data states and non-revealing public-link unavailable screen.

### FR-07 Automated verification
- pytest tests for SUM/AVG/COUNT/MIN/MAX (including nulls and filters), one invalid-file case, cross-user dataset and report denial, expired and revoked share links. Include tests that public link cannot retrieve private raw dataset or mutate report.
- No phase considered complete if checks fail.

### FR-08 Local run
- README setup with Python version, commands, migration/seed instructions, env examples. Prefer `python -m ...` invocations working on Windows and Linux. Deliver a fresh-clone smoke test.

## 5. Non-functional requirements
- No personal data in sample; performance target smooth interaction for 2,000–5,000 rows and <=5 MiB files. Do not promise large-scale processing.
- Deterministic aggregation and stable rounding/formatting; use Decimal for money-sensitive CSV test cases where possible and document floating-point constraints for Polars aggregation.
- Restrict file size in application and server; control memory and avoid excessive logs of uploaded content.
- Accessibility: labels, semantic controls, focus management, readable contrast, keyboard reorder alternative (Up/Down buttons if drag-and-drop is not accessible).

## 6. Suggested optional enhancement — ONLY ONE
If and only if P0 passes within time limit: *suggested charts on upload* based on types, with a human confirmation button. Do not implement PDF export, comments, or changed-view in assessment build.

## 7. Out of scope
LLM-generated insights, Kafka, Redis, cloud object storage, teams, multi-dataset joins, raw SQL editor, billing, real-time collaboration, complete BI suite, PDF/image export, comments, arbitrary custom transforms.

## 8. Prioritized delivery / cut plan
P0 all assignment requirements, security tests, README and video. P1 polished styling and keyboard UX (functional accessibility remains P0). P2 the single optional chart suggestion. At 5.5 hours STOP. Record what is cut, remaining risks and actual elapsed time; do not invent timing.

## 9. Evaluation rubric (internal)
- 30% reproducible numeric correctness and traceability
- 25% access control and sharing safety
- 15% honest CSV ingestion/data-quality visibility
- 15% functional UX and responsive accessibility
- 15% tests, README, demo and live-change readiness
These are our internal priorities, **not** ByteVox-published scoring weights.

## 10. Definition of done
All eight functional requirement groups demonstrated locally, automated minimum tests pass, no unapproved optional work, clean README including <=2-page 'How my report builder works', demo video checklist completed, truthful cut list, tracked time and genuine AI error/correction.
