import os
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session

from app.config import settings
from app.db import init_db, get_db, Dataset, Report, SessionRecord, User
from app.web.dependencies import get_current_session, get_current_user
from app.web.routes_auth import router as auth_router
from app.web.routes_datasets import router as datasets_router
from app.web.routes_reports import router as reports_router
from app.web.routes_shares import router as shares_router

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware applying defensive security headers to all responses.
    - Prevents MIME-sniffing
    - Prevents framing/clickjacking
    - Restricts referrer leakage
    - Enforces no-store cache control on authenticated responses
    """
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Apply no-store cache control for private endpoints and shared links
        if "prooflytics_session" in request.cookies or request.url.path.startswith(("/datasets", "/reports", "/api", "/share")):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"

        return response

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables on startup
    init_db()
    yield

def create_app() -> FastAPI:
    app = FastAPI(
        title="Prooflytics",
        description="Auditable, Provenance-First Reporting Platform",
        version="0.1.0",
        lifespan=lifespan
    )

    # Add security middleware
    app.add_middleware(SecurityHeadersMiddleware)

    # Mount static assets if directory exists
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if os.path.exists(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # Register routers
    app.include_router(auth_router)
    app.include_router(datasets_router)
    app.include_router(reports_router)
    app.include_router(shares_router)

    templates = Jinja2Templates(directory="app/templates")

    @app.get("/", response_class=HTMLResponse)
    def index_page(
        request: Request,
        current_user: Optional[User] = Depends(get_current_user),
        current_session: Optional[SessionRecord] = Depends(get_current_session),
        db: Session = Depends(get_db)
    ):
        """Root view: if authenticated, shows user dashboard; otherwise redirects to login."""
        if not current_user:
            return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

        datasets = db.query(Dataset).filter(
            Dataset.owner_id == current_user.id
        ).order_by(Dataset.created_at.desc()).all()

        reports = db.query(Report).filter(
            Report.owner_id == current_user.id
        ).order_by(Report.created_at.desc()).all()

        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context={
                "current_user": current_user,
                "current_session": current_session,
                "datasets": datasets,
                "reports": reports
            }
        )

    @app.get("/health")
    def health_check():
        return {"status": "ok", "app": "Prooflytics"}

    return app

app = create_app()
