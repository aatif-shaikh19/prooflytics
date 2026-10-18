from typing import Optional
from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.config import settings
from app.db.models import SessionRecord, User
from app.db.session import get_db
from app.services.auth import (
    create_session,
    delete_session,
    verify_password
)
from app.web.dependencies import (
    get_current_session,
    get_current_user,
    get_session_token_from_request,
    require_authenticated_user,
    require_csrf
)

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/login", response_class=HTMLResponse)
def login_page(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user)
):
    """Render the login form. If already authenticated, redirect to dashboard."""
    if current_user:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"current_user": None, "error": None}
    )

@router.post("/login")
def login(
    request: Request,
    response: Response,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Authenticate user with email and password, create session, and set HttpOnly cookie."""
    normalized_email = email.strip().lower()
    user = db.query(User).filter(User.email == normalized_email).first()

    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "current_user": None,
                "error": "Invalid email or password",
                "email": email
            },
            status_code=status.HTTP_400_BAD_REQUEST
        )

    raw_token, session_record = create_session(db, user.id)

    # Set secure HttpOnly session cookie
    redirect = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    redirect.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=raw_token,
        max_age=settings.SESSION_MAX_AGE_DAYS * 86400,
        httponly=True,
        samesite="lax",
        secure=settings.COOKIE_SECURE,
        path="/"
    )
    return redirect

@router.post("/logout")
def logout(
    request: Request,
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(get_session_token_from_request),
    _: None = Depends(require_csrf)
):
    """Revoke session and clear session cookie. Requires valid CSRF token."""
    if token:
        delete_session(db, token)

    redirect = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    redirect.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path="/"
    )
    return redirect

@router.get("/api/me")
def api_me(
    user: User = Depends(require_authenticated_user),
    session_record: SessionRecord = Depends(get_current_session)
):
    """JSON inspection endpoint for authenticated user and CSRF token."""
    return {
        "id": user.id,
        "email": user.email,
        "csrf_token": session_record.csrf_token if session_record else None
    }
