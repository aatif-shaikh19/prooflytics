"""
Report and Report Block management service for Prooflytics.

Enforces:
1. Multi-tenant isolation: every query is scoped to owner_id.
2. Transitive ownership: block belongs to report, which belongs to owner, bound to owned dataset.
3. Server-side validation of block configuration and global filters.
4. Position indexing and keyboard-accessible reordering (up/down).
5. Unified evaluation: evaluates all blocks against dataset rows and active filters.
"""
import json
from typing import Any, Dict, List, Literal, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import Dataset, DatasetRow, Report, ReportBlock
from app.schemas.analytics import BlockConfig, CalculationResult, ReportFilter
from app.services.analytics import evaluate_block

def get_owner_report(db: Session, owner_id: str, report_id: str) -> Report:
    """Fetch report strictly scoped to owner_id. Returns 404 on mismatch to avoid leakage."""
    report = db.query(Report).filter(
        Report.id == report_id,
        Report.owner_id == owner_id
    ).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )
    return report

def create_report(
    db: Session,
    owner_id: str,
    dataset_id: str,
    title: str
) -> Report:
    """Create a new report bound to an owned dataset."""
    dataset = db.query(Dataset).filter(
        Dataset.id == dataset_id,
        Dataset.owner_id == owner_id
    ).first()
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found or not owned by user"
        )

    clean_title = title.strip() if title and title.strip() else f"Report for {dataset.name}"

    report = Report(
        owner_id=owner_id,
        dataset_id=dataset.id,
        title=clean_title,
        filter_json="{}"
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report

def update_report_title(
    db: Session,
    owner_id: str,
    report_id: str,
    title: str
) -> Report:
    """Update title of an owned report."""
    report = get_owner_report(db, owner_id, report_id)
    if title and title.strip():
        report.title = title.strip()
        db.commit()
        db.refresh(report)
    return report

def update_report_filter(
    db: Session,
    owner_id: str,
    report_id: str,
    filter_data: Dict[str, Any]
) -> Report:
    """Validate and persist report-level filter configuration."""
    report = get_owner_report(db, owner_id, report_id)

    # Validate schema using ReportFilter Pydantic model
    try:
        validated_filter = ReportFilter(**filter_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid filter configuration: {e}"
        )
    report.filter_json = validated_filter.model_dump_json()
    db.commit()
    db.refresh(report)
    return report

def delete_report(
    db: Session,
    owner_id: str,
    report_id: str
) -> None:
    """Delete an owned report and its associated blocks."""
    report = get_owner_report(db, owner_id, report_id)
    db.delete(report)
    db.commit()

def add_report_block(
    db: Session,
    owner_id: str,
    report_id: str,
    kind: str,
    config_dict: Dict[str, Any]
) -> ReportBlock:
    """Add a validated block to an owned report."""
    report = get_owner_report(db, owner_id, report_id)

    # Validate config
    try:
        valid_config = BlockConfig(kind=kind, **config_dict)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid block configuration: {e}"
        )

    # Determine next position
    max_pos = db.query(ReportBlock.position).filter(
        ReportBlock.report_id == report.id
    ).order_by(ReportBlock.position.desc()).first()

    next_pos = (max_pos[0] + 1) if max_pos else 0

    block = ReportBlock(
        report_id=report.id,
        kind=kind,
        position=next_pos,
        config_json=valid_config.model_dump_json()
    )
    db.add(block)
    db.commit()
    db.refresh(block)
    return block

def delete_report_block(
    db: Session,
    owner_id: str,
    report_id: str,
    block_id: str
) -> None:
    """Delete a block from an owned report and re-normalize continuous positions."""
    report = get_owner_report(db, owner_id, report_id)
    block = db.query(ReportBlock).filter(
        ReportBlock.id == block_id,
        ReportBlock.report_id == report.id
    ).first()
    if not block:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report block not found"
        )

    db.delete(block)
    db.commit()

    # Re-normalize remaining block positions
    remaining_blocks = db.query(ReportBlock).filter(
        ReportBlock.report_id == report.id
    ).order_by(ReportBlock.position.asc()).all()

    for idx, b in enumerate(remaining_blocks):
        b.position = idx
    db.commit()

def move_report_block(
    db: Session,
    owner_id: str,
    report_id: str,
    block_id: str,
    direction: Literal["up", "down"]
) -> None:
    """
    Swap positions between adjacent blocks for keyboard-accessible reordering.
    Does nothing if already at boundary.
    """
    report = get_owner_report(db, owner_id, report_id)
    blocks = db.query(ReportBlock).filter(
        ReportBlock.report_id == report.id
    ).order_by(ReportBlock.position.asc()).all()

    block_indices = {b.id: i for i, b in enumerate(blocks)}
    if block_id not in block_indices:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report block not found"
        )

    curr_idx = block_indices[block_id]
    swap_idx = (curr_idx - 1) if direction == "up" else (curr_idx + 1)

    if 0 <= swap_idx < len(blocks):
        # Swap positions
        blocks[curr_idx].position, blocks[swap_idx].position = (
            blocks[swap_idx].position,
            blocks[curr_idx].position,
        )
        db.commit()

def evaluate_report_blocks(
    db: Session,
    report: Report
) -> List[Tuple[ReportBlock, CalculationResult]]:
    """
    Evaluate all blocks in a report against its bound dataset rows and report filter.
    Returns list of (block_model, calculation_result).
    """
    # Fetch rows from bound dataset
    dataset_rows = db.query(DatasetRow).filter(
        DatasetRow.dataset_id == report.dataset_id
    ).order_by(DatasetRow.source_row_number.asc()).all()

    raw_row_items = [
        {
            "typed": r.typed_json,
            "structurally_valid": r.structurally_valid
        }
        for r in dataset_rows
    ]

    # Parse report filter
    try:
        filter_dict = json.loads(report.filter_json or "{}")
        report_filter = ReportFilter(**filter_dict)
    except Exception:
        report_filter = ReportFilter()

    results: List[Tuple[ReportBlock, CalculationResult]] = []

    # Sort blocks by position
    sorted_blocks = sorted(report.blocks, key=lambda b: b.position)

    for block in sorted_blocks:
        try:
            cfg_dict = json.loads(block.config_json or "{}")
            block_cfg = BlockConfig(kind=block.kind, **cfg_dict)
        except Exception:
            block_cfg = BlockConfig(kind=block.kind)

        calc_result = evaluate_block(raw_row_items, block_cfg, report_filter=report_filter)
        results.append((block, calc_result))

    return results
