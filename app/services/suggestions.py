"""
Deterministic Chart and Block Suggestion Service for Prooflytics.

Enforces:
1. Strict determinism: recommendations are pure functions of inferred column types (number, category, date).
2. No non-deterministic AI generation or speculative schema guessing.
3. Requires human confirmation before any report or block is created.
4. Multitenant owner scoping on dataset retrieval and report binding.
"""
import json
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import Dataset, Report, ReportBlock
from app.schemas.analytics import BlockConfig
from app.services.reports import add_report_block, create_report, get_owner_report

def get_deterministic_suggestions(dataset: Dataset) -> List[Dict[str, Any]]:
    """
    Generate deterministic report block suggestions based strictly on inferred column types:
    - Number column -> Summary KPI metric (SUM)
    - Category + Number -> Bar chart breakdown
    - Date + Number -> Line chart trend over time
    - Number -> Top-N ranking table
    """
    try:
        schema = json.loads(dataset.schema_json or "{}")
        raw_columns = schema.get("columns", [])
    except Exception:
        raw_columns = []

    columns = []
    for c in raw_columns:
        if isinstance(c, dict):
            columns.append({"name": c.get("name", ""), "type": c.get("type", "text")})
        elif isinstance(c, str):
            columns.append({"name": c, "type": "text"})

    numbers = [c["name"] for c in columns if c.get("type") == "number"]
    categories = [c["name"] for c in columns if c.get("type") == "category"]
    dates = [c["name"] for c in columns if c.get("type") == "date"]

    suggestions: List[Dict[str, Any]] = []

    if numbers:
        primary_num = numbers[0]

        # 1. Primary Metric KPI
        suggestions.append({
            "kind": "metric",
            "title": f"Total {primary_num.replace('_', ' ').title()}",
            "column": primary_num,
            "op": "SUM",
            "group_by_column": None,
            "limit": 10,
            "reason": f"High-level KPI aggregation for primary numeric column '{primary_num}'.",
        })

        # 2. Bar Chart (Category + Number)
        if categories:
            primary_cat = categories[0]
            suggestions.append({
                "kind": "bar_chart",
                "title": f"{primary_num.replace('_', ' ').title()} by {primary_cat.replace('_', ' ').title()}",
                "column": primary_num,
                "op": "SUM",
                "group_by_column": primary_cat,
                "limit": 10,
                "reason": f"Category distribution comparing '{primary_num}' across distinct '{primary_cat}' values.",
            })

        # 3. Line Chart (Date + Number)
        if dates:
            primary_date = dates[0]
            suggestions.append({
                "kind": "line_chart",
                "title": f"{primary_num.replace('_', ' ').title()} Trend ({primary_date.replace('_', ' ').title()})",
                "column": primary_num,
                "op": "SUM",
                "group_by_column": primary_date,
                "limit": 20,
                "reason": f"Chronological trend of '{primary_num}' tracked over '{primary_date}'.",
            })

        # 4. Top-N Ranking Table
        suggestions.append({
            "kind": "top_n_table",
            "title": f"Top 10 Records by {primary_num.replace('_', ' ').title()}",
            "column": primary_num,
            "op": "SUM",
            "group_by_column": None,
            "limit": 10,
            "reason": f"Ordered ranking of highest-value records by '{primary_num}'.",
        })

    # 5. Explanatory Note Block
    suggestions.append({
        "kind": "note",
        "title": "Dataset Overview & Context",
        "column": None,
        "op": "SUM",
        "group_by_column": None,
        "limit": 10,
        "note_text": f"Report generated from dataset '{dataset.name}' containing {dataset.row_count} records. Columns inferred: {len(columns)} total ({len(numbers)} numeric, {len(categories)} categorical, {len(dates)} date).",
        "reason": "Contextual documentation providing provenance details for reviewers.",
    })

    return suggestions

def create_report_with_suggestions(
    db: Session,
    owner_id: str,
    dataset_id: str,
    title: Optional[str] = None
) -> Report:
    """
    Human-confirmed creation of a report populated with deterministic suggestions.
    Enforces owner authorization and creates blocks sequentially.
    """
    dataset = db.query(Dataset).filter(
        Dataset.id == dataset_id,
        Dataset.owner_id == owner_id
    ).first()
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found or not owned by user"
        )

    clean_title = title.strip() if title and title.strip() else f"Suggested Report: {dataset.name}"
    report = create_report(db, owner_id=owner_id, dataset_id=dataset.id, title=clean_title)

    # Generate and append deterministic suggestion blocks
    suggestions = get_deterministic_suggestions(dataset)
    for s in suggestions:
        config_dict = {
            "title": s["title"],
            "column": s.get("column"),
            "op": s.get("op", "SUM"),
            "group_by_column": s.get("group_by_column"),
            "limit": s.get("limit", 10),
            "note_text": s.get("note_text"),
        }
        add_report_block(
            db=db,
            owner_id=owner_id,
            report_id=report.id,
            kind=s["kind"],
            config_dict=config_dict,
        )

    return report
