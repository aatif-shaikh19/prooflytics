import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from typing import Optional, Tuple
import bcrypt
from sqlalchemy.orm import Session
from app.config import settings
from app.db.models import SessionRecord, User

def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt with a random salt."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False

def hash_token(raw_token: str) -> str:
    """Compute the SHA-256 hexadecimal digest of a token."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

def create_session(db: Session, user_id: str) -> Tuple[str, SessionRecord]:
    """
    Generate an opaque 32-byte random session token, store its SHA-256 hash in DB,
    and generate a session-bound CSRF token.
    """
    raw_token = secrets.token_urlsafe(32)
    id_hash = hash_token(raw_token)
    csrf_token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(days=settings.SESSION_MAX_AGE_DAYS)

    session_record = SessionRecord(
        id_hash=id_hash,
        user_id=user_id,
        csrf_token=csrf_token,
        expires_at=expires_at,
        created_at=datetime.utcnow(),
    )
    db.add(session_record)
    db.commit()
    db.refresh(session_record)
    return raw_token, session_record

def get_session_by_token(db: Session, raw_token: str) -> Optional[SessionRecord]:
    """Retrieve an active, non-expired session by raw token."""
    if not raw_token:
        return None
    id_hash = hash_token(raw_token)
    session_record = db.query(SessionRecord).filter(
        SessionRecord.id_hash == id_hash,
        SessionRecord.expires_at > datetime.utcnow()
    ).first()
    return session_record

def delete_session(db: Session, raw_token: str) -> None:
    """Revoke/delete a session by raw token."""
    if not raw_token:
        return
    id_hash = hash_token(raw_token)
    session_record = db.query(SessionRecord).filter(SessionRecord.id_hash == id_hash).first()
    if session_record:
        db.delete(session_record)
        db.commit()

def validate_csrf(session_record: SessionRecord, submitted_token: Optional[str]) -> bool:
    """Safely compare session CSRF token with submitted token using constant-time comparison."""
    if not session_record or not submitted_token:
        return False
    return hmac.compare_digest(session_record.csrf_token, submitted_token)
