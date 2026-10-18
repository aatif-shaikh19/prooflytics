# Security policy for the assignment

## Protected assets
User identity; datasets and raw CSV cells; all private reports; share tokens. Authenticated APIs are owner-only. Public token accesses exactly one report projection and no raw source.

## Security invariants
- Queries join/limit by authenticated owner even when attacker knows UUID.
- Share tokens generated via `secrets`, token digest stored, expiry and revocation checked on each request.
- Browser cookie: HttpOnly, SameSite=Lax, HTTPS Secure in production; CSRF token for mutations; no session tokens in URL.
- CSRF excluded only from intended token-authenticated public GET reading. Token-bearing public GET must not mutate.
- Default no-store for protected and shared responses; Referrer-Policy: no-referrer on shared pages.
- Autoescape all dataset fields and text notes. Chart labels injected via safe JSON serialization, never `innerHTML`.
- Server-enforced 5 MiB maximum (configurable); reject untrusted MIME/encoding/CSV and preserve diagnostics.
- No raw SQL concatenation; validated columns/operators only. Validate top-N upper bound and filter date/category types.
- Avoid token/body/file content in server logs; do not commit `.env`, SQLite DB, generated private data or credentials.

## Negative verification
Tamper IDs, wrong owner block modification, revoke/expiry, unauthorized raw export, arbitrary query parameters, XSS payload `<script>` from CSV, malformed CSV, CSRF-less POST, token in URL logs. Record outcomes of actual tests.
