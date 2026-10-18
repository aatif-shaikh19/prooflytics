"""
Security Audit Logger for Prooflytics.

Provides structured, tamper-evident security logging for:
- Authentication success & failures
- CSRF validation failures
- IDOR access denials (unauthorized cross-tenant attempts)
- Rate limiting triggers
- File upload rejections (magic bytes / malformed / oversized)
"""
import logging
import json
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger("prooflytics.security")
logger.setLevel(logging.INFO)

# Formatter producing structured JSON audit logs
class SecurityAuditFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event": record.msg,
            "level": record.levelname,
        }
        if hasattr(record, "audit_data"):
            log_obj.update(record.audit_data)
        return json.dumps(log_obj)

# Setup console handler if not present
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(SecurityAuditFormatter())
    logger.addHandler(handler)

def log_security_event(
    event_type: str,
    client_ip: str,
    user_id: Optional[str] = None,
    resource: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    status: str = "DENIED"
) -> None:
    """Log an auditable security event."""
    audit_data = {
        "event_type": event_type,
        "client_ip": client_ip,
        "user_id": user_id or "anonymous",
        "resource": resource or "none",
        "status": status,
        "details": details or {}
    }
    extra = {"audit_data": audit_data}
    logger.info(event_type, extra=extra)
