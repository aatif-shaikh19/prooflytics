import json
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db.models import Dataset, DatasetRow, SessionRecord, User
from app.db.session import get_db
from app.services.ingestion import (
    EmptyCSVError,
    EncodingError,
    IngestionError,
    MalformedCSVError,
    OversizedFileError,
    ingest_dataset_from_bytes,
)
from app.services.suggestions import get_deterministic_suggestions
from app.web.dependencies import (
    get_current_session,
    get_user_dataset,
    require_authenticated_user,
    require_csrf,
)

router = APIRouter(prefix="/datasets", tags=["datasets"])
templates = Jinja2Templates(directory="app/templates")

@router.get("", response_class=HTMLResponse)
def list_datasets_page(
    request: Request,
    user: User = Depends(require_authenticated_user),
    session_record: Optional[SessionRecord] = Depends(get_current_session),
    db: Session = Depends(get_db)
):
    """HTML view listing datasets owned by authenticated user."""
    datasets = db.query(Dataset).filter(Dataset.owner_id == user.id).order_by(Dataset.created_at.desc()).all()
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "current_user": user,
            "current_session": session_record,
            "datasets": datasets,
            "reports": []
        }
    )

@router.get("/upload", response_class=HTMLResponse)
def upload_dataset_page(
    request: Request,
    user: User = Depends(require_authenticated_user),
    session_record: Optional[SessionRecord] = Depends(get_current_session)
):
    """Render CSV file upload form."""
    return templates.TemplateResponse(
        request=request,
        name="dataset_upload.html",
        context={
            "current_user": user,
            "current_session": session_record,
            "error": None
        }
    )

@router.post("/upload")
async def upload_dataset_form(
    request: Request,
    csv_file: UploadFile = File(...),
    dataset_name: Optional[str] = Form(None),
    user: User = Depends(require_authenticated_user),
    session_record: Optional[SessionRecord] = Depends(get_current_session),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf)
):
    """Handle CSV file upload from HTML form with CSRF defense."""
    try:
        content_bytes = await csv_file.read()
        filename = csv_file.filename or "uploaded_data.csv"
        display_name = dataset_name.strip() if dataset_name and dataset_name.strip() else filename

        dataset = ingest_dataset_from_bytes(
            db=db,
            owner_id=user.id,
            original_filename=filename,
            dataset_name=display_name,
            content_bytes=content_bytes
        )

        return RedirectResponse(
            url=f"/datasets/{dataset.id}",
            status_code=status.HTTP_303_SEE_OTHER
        )

    except OversizedFileError as e:
        return templates.TemplateResponse(
            request=request,
            name="dataset_upload.html",
            context={
                "current_user": user,
                "current_session": session_record,
                "error": str(e)
            },
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
        )
    except (EncodingError, MalformedCSVError, EmptyCSVError, IngestionError) as e:
        return templates.TemplateResponse(
            request=request,
            name="dataset_upload.html",
            context={
                "current_user": user,
                "current_session": session_record,
                "error": str(e)
            },
            status_code=status.HTTP_400_BAD_REQUEST
        )

@router.post("/api/upload")
async def upload_dataset_api(
    csv_file: UploadFile = File(...),
    dataset_name: Optional[str] = Form(None),
    user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db)
):
    """JSON API endpoint for uploading and ingesting CSV."""
    try:
        content_bytes = await csv_file.read()
        filename = csv_file.filename or "uploaded_data.csv"
        display_name = dataset_name.strip() if dataset_name and dataset_name.strip() else filename

        dataset = ingest_dataset_from_bytes(
            db=db,
            owner_id=user.id,
            original_filename=filename,
            dataset_name=display_name,
            content_bytes=content_bytes
        )

        profile = json.loads(dataset.profile_json)
        return {
            "id": dataset.id,
            "name": dataset.name,
            "original_filename": dataset.original_filename,
            "row_count": dataset.row_count,
            "total_rows": profile.get("total_rows"),
            "accepted_rows": profile.get("accepted_rows"),
            "warning_rows": profile.get("warning_rows"),
            "rejected_rows": profile.get("rejected_rows"),
            "columns": profile.get("columns", [])
        }

    except OversizedFileError as e:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(e)
        )
    except (EncodingError, MalformedCSVError, EmptyCSVError, IngestionError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/api")
def list_datasets_api(
    user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db)
):
    """JSON API returning only datasets belonging to the authenticated user."""
    datasets = db.query(Dataset).filter(Dataset.owner_id == user.id).order_by(Dataset.created_at.desc()).all()
    return [
        {
            "id": d.id,
            "name": d.name,
            "status": d.status,
            "original_filename": d.original_filename,
            "row_count": d.row_count,
            "created_at": d.created_at.isoformat()
        }
        for d in datasets
    ]

@router.get("/{dataset_id}", response_class=HTMLResponse)
def get_dataset_page(
    request: Request,
    dataset: Dataset = Depends(get_user_dataset),
    user: User = Depends(require_authenticated_user),
    session_record: Optional[SessionRecord] = Depends(get_current_session)
):
    """HTML profile view for a specific dataset (strictly owner-scoped)."""
    try:
        profile_data = json.loads(dataset.profile_json)
    except Exception:
        profile_data = {}

    suggestions = get_deterministic_suggestions(dataset)

    return templates.TemplateResponse(
        request=request,
        name="dataset_detail.html",
        context={
            "request": request,
            "current_user": user,
            "current_session": session_record,
            "dataset": dataset,
            "profile": profile_data,
            "suggestions": suggestions,
        }
    )

@router.get("/{dataset_id}/api")
def get_dataset_api(
    dataset: Dataset = Depends(get_user_dataset)
):
    """JSON API returning single dataset profile strictly owner-scoped."""
    return {
        "id": dataset.id,
        "name": dataset.name,
        "status": dataset.status,
        "original_filename": dataset.original_filename,
        "row_count": dataset.row_count,
        "schema": json.loads(dataset.schema_json),
        "profile": json.loads(dataset.profile_json),
        "created_at": dataset.created_at.isoformat()
    }

@router.get("/{dataset_id}/rows/api")
def get_dataset_rows_api(
    dataset: Dataset = Depends(get_user_dataset),
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """JSON API returning individual dataset rows strictly owner-scoped."""
    bounded_limit = min(max(1, limit), 200)
    rows = db.query(DatasetRow).filter(
        DatasetRow.dataset_id == dataset.id
    ).order_by(DatasetRow.source_row_number).offset(offset).limit(bounded_limit).all()

    return [
        {
            "source_row_number": r.source_row_number,
            "raw": json.loads(r.raw_json),
            "typed": json.loads(r.typed_json),
            "issues": json.loads(r.issues_json),
            "structurally_valid": r.structurally_valid
        }
        for r in rows
    ]
