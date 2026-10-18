---
name: secure-sharing
description: Use when implementing authentication, owner scoping, public report tokens, expiry, revocation, CSRF and adversarial access tests.
---
# Secure sharing skill
1. Map data-access endpoints and require authenticated owner for every private route.
2. Check transitive ownership: block→report→dataset; do not rely on client input.
3. Generate random tokens via secrets; store hash, check expiry and revocation per request.
4. Build separate anonymous projection returning only block output and provenance, not raw dataset/source.
5. Use no-store and no-referrer; no token leakage into logs.
6. Verify CSRF strategy and escaping.
7. Test direct-URL IDOR, tampered nested IDs, expired/revoked token, anonymous writes, raw dataset access, XSS.
