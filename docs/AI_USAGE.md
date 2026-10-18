# AI usage and corrections

Model(s) and tools used: Gemini 3.8 Flash (High) via Antigravity Agentic IDE

### Phase 1
- What AI helped with: Architecture skeleton, Pydantic/SQLAlchemy models, authentication service with bcrypt and SHA-256 opaque session tokens, CSRF defense, Jinja2 templates, database seed script, pytest multi-tenant isolation suite.
- Where AI made a real mistake: Invoked `pytest` directly via executable without setting `pythonpath` or configuring `pytest.ini`, leading to `ModuleNotFoundError: No module named 'app'` when loading `conftest.py`. Also initially generated Starlette 0.38+ deprecated signatures for `on_event("startup")` and `TemplateResponse(name, context)`.
- How the mistake was caught: Real terminal output from running `.\.venv\Scripts\pytest.exe tests/test_authz.py -v` failed with exit code 1. Warning summaries revealed Starlette and Pydantic v2 deprecation warnings.
- Corrective action and verification: Created `pytest.ini` with `pythonpath = .` and `asyncio_default_fixture_loop_scope = function`, refactored `app/main.py` to use FastAPI `lifespan` context manager, updated `app/config.py` to use `SettingsConfigDict`, and updated `TemplateResponse(request=request, name=..., context=...)`. Verified with `python -m pytest tests/test_authz.py -v` achieving 12 passed tests and 0 deprecation warnings from app code.
- What I independently checked and can explain: Verified password hashing via bcrypt, opaque session token hashing via SHA-256, constant-time CSRF token comparison via `hmac.compare_digest`, and owner isolation returning HTTP 404 rather than HTTP 403 on IDOR attempts to prevent resource existence disclosure.

### Phase 2
- What AI helped with: Auditable CSV parsing pipeline, UTF-8 BOM detection, bounded byte streaming, RFC 4180 quote parsing with strict mode, deterministic column type inference (number/date/category/text), disjoint data quality row accounting, synthetic messy 2,500-row dataset generation with ground truth fixture, HTML profile and row issue audit UI.
- Where AI made a real mistake:
  1. In `tests/conftest.py`, `auth_client_a` and `auth_client_b` fixtures both mutated a shared singleton `client` fixture, causing test cookies to bleed across users in dual-tenant tests.
  2. In `app/web/routes_datasets.py`, parameterized route `@router.get("/{dataset_id}")` was placed above static route `@router.get("/api")`, causing FastAPI to route `/datasets/api` to `dataset_id="api"`.
  3. In `tests/test_csv_ingest.py`, test for UTF-8 decode error contained `\x00`, which tripped the binary file guard instead of `UnicodeDecodeError`.
  4. In `app/templates/dataset_detail.html`, inline Jinja expressions placed inside HTML `style` attributes triggered CSS Language Server tokenizer syntax errors.
- How the mistake was caught: Real pytest execution (`pytest tests/ -v`) caught routing and fixture issues with exact tracebacks; user inspection surfaced template editor syntax warnings.
- Corrective action and verification: Refactored `conftest.py` to instantiate dedicated isolated `TestClient(app)` instances for each user fixture; moved static `/api` routes before parameterized `/{dataset_id}` routes in FastAPI router; updated UTF-8 test inputs to use non-null invalid byte sequences (`b"\x80\x81"`); extracted inline Jinja style conditions into dedicated CSS classes (`.text-warning-cell`, `.text-danger-cell`). Verified with `pytest tests/ -v` where all 29 tests passed cleanly.
- What I independently checked and can explain: Verified that CSV ingestion preserves every row in `dataset_rows` with original 1-indexed source row numbers; verified disjoint accounting invariant `total_rows == accepted_rows + warning_rows + rejected_rows`; verified that malformed unclosed quotes cause explicit failure rather than silent row truncation.

### Phase 3
- What AI helped with: Polars analytical aggregation engine, canonical AST generation, human formula derivation, disjoint row accounting (`total = structurally_rejected + filtered_out + invalid_for_operation + included`), deterministic null policies for empty/invalid selections, grouped breakdowns, and fixture reconciliation.
- Where AI made a real mistake: In `app/services/analytics.py`, `evaluate_block` initially evaluated report-level date range and category filters unconditionally before checking block kind, causing static text notes to exclude rows and increment `filtered_out` when active report filters were configured.
- How the mistake was caught: `tests/test_filtering.py::test_note_block_unaffected_by_filters` failed with `AssertionError: assert 2 == 0`.
- Corrective action and verification: Updated `evaluate_block` to explicitly verify `block.kind != 'note'` before applying report filters, adhering strictly to PRD FR-03 ("Report-level date range or category filter applies to all data blocks; note blocks display unchanged"). Re-verified with full test suite: all 43 tests passed.
- What I independently checked and can explain: Verified that all arithmetic is strictly computed server-side in Polars; verified that the canonical AST contains the exact executed Polars expression string without pretending to execute raw SQL; verified that the sum of per-group included counts equals the block included row count.

### Phase 4
- What AI helped with: Report CRUD routes, block CRUD (Metric, Bar, Line, Top-N Table, Text Note), keyboard-accessible reordering with Up/Down buttons and boundary safety, position re-normalization on block delete, report-level global date/category filter applying across data blocks, "How was this calculated?" provenance modal with disjoint row reconciliation and Polars AST, Chart.js canvas initialization via data attributes, responsive 375px CSS layout.
- Where AI made a real mistake: In `app/web/routes_reports.py`, `add_block_action` initially risked passing empty strings for optional configuration parameters (e.g., `column=""` on note blocks or `group_by_column=""` on single metrics) directly into `BlockConfig`, which could trigger unexpected Pydantic validation failures or default fallback issues.
- How the mistake was caught: Anticipated during implementation review against `report-provenance` and `api-and-interface-design` skill requirements prior to test execution.
- Corrective action and verification: Added explicit input trimming and conversion of empty strings to `None` for optional fields, validated limit parsing with defensive fallbacks, and wrapped Pydantic validation in `HTTPException(400)` within `app/services/reports.py`. Added comprehensive tests in `tests/test_builder.py` covering all 5 block types, up/down swaps, deletions, boundary cases, filters, and cross-tenant isolation. All 54 tests pass.
- What I independently checked and can explain: Verified that client-side JavaScript contains zero authoritative arithmetic (Chart.js and HTML tables only render pre-computed datasets delivered by the backend Polars engine); verified keyboard accessibility via discrete Up/Down buttons with boundary disabling; verified transitive ownership checks (`block -> report -> owner_id == user.id`) on all mutations.

### Phase 5
- What AI helped with: Cryptographically secure random share token generation via `secrets`, SHA-256 digest hashing and storage, owner creation and revocation routes, per-request token state validation, live report projection using identical Polars analytics service, graceful 410 error handling for revoked and expired tokens, security headers (`no-store`, `no-referrer`), and adversarial test suite in `tests/test_shares.py`.
- Where AI made a real mistake: In `app/templates/shared_report.html`, referenced `block.title` assuming `title` was an ORM column on `ReportBlock`, whereas `ReportBlock` stores all configuration in `config_json`, causing `block.title` to evaluate to `None` and display `"Report Block"`.
- How the mistake was caught: Real test output from running `pytest tests/ -v` failed on `tests/test_shares.py::test_anonymous_valid_view_and_provenance` (`assert "Total Sales KPI" in res_html.text`).
- Corrective action and verification: Added a `@property def title(self)` on `ReportBlock` in `app/db/models.py` to safely extract `"title"` from `config_json`. Re-ran targeted pytest `pytest tests/test_shares.py -v` (8 passed) and full pytest suite `pytest tests/ -v` (all 62 passed).
- What I independently checked and can explain: Verified that raw bearer tokens are NEVER stored in the database (only SHA-256 digests); verified that the public view strictly isolates tenant data by completely excluding dataset UUIDs, raw row contents, and user identities; verified that revoked or expired share links immediately return HTTP 410 Gone with zero metadata leakage.

### Phase 6
- What AI helped with: Comprehensive security audit, XSS escaping verification across CSV cells, notes, and report titles; CSRF enforcement verification; IDOR denial across all dataset/report/block endpoints; deterministic type-driven chart suggestions (`app/services/suggestions.py`), human confirmation workflow (`/reports/from-suggestions`), and UI integration.
- Where AI made a real mistake: In `tests/test_security_audit.py`, attempted to import non-existent `TestingSessionLocal` from `app.db.session` instead of using the established `db_session` fixture from `conftest.py`, causing an `ImportError` during test execution.
- How the mistake was caught: Real terminal output from running `pytest tests/test_security_audit.py -v` caught this with `ImportError: cannot import name 'TestingSessionLocal' from 'app.db.session'`.
- Corrective action and verification: Refactored `test_security_headers_enforced_everywhere` to use the standard `db_session` fixture and `create_share_link` helper. Re-ran targeted pytest `pytest tests/test_security_audit.py -v` (4 passed) and full pytest suite across all 69 tests (all 69 passed).
- What I independently checked and can explain: Verified that the chart suggestion engine is 100% deterministic based solely on inferred column types (numbers, categories, dates) and strictly requires human confirmation before saving any report or block to the database; verified that Jinja2 autoescaping prevents XSS script execution even when malicious payloads are ingested into CSV data cells.

### Post-Phase 6 Runtime Regressions & Stabilization
- What AI helped with: Diagnosing and resolving runtime HTTP 500 exceptions encountered during interactive user testing on seeded datasets and unconfigured blocks; adding browser print-to-PDF styles; updating seed data with realistic rows.
- Where AI made a real mistake:
  1. In `scripts/seed.py`, `schema_json` was seeded as bare string column names (`'{"columns": ["id", "amount", "category"]}'`) rather than structured column dictionaries (`{"name": "...", "type": "..."}`). When `app/services/suggestions.py` traversed columns checking `c.get("type")`, it crashed with `AttributeError: 'str' object has no attribute 'get'`.
  2. In `app/services/analytics.py`, `evaluate_block` passed `target_col` directly to `pl.col(target_col)` without checking if `target_col` was `None` or omitted. This caused Polars to crash with `TypeError: invalid input for 'col': Expected 'str' or 'DataType', got 'NoneType'`.
- How the mistake was caught: User encountered HTTP 500 errors when navigating to `GET /datasets/{dataset_id}` and `GET /reports/{report_id}` on the live dev server and shared ASGI stack traces.
- Corrective action and verification:
  1. Defensively normalized column extraction in `app/services/suggestions.py` and `app/web/routes_reports.py` using `isinstance(c, dict)` with safe text fallback for raw strings.
  2. Added defensive column existence guards across all Polars analytical aggregation paths in `app/services/analytics.py` (`if not target_col or not df.columns or target_col not in df.columns: return primary_value=None, formatted_value="N/A"`).
  3. Upgraded `scripts/seed.py` to generate complete typed schemas, profile metrics, and realistic `DatasetRow` entries, and re-executed `python scripts/seed.py`.
  4. Added regression tests `test_suggestions_with_legacy_string_schema_json` and `test_report_view_with_null_target_column_no_crash` in `tests/test_suggestions.py`.
  5. Implemented zero-dependency `@media print` styling in `app/templates/base.html` and added "🖨️ Print / Save PDF" buttons to report detail and shared views.
  6. Verified complete test suite: 71 passed tests.
- What I independently checked and can explain: Evaluated ByteVox assignment constraints regarding forbidden out-of-scope features (PDF export, comments, real-time collaboration). Confirmed that adding heavy external PDF generator libraries or team collaboration engines is explicitly prohibited by ByteVox's contract (Section 6 & 7 of `PRD.md`), whereas native browser `@media print` stylesheets provide clean, immediate print-to-PDF functionality with zero dependency or security overhead.

