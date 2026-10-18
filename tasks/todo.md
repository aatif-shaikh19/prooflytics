# Prooflytics — Task Checklist

## Phase 0: Audit Scope, Skills, and Execution Plan
- [x] Read `AGENTS.md`, `PRD.md`, `architecture.md`, `docs/ACCEPTANCE.md`, `docs/SECURITY.md`
- [x] Inspect actually installed global and workspace skills
- [x] Verify environment tools (Python 3.11.9, pip 26.1.1, git 2.49.0)
- [x] Reconcile document requirements and identify constraints
- [x] Define task breakdown, file structure, and test plan
- [x] Update `docs/BUILD_LOG.md` with real Phase 0 timing

## Phase 1: Bootstrap Foundation & Auth
- [x] Create `pyproject.toml` / `requirements.txt` with verified pinned versions
- [x] Configure SQLite database and SQLAlchemy models
- [x] Implement password hashing and opaque session store
- [x] Implement CSRF token defense
- [x] Create seed script with User A and User B
- [x] Implement login/logout routes
- [x] Write `tests/test_authz.py` verifying multi-tenant isolation

## Phase 2: Auditable CSV Ingestion & Profiling
- [x] Implement bounded upload handler (5 MiB cap)
- [x] Implement strict UTF-8 parser and quote syntax validator
- [x] Preserve original row numbers and raw values (no silent drops)
- [x] Implement conservative type inference (number, date, category, text)
- [x] Implement profiler with disjoint row accounting
- [x] Generate synthetic messy CSV fixture (2k–5k rows)
- [x] Build upload and profile UI
- [x] Write `tests/test_csv_ingest.py`

## Phase 3: Exact Backend Calculation Engine & Provenance
- [x] Define `AggregationSpec` and `CalculationResult` Pydantic schemas
- [x] Implement Polars aggregation (SUM, AVG, COUNT, MIN, MAX, grouping)
- [x] Implement disjoint row accounting in calculation engine
- [x] Build exact canonical AST and human-readable explanation generator
- [x] Write `tests/test_metrics.py` and `tests/test_filtering.py`

## Phase 4: Report Composer & Responsive UI
- [x] Implement report CRUD endpoints and views
- [x] Implement block CRUD (Metric, Bar, Line, Top-N, Note)
- [x] Add accessible keyboard reordering (Up/Down buttons)
- [x] Implement global report filters applying to all data blocks
- [x] Implement "How was this calculated?" provenance modal
- [x] Verify 375px mobile responsive layout and keyboard focus

## Phase 5: Anonymous Share, Expiration, Revocation
- [x] Implement bearer token generator and SHA-256 digest store
- [x] Implement public report read endpoint with per-request token check
- [x] Restrict public view to serialized report blocks (no raw CSV access)
- [x] Add `Cache-Control: no-store` and `Referrer-Policy: no-referrer`
- [x] Implement token revocation and expiration handling
- [x] Write `tests/test_shares.py`

## Phase 6: Hardening & Optional Feature Decision
- [x] Run complete automated test suite
- [x] Perform security review (IDOR, CSRF, CSV XSS, size limits)
- [x] Check mobile (375px) and keyboard accessibility
- [x] Decide on optional suggested charts feature based on remaining time (IMPLEMENTED: deterministic type-driven chart suggestions with human confirmation)

## Phase 7: Release Audit, Documentation & Demo
- [ ] Verify fresh setup commands on Windows and Linux
- [ ] Write <=2-page "How my report builder works" in `README.md`
- [ ] Document trade-offs, scale limits (100x), and cuts
- [ ] Record truthful AI mistakes and lessons in `docs/AI_USAGE.md`
- [ ] Complete demo narration script (`docs/DEMO.md`)
- [ ] Final exit verification
