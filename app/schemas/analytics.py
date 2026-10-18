"""
Pydantic schemas for Report Filters, Block Configurations,
Canonical AST, Row Accounting, and Calculation Results.
"""
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, model_validator

class ReportFilter(BaseModel):
    """Global report-level filter applying to all data blocks."""
    date_column: Optional[str] = None
    start_date: Optional[str] = None  # ISO YYYY-MM-DD
    end_date: Optional[str] = None    # ISO YYYY-MM-DD
    category_column: Optional[str] = None
    selected_categories: Optional[List[str]] = None

    def is_active(self) -> bool:
        """Returns True if any filter constraint is set."""
        has_date = bool(self.date_column and (self.start_date or self.end_date))
        has_cat = bool(self.category_column and self.selected_categories)
        return has_date or has_cat

class BlockConfig(BaseModel):
    """Configuration specification for a report block."""
    kind: Literal["metric", "bar_chart", "line_chart", "top_n_table", "note"]
    title: Optional[str] = None
    column: Optional[str] = None
    op: Optional[Literal["SUM", "AVG", "COUNT", "MIN", "MAX"]] = "SUM"
    count_mode: Optional[Literal["count_non_null", "count_rows"]] = "count_non_null"
    group_by_column: Optional[str] = None
    sort_order: Optional[Literal["asc", "desc"]] = "desc"
    limit: Optional[int] = 10
    columns_to_show: Optional[List[str]] = None
    note_text: Optional[str] = None

class RowAccounting(BaseModel):
    """
    Mutually exclusive accounting of all rows in the dataset for a specific block computation:
    total_rows = structurally_rejected + filtered_out + invalid_for_operation + included.
    """
    total_rows: int
    structurally_rejected: int
    filtered_out: int
    invalid_for_operation: int
    included: int

    @model_validator(mode="after")
    def verify_disjoint_invariant(self) -> "RowAccounting":
        computed_total = (
            self.structurally_rejected
            + self.filtered_out
            + self.invalid_for_operation
            + self.included
        )
        if self.total_rows != computed_total:
            raise ValueError(
                f"Row accounting invariant violated: total_rows ({self.total_rows}) != "
                f"sum of disjoint partitions ({computed_total} = "
                f"{self.structurally_rejected} rejected + {self.filtered_out} filtered + "
                f"{self.invalid_for_operation} invalid_op + {self.included} included)"
            )
        return self

class CanonicalAST(BaseModel):
    """
    Exact canonical query/aggregation specification executed on the backend.
    Reflects genuine Polars expression, never fabricated SQL.
    """
    operation: str
    target_column: Optional[str] = None
    group_by: Optional[str] = None
    filters: Dict[str, Any] = Field(default_factory=dict)
    null_policy: str = "exclude_nulls"
    ordering: Optional[str] = None
    limit: Optional[int] = None
    execution_engine: str = "polars"
    polars_expression: str

class GroupResult(BaseModel):
    """Grouped aggregation data point."""
    group_key: str
    value: Optional[Union[float, int]] = None
    included_count: int

class CalculationResult(BaseModel):
    """Authoritative result combining rendered data and provenance lineage in ONE payload."""
    block_kind: str
    primary_value: Optional[Union[float, int, str]] = None
    formatted_value: str
    chart_data: Optional[Dict[str, Any]] = None
    table_data: Optional[Dict[str, Any]] = None
    group_breakdown: Optional[List[GroupResult]] = None
    row_accounting: RowAccounting
    canonical_ast: CanonicalAST
    human_formula: str
    narrative_explanation: str
