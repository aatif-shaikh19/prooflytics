"""
Rate Limiting Middleware for Prooflytics.

Protects against:
- Brute-force credential stuffing on /login
- Denial of Service (DoS) and disk-exhaustion attacks on file uploads
- Automated scrapers on sensitive endpoints
"""
import time
import threading
from typing import Dict, List, Tuple
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.services.audit import log_security_event

class RateLimiter:
    def __init__(self):
        self._lock = threading.Lock()
        # Map: (ip, route_prefix) -> list of timestamp floats
        self._requests: Dict[Tuple[str, str], List[float]] = {}

    def is_allowed(self, ip: str, route_prefix: str, max_requests: int, window_seconds: int) -> Tuple[bool, int, int]:
        """
        Check if request is within sliding window rate limit.
        Returns: (allowed: bool, remaining: int, retry_after: int)
        """
        now = time.time()
        window_start = now - window_seconds
        key = (ip, route_prefix)

        with self._lock:
            timestamps = self._requests.get(key, [])
            # Filter timestamps within current window
            valid_timestamps = [t for t in timestamps if t > window_start]

            if len(valid_timestamps) >= max_requests:
                earliest = valid_timestamps[0]
                retry_after = int(earliest + window_seconds - now) + 1
                self._requests[key] = valid_timestamps
                return False, 0, max(1, retry_after)

            valid_timestamps.append(now)
            self._requests[key] = valid_timestamps
            remaining = max_requests - len(valid_timestamps)
            return True, remaining, 0

    def cleanup(self):
        """Purge stale records older than 10 minutes."""
        now = time.time()
        cutoff = now - 600
        with self._lock:
            for key in list(self._requests.keys()):
                self._requests[key] = [t for t in self._requests[key] if t > cutoff]
                if not self._requests[key]:
                    del self._requests[key]

limiter = RateLimiter()

class RateLimitMiddleware(BaseHTTPMiddleware):
    # Route rules: (method, path_prefix, max_requests, window_seconds)
    RULES = [
        ("POST", "/login", 30, 60),             # Max 30 login POSTs per minute per IP
        ("POST", "/datasets/upload", 40, 60),    # Max 40 uploads per minute per IP
    ]

    async def dispatch(self, request: Request, call_next):
        # Client IP extraction (handles proxy headers safely)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "127.0.0.1"

        method = request.method
        path = request.url.path

        for rule_method, rule_prefix, max_reqs, window_secs in self.RULES:
            if method == rule_method and path.startswith(rule_prefix):
                allowed, remaining, retry_after = limiter.is_allowed(client_ip, rule_prefix, max_reqs, window_secs)
                if not allowed:
                    log_security_event(
                        event_type="RATE_LIMIT_EXCEEDED",
                        client_ip=client_ip,
                        resource=path,
                        details={"rule_prefix": rule_prefix, "max_requests": max_reqs, "window_seconds": window_secs},
                        status="BLOCKED"
                    )
                    return JSONResponse(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        content={
                            "error": {
                                "code": "RATE_LIMIT_EXCEEDED",
                                "message": f"Too many requests. Please wait {retry_after} seconds before trying again.",
                                "retry_after": retry_after
                            }
                        },
                        headers={
                            "Retry-After": str(retry_after),
                            "X-RateLimit-Limit": str(max_reqs),
                            "X-RateLimit-Remaining": "0"
                        }
                    )

        response = await call_next(request)
        return response
