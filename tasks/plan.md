# Prooflytics — Implementation Plan

## Overview
Prooflytics is a server-rendered reporting web application built with FastAPI, Jinja2, HTMX, SQLite (SQLAlchemy), and Polars. It emphasizes numeric correctness, provenance transparency ("How was this calculated?"), strict multi-tenant isolation, and secure, revocable report sharing.

## Architectural Decisions & Constraints
- **Python Runtime:** Python 3.11.9 (system installed; fully compatible with modern typing, FastAPI, Polars, SQLAlchemy, Pydantic v2).
- **Architecture:** Monolithic server-side rendered application (FastAPI + Jinja2 + HTMX + minimal Chart.js).
- **Analytics Engine:** Polars for server-side aggregation and exact AST generation. No client-side arithmetic.
- **Data Ingestion:** Python standard `csv` library for audited, non-dropping row preservation; deterministic type inference with explicit quality metrics.
- **Security:** Opaque hashed session tokens in HttpOnly/SameSite=Lax cookies, CSRF protection on mutations, owner-scoped queries on all private endpoints, cryptographic hash lookups for public share links.
- **Sharing:** Live report semantics for MVP; public view exposes serialized block results and provenance, with zero raw dataset exposure.

## Phase Breakdown

### Phase 0: Audit Scope, Skills, and Execution Plan (Budget: 10m)
- Inventory skills and environment.
- Reconcile documentation and constraints.
- Define architecture, file layout, and test plan.
- Update `docs/BUILD_LOG.md`.

### Phase 1: Bootstrap Foundation & Auth (Budget: 35m)
- Define `pyproject.toml` / `requirements.txt` with verified pinned versions.
- Setup SQLAlchemy models (`User`, `Session`, `Dataset`, `DatasetRow`, `Report`, `ReportBlock`, `ShareLink`).
- Implement secure password hashing, opaque session store, and CSRF protection.
- Implement login/logout routes and owner authorization dependency.
- Write database seed script with User A and User B.
- Tests in `tests/test_authz.py`.

### Phase 2: Auditable CSV Ingestion & Profiling (Budget: 50m)
- Bounded file upload (5 MiB limit, streaming byte counter).
- Strict UTF-8 validation (with BOM tolerance).
- Audited CSV parser preserving raw strings, source row indices, and syntax diagnostics.
- Deterministic column type inference (number, date, category, text) with explicit thresholds.
- Profiler generating disjoint counts (accepted, rejected, warnings, per-column nulls).
- Generate 2k–5k row synthetic messy CSV fixture (`fixtures/messy_sample.csv`).
- Ingestion UI with upload and profiling feedback.
- Tests in `tests/test_csv_ingest.py`.

### Phase 3: Exact Backend Calculation Engine & Provenance (Budget: 55m)
- Pydantic models for `AggregationSpec` and `CalculationResult`.
- Polars aggregation engine supporting SUM, AVG, COUNT (`count_non_null` and `count_rows`), MIN, MAX, optional category grouping, and top-N filtering.
- Deterministic disjoint row accounting: `total = structurally_rejected + filtered_out + invalid_for_operation + included`.
- Exact canonical AST serialization and human-readable explanation generation in the same calculation call.
- Tests in `tests/test_metrics.py` and `tests/test_filtering.py` against independent fixtures.

### Phase 4: Report Composer & Responsive UI (Budget: 55m)
- Report management (create, view, update, delete).
- Block management: Metric, Bar Chart, Line Chart, Top-N Table, Text Note.
- Accessible keyboard reordering (Up/Down buttons).
- Global report-level filters (date range, category) applied uniformly to all data blocks.
- Provenance modal ("How was this calculated?") driven by server-rendered HTMX fragments.
- Responsive layout verified at 375px mobile viewport.

### Phase 5: Anonymous Share, Expiration, Revocation (Budget: 45m)
- Cryptographic bearer token generation (`secrets.token_urlsafe(32)`).
- SHA-256 token hashing; store hash, UTC expiry, and revocation timestamp.
- Public read endpoint with per-request token validation, `Cache-Control: no-store`, and `Referrer-Policy: no-referrer`.
- Projection rendering blocks and provenance without exposing raw CSV or editing endpoints.
- Tests in `tests/test_shares.py`.

### Phase 6: Hardening & Optional Feature Decision (Budget: 30m)
- Full automated test suite execution.
- Security review: IDOR, CSRF, CSV script injection autoescaping, size limits.
- Mobile (375px) and keyboard accessibility check.
- Optional feature decision: deterministic suggested charts on upload if time permits, or clean cut.

### Phase 7: Release Audit, Documentation & Demo (Budget: 20m)
- Verify local fresh-clone setup instructions.
- Complete `README.md` with "How my report builder works" (<= 2 pages).
- Record real elapsed time in `docs/BUILD_LOG.md` and genuine AI learning in `docs/AI_USAGE.md`.
- Final rehearsal of 3–4 min demo script (`docs/DEMO.md`) and submission checklist.

## Implementation Risks & Mitigations
| Risk | Severity | Mitigation |
|---|---|---|
| Disjoint row accounting reconciliation drift | High | Implement single shared row-labeling function ensuring exhaustive, mutually exclusive row classification. |
| Timebox overrun (5h target / 5.5h hard stop) | High | Prioritize core P0 functionality and automated tests. Cut optional suggested charts and complex UI transitions immediately if delayed. |
| Client-side calculation leakage | High | Architecture invariant: all aggregation and provenance computed server-side in Polars; client only receives rendered data and strings. |
| Multi-tenant authorization leakage (IDOR) | High | Enforce server-side owner scoping on all database queries; test cross-user access attempts in pytest. |
