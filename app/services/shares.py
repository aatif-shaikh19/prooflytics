"""
Share Link service for Prooflytics.

Enforces:
1. Cryptographically secure random tokens generated via `secrets`.
2. SHA-256 token hashing so raw bearer tokens are NEVER stored in plaintext in the database.
3. Owner-only generation and revocation of expiring share links.
4. Validation of token existence, expiry, and revocation on EVERY anonymous request.
5. Strict read-only public projection using the live report semantics and same Polars analytics service.
6. Zero leakage of raw CSV cells, dataset IDs, owner identity, or edit endpoints.
"""
import hashlib
import json
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import Report, ReportBlock, ShareLink
from app.schemas.analytics import CalculationResult
from app.services.reports import evaluate_report_blocks, get_owner_report

def hash_token(raw_token: str) -> str:
    """Compute SHA-256 hex digest of a bearer token."""
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()

def create_share_link(
    db: Session,
    owner_id: str,
    report_id: str,
    expires_in_days: int = 7
) -> Tuple[ShareLink, str]:
    """
    Create a new expiring share link for an owned report.
    Returns the created ShareLink DB model and the raw bearer token (to show once to owner).
    """
    # Enforce report ownership
    report = get_owner_report(db, owner_id, report_id)

    # Bound expiry: minimum 1 day, maximum 90 days, default 7 days
    days = max(1, min(90, expires_in_days))
    expires_at = datetime.utcnow() + timedelta(days=days)

    # Generate 32 bytes (256 bits) cryptographically random urlsafe token
    raw_token = secrets.token_urlsafe(32)
    token_digest = hash_token(raw_token)

    share_link = ShareLink(
        report_id=report.id,
        token_hash=token_digest,
        expires_at=expires_at,
        revoked_at=None,
    )
    db.add(share_link)
    db.commit()
    db.refresh(share_link)

    return share_link, raw_token

def revoke_share_link(
    db: Session,
    owner_id: str,
    report_id: str,
    share_id: str
) -> ShareLink:
    """
    Revoke an active share link. Enforces owner authorization.
    """
    report = get_owner_report(db, owner_id, report_id)

    share_link = db.query(ShareLink).filter(
        ShareLink.id == share_id,
        ShareLink.report_id == report.id
    ).first()

    if not share_link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share link not found"
        )

    if not share_link.revoked_at:
        share_link.revoked_at = datetime.utcnow()
        db.commit()
        db.refresh(share_link)

    return share_link

def list_report_shares(
    db: Session,
    owner_id: str,
    report_id: str
) -> List[ShareLink]:
    """List all share links for an owned report."""
    report = get_owner_report(db, owner_id, report_id)
    return db.query(ShareLink).filter(
        ShareLink.report_id == report.id
    ).order_by(ShareLink.created_at.desc()).all()

def resolve_share_token(
    db: Session,
    raw_token: str
) -> Tuple[ShareLink, Report, List[Tuple[ReportBlock, CalculationResult]]]:
    """
    Validate public share token on every request:
    1. Hashes token and queries DB.
    2. Validates token existence, revocation, and expiration.
    3. Evaluates live report blocks using the authoritative analytics service.
    4. Raises appropriate HTTP status on failure with zero metadata leakage.
    """
    if not raw_token or not raw_token.strip():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )

    token_digest = hash_token(raw_token)
    share_link = db.query(ShareLink).filter(
        ShareLink.token_hash == token_digest
    ).first()

    if not share_link:
        # Avoid leaking whether token ever existed
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found or link is invalid"
        )

    # Check if revoked
    if share_link.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This share link has been revoked by the owner"
        )

    # Check if expired
    if datetime.utcnow() > share_link.expires_at:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This share link has expired"
        )

    # Evaluate live report blocks using identical Polars calculation engine
    report = share_link.report
    evaluated_blocks = evaluate_report_blocks(db, report)

    return share_link, report, evaluated_blocks
