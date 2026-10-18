"""
Public anonymous share endpoints for Prooflytics.

Enforces:
1. Validates token existence, expiry, and revocation on EVERY request.
2. Read-only projection using live report semantics and authoritative Polars engine.
3. No-store and no-referrer response headers.
4. Zero leakage of dataset IDs, raw CSV rows, user identifiers, or edit controls.
"""
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.shares import resolve_share_token

router = APIRouter(prefix="/share", tags=["shares"])
templates = Jinja2Templates(directory="app/templates")

def _set_security_headers(response: Response) -> None:
    """Enforce strict caching prevention and privacy headers for shared content."""
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Referrer-Policy"] = "no-referrer"

@router.get("/{token}", response_class=HTMLResponse)
def view_shared_report_page(
    request: Request,
    token: str,
    db: Session = Depends(get_db)
):
    """
    Public anonymous HTML view of a shared report.
    Re-verifies token, expiry, and revocation on every invocation.
    """
    try:
        share_link, report, evaluated_blocks = resolve_share_token(db, token)
        response = templates.TemplateResponse(
            request=request,
            name="shared_report.html",
            context={
                "request": request,
                "current_user": None,
                "current_session": None,
                "report": report,
                "evaluated_blocks": evaluated_blocks,
            }
        )
        _set_security_headers(response)
        return response

    except HTTPException as e:
        status_code = e.status_code
        if status_code == status.HTTP_410_GONE:
            if "revoked" in str(e.detail).lower():
                error_type = "revoked"
                error_title = "Share Link Revoked"
                error_message = "This share link has been revoked by the report owner."
            else:
                error_type = "expired"
                error_title = "Share Link Expired"
                error_message = "This share link has expired and is no longer accessible."
        else:
            error_type = "not_found"
            error_title = "Report Not Found"
            error_message = "The requested report could not be found or the link is invalid."

        response = templates.TemplateResponse(
            request=request,
            name="shared_error.html",
            context={
                "request": request,
                "current_user": None,
                "current_session": None,
                "error_type": error_type,
                "error_title": error_title,
                "error_message": error_message,
            },
            status_code=status_code
        )
        _set_security_headers(response)
        return response

@router.get("/{token}/api")
def get_shared_report_api(
    token: str,
    db: Session = Depends(get_db)
):
    """
    Public anonymous JSON projection of a shared report.
    Returns strictly serialized calculation results and provenance.
    Excludes dataset IDs, raw CSV rows, user identifiers, and mutation endpoints.
    """
    share_link, report, evaluated_blocks = resolve_share_token(db, token)

    payload = {
        "report_title": report.title,
        "blocks": [
            {
                "id": block.id,
                "kind": block.kind,
                "position": block.position,
                "calculation": calc.model_dump()
            }
            for block, calc in evaluated_blocks
        ]
    }

    response = JSONResponse(content=payload)
    _set_security_headers(response)
    return response
