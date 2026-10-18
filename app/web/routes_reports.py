import json
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db.models import Dataset, DatasetRow, Report, ReportBlock, SessionRecord, User
from app.db.session import get_db
from app.schemas.analytics import ReportFilter
from app.services.reports import (
    add_report_block,
    create_report,
    delete_report,
    delete_report_block,
    evaluate_report_blocks,
    get_owner_report,
    move_report_block,
    update_report_filter,
    update_report_title,
)
from app.services.shares import (
    create_share_link,
    list_report_shares,
    revoke_share_link,
)
from app.services.suggestions import create_report_with_suggestions
from app.web.dependencies import (
    get_current_session,
    get_user_report,
    require_authenticated_user,
    require_csrf,
)

router = APIRouter(prefix="/reports", tags=["reports"])
templates = Jinja2Templates(directory="app/templates")

@router.get("", response_class=RedirectResponse)
def list_reports_redirect():
    """Redirect to main dashboard which lists reports and datasets."""
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

@router.get("/create", response_class=HTMLResponse)
def create_report_page(
    request: Request,
    user: User = Depends(require_authenticated_user),
    session_record: Optional[SessionRecord] = Depends(get_current_session),
    db: Session = Depends(get_db)
):
    """Render report creation form with user's available datasets."""
    datasets = (
        db.query(Dataset)
        .filter(Dataset.owner_id == user.id)
        .order_by(Dataset.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        request=request,
        name="report_create.html",
        context={
            "request": request,
            "current_user": user,
            "current_session": session_record,
            "datasets": datasets,
            "error": None,
        },
    )

@router.post("", response_class=RedirectResponse)
def create_report_action(
    request: Request,
    title: str = Form(...),
    dataset_id: str = Form(...),
    user: User = Depends(require_authenticated_user),
    session_record: Optional[SessionRecord] = Depends(get_current_session),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    """Handle report creation form submission."""
    try:
        report = create_report(
            db=db,
            owner_id=user.id,
            dataset_id=dataset_id,
            title=title,
        )
        return RedirectResponse(
            url=f"/reports/{report.id}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except HTTPException:
        raise
    except Exception as e:
        datasets = (
            db.query(Dataset)
            .filter(Dataset.owner_id == user.id)
            .order_by(Dataset.created_at.desc())
            .all()
        )
        return templates.TemplateResponse(
            request=request,
            name="report_create.html",
            context={
                "request": request,
                "current_user": user,
                "current_session": session_record,
                "datasets": datasets,
                "error": str(e),
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

@router.post("/from-suggestions", response_class=RedirectResponse)
def create_report_from_suggestions_action(
    dataset_id: str = Form(...),
    title: Optional[str] = Form(None),
    user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    """Create a new report pre-populated with deterministic suggested blocks after human confirmation."""
    report = create_report_with_suggestions(
        db=db,
        owner_id=user.id,
        dataset_id=dataset_id,
        title=title,
    )
    return RedirectResponse(
        url=f"/reports/{report.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )

@router.get("/api")
def list_reports_api(
    user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
):
    """JSON API returning only reports belonging to the authenticated user."""
    reports = (
        db.query(Report)
        .filter(Report.owner_id == user.id)
        .order_by(Report.created_at.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "dataset_id": r.dataset_id,
            "title": r.title,
            "filter_json": r.filter_json,
            "created_at": r.created_at.isoformat(),
            "updated_at": r.updated_at.isoformat(),
        }
        for r in reports
    ]

@router.get("/{report_id}", response_class=HTMLResponse)
def view_report_page(
    request: Request,
    report: Report = Depends(get_user_report),
    user: User = Depends(require_authenticated_user),
    session_record: Optional[SessionRecord] = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Render complete report view with evaluated blocks, provenance details,
    reordering controls, and filter configurations.
    """
    evaluated_blocks = evaluate_report_blocks(db, report)

    # Extract column schema metadata from bound dataset
    schema = {}
    try:
        schema = json.loads(report.dataset.schema_json or "{}")
    except Exception:
        schema = {}

    cols = schema.get("columns", [])
    normalized_cols = []
    for c in cols:
        if isinstance(c, dict):
            normalized_cols.append({"name": c.get("name", ""), "type": c.get("type", "text")})
        elif isinstance(c, str):
            normalized_cols.append({"name": c, "type": "text"})

    date_columns = [c["name"] for c in normalized_cols if c["type"] == "date"]
    category_columns = [c["name"] for c in normalized_cols if c["type"] == "category"]
    all_columns = normalized_cols

    # Parse active report filter
    try:
        filter_dict = json.loads(report.filter_json or "{}")
        active_filter = ReportFilter(**filter_dict)
    except Exception:
        active_filter = ReportFilter()

    # Retrieve existing share links
    shares = list_report_shares(db, owner_id=user.id, report_id=report.id)
    created_token = request.query_params.get("created_token")

    return templates.TemplateResponse(
        request=request,
        name="report_detail.html",
        context={
            "request": request,
            "current_user": user,
            "current_session": session_record,
            "report": report,
            "dataset": report.dataset,
            "evaluated_blocks": evaluated_blocks,
            "active_filter": active_filter,
            "date_columns": date_columns,
            "category_columns": category_columns,
            "all_columns": all_columns,
            "shares": shares,
            "created_token": created_token,
            "now": datetime.utcnow(),
        },
    )

@router.get("/{report_id}/api")
def get_report_api(
    report: Report = Depends(get_user_report),
):
    """
    JSON API returning single report details strictly owner-scoped.
    Returns 404 if owned by another user.
    """
    return {
        "id": report.id,
        "dataset_id": report.dataset_id,
        "title": report.title,
        "filter_json": report.filter_json,
        "created_at": report.created_at.isoformat(),
        "updated_at": report.updated_at.isoformat(),
        "blocks": [
            {
                "id": b.id,
                "kind": b.kind,
                "position": b.position,
                "config_json": b.config_json,
            }
            for b in report.blocks
        ],
    }

@router.post("/{report_id}/edit", response_class=RedirectResponse)
def update_report_title_action(
    title: str = Form(...),
    report: Report = Depends(get_user_report),
    user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    """Update title of an owned report."""
    update_report_title(db, owner_id=user.id, report_id=report.id, title=title)
    return RedirectResponse(
        url=f"/reports/{report.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )

@router.post("/{report_id}/filter", response_class=RedirectResponse)
def update_report_filter_action(
    report: Report = Depends(get_user_report),
    user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
    date_column: Optional[str] = Form(None),
    start_date: Optional[str] = Form(None),
    end_date: Optional[str] = Form(None),
    category_column: Optional[str] = Form(None),
    selected_categories: Optional[str] = Form(None),
    clear: Optional[str] = Form(None),
    _: None = Depends(require_csrf),
):
    """Update or clear report-level filters applied to all data blocks."""
    if clear:
        filter_data: Dict[str, Any] = {}
    else:
        cats = [
            c.strip()
            for c in (selected_categories or "").split(",")
            if c.strip()
        ]
        filter_data = {
            "date_column": date_column if date_column else None,
            "start_date": start_date.strip() if start_date and start_date.strip() else None,
            "end_date": end_date.strip() if end_date and end_date.strip() else None,
            "category_column": category_column if category_column else None,
            "selected_categories": cats if cats else None,
        }

    update_report_filter(db, owner_id=user.id, report_id=report.id, filter_data=filter_data)
    return RedirectResponse(
        url=f"/reports/{report.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )

@router.post("/{report_id}/delete", response_class=RedirectResponse)
def delete_report_action(
    report: Report = Depends(get_user_report),
    user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    """Delete an owned report and all its blocks."""
    delete_report(db, owner_id=user.id, report_id=report.id)
    return RedirectResponse(
        url="/",
        status_code=status.HTTP_303_SEE_OTHER,
    )

@router.post("/{report_id}/blocks", response_class=RedirectResponse)
def add_block_action(
    report: Report = Depends(get_user_report),
    user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
    kind: str = Form(...),
    title: Optional[str] = Form(None),
    column: Optional[str] = Form(None),
    op: Optional[str] = Form(None),
    group_by_column: Optional[str] = Form(None),
    limit: Optional[int] = Form(10),
    note_text: Optional[str] = Form(None),
    _: None = Depends(require_csrf),
):
    """Add a new validated block to the report."""
    clean_column = column.strip() if column and column.strip() else None
    clean_group = group_by_column.strip() if group_by_column and group_by_column.strip() else None
    clean_title = title.strip() if title and title.strip() else None
    clean_note = note_text.strip() if note_text and note_text.strip() else None
    clean_op = op.strip().upper() if op and op.strip() else "SUM"

    try:
        limit_val = int(limit) if limit is not None else 10
        if limit_val < 1:
            limit_val = 10
    except (ValueError, TypeError):
        limit_val = 10

    config_dict: Dict[str, Any] = {
        "title": clean_title,
        "column": clean_column,
        "op": clean_op,
        "group_by_column": clean_group,
        "limit": limit_val,
        "note_text": clean_note,
    }

    block = add_report_block(
        db=db,
        owner_id=user.id,
        report_id=report.id,
        kind=kind,
        config_dict=config_dict,
    )
    return RedirectResponse(
        url=f"/reports/{report.id}#block-{block.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )

@router.post("/{report_id}/blocks/{block_id}/delete", response_class=RedirectResponse)
def delete_block_action(
    block_id: str,
    report: Report = Depends(get_user_report),
    user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    """Delete a block from an owned report and re-normalize positions."""
    delete_report_block(
        db=db,
        owner_id=user.id,
        report_id=report.id,
        block_id=block_id,
    )
    return RedirectResponse(
        url=f"/reports/{report.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )

@router.post("/{report_id}/blocks/{block_id}/move", response_class=RedirectResponse)
def move_block_action(
    block_id: str,
    direction: str = Form(...),
    report: Report = Depends(get_user_report),
    user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    """
    Swap positions between adjacent blocks for accessible keyboard reordering.
    Accepts 'up' or 'down'.
    """
    if direction not in ("up", "down"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Direction must be 'up' or 'down'",
        )

    move_report_block(
        db=db,
        owner_id=user.id,
        report_id=report.id,
        block_id=block_id,
        direction=direction,  # type: ignore[arg-type]
    )
    return RedirectResponse(
        url=f"/reports/{report.id}#block-{block_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )

@router.post("/{report_id}/shares", response_class=RedirectResponse)
def create_share_link_action(
    report: Report = Depends(get_user_report),
    user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
    expires_days: int = Form(7),
    _: None = Depends(require_csrf),
):
    """Generate a cryptographically random share token with bounded expiration."""
    share_link, raw_token = create_share_link(
        db=db,
        owner_id=user.id,
        report_id=report.id,
        expires_in_days=expires_days,
    )
    return RedirectResponse(
        url=f"/reports/{report.id}?created_token={raw_token}#shares",
        status_code=status.HTTP_303_SEE_OTHER,
    )

@router.post("/{report_id}/shares/{share_id}/revoke", response_class=RedirectResponse)
def revoke_share_link_action(
    share_id: str,
    report: Report = Depends(get_user_report),
    user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    """Revoke an active share link immediately."""
    revoke_share_link(
        db=db,
        owner_id=user.id,
        report_id=report.id,
        share_id=share_id,
    )
    return RedirectResponse(
        url=f"/reports/{report.id}#shares",
        status_code=status.HTTP_303_SEE_OTHER,
    )

@router.post("/{report_id}/clone", response_class=RedirectResponse)
def clone_report_action(
    report: Report = Depends(get_user_report),
    user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    """Clone an existing report and all its blocks for rapid iteration."""
    cloned_report = Report(
        owner_id=user.id,
        dataset_id=report.dataset_id,
        title=f"Copy of {report.title}",
        filter_json=report.filter_json,
    )
    db.add(cloned_report)
    db.commit()
    db.refresh(cloned_report)

    for block in report.blocks:
        cloned_block = ReportBlock(
            report_id=cloned_report.id,
            kind=block.kind,
            position=block.position,
            config_json=block.config_json,
        )
        db.add(cloned_block)
    db.commit()

    return RedirectResponse(
        url=f"/reports/{cloned_report.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )

@router.get("/{report_id}/export-csv")
def export_report_csv_action(
    report: Report = Depends(get_user_report),
    user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
):
    """
    Export dataset rows included in this report (filtered according to report filter)
    as an RFC 4180 CSV attachment, sanitizing potential Excel formula injections.
    """
    import csv
    import io
    from fastapi.responses import StreamingResponse

    # Parse active filter
    try:
        filter_dict = json.loads(report.filter_json or "{}")
        active_filter = ReportFilter(**filter_dict)
    except Exception:
        active_filter = ReportFilter()

    # Load rows
    rows = db.query(DatasetRow).filter(
        DatasetRow.dataset_id == report.dataset_id,
        DatasetRow.structurally_valid == True
    ).order_by(DatasetRow.source_row_number).all()

    # Filter rows according to active_filter
    included_rows = []
    headers_set = set()
    for r in rows:
        typed = json.loads(r.typed_json or "{}")
        # Check date filter
        if active_filter.date_column:
            val = typed.get(active_filter.date_column)
            if val is None or str(val) < (active_filter.start_date or "") or (active_filter.end_date and str(val) > active_filter.end_date):
                continue
        # Check category filter
        if active_filter.category_column and active_filter.selected_categories:
            val = typed.get(active_filter.category_column)
            if str(val) not in active_filter.selected_categories:
                continue
        included_rows.append(typed)
        headers_set.update(typed.keys())

    # Build CSV output
    output = io.StringIO()
    headers = sorted(list(headers_set))
    writer = csv.writer(output)
    writer.writerow(headers)

    for row in included_rows:
        row_vals = []
        for h in headers:
            val = row.get(h)
            if val is None:
                row_vals.append("")
            else:
                s_val = str(val)
                # DDE Formula Injection Sanitization: prepend ' if begins with =, +, -, @
                if s_val and s_val[0] in ("=", "+", "-", "@", "\t", "\r"):
                    s_val = "'" + s_val
                row_vals.append(s_val)
        writer.writerow(row_vals)

    output.seek(0)
    sanitized_filename = "".join(c for c in report.title if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_").lower()
    filename = f"{sanitized_filename or 'report'}_export.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        }
    )


