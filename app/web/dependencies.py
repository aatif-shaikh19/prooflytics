from typing import Optional
from fastapi import Cookie, Depends, Form, Header, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.config import settings
from app.db.models import Dataset, Report, SessionRecord, User
from app.db.session import get_db
from app.services.auth import get_session_by_token, validate_csrf

def get_session_token_from_request(
    request: Request,
    prooflytics_session: Optional[str] = Cookie(None, alias=settings.SESSION_COOKIE_NAME)
) -> Optional[str]:
    """Retrieve session token from HttpOnly cookie or Authorization Bearer header."""
    if prooflytics_session:
        return prooflytics_session
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    return None

def get_current_session(
    request: Request,
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(get_session_token_from_request)
) -> Optional[SessionRecord]:
    """Return active SessionRecord or None."""
    if not token:
        return None
    session_record = get_session_by_token(db, token)
    return session_record

def get_current_user(
    current_session: Optional[SessionRecord] = Depends(get_current_session),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Return authenticated User or None."""
    if not current_session:
        return None
    user = db.query(User).filter(User.id == current_session.user_id).first()
    return user

def require_authenticated_user(
    user: Optional[User] = Depends(get_current_user)
) -> User:
    """Enforce that the request is authenticated; raise 401 if not."""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    return user

def require_csrf(
    request: Request,
    current_session: Optional[SessionRecord] = Depends(get_current_session),
    csrf_token: Optional[str] = Form(None),
    x_csrf_token: Optional[str] = Header(None, alias="X-CSRF-Token")
) -> None:
    """
    Enforce CSRF protection for state-changing HTTP methods on session-authenticated routes.
    Accepts CSRF token from either form field 'csrf_token' or header 'X-CSRF-Token'.
    """
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        if not current_session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        token_to_check = csrf_token or x_csrf_token
        if not token_to_check or not validate_csrf(current_session, token_to_check):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid or missing CSRF token"
            )

def get_user_dataset(
    dataset_id: str,
    user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db)
) -> Dataset:
    """
    Retrieve dataset strictly scoped to authenticated owner.
    Returns 404 to avoid leaking existence across tenants.
    """
    dataset = db.query(Dataset).filter(
        Dataset.id == dataset_id,
        Dataset.owner_id == user.id
    ).first()
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found"
        )
    return dataset

def get_user_report(
    report_id: str,
    user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db)
) -> Report:
    """
    Retrieve report strictly scoped to authenticated owner.
    Returns 404 to avoid leaking existence across tenants.
    """
    report = db.query(Report).filter(
        Report.id == report_id,
        Report.owner_id == user.id
    ).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )
    return report
