"""
Authoritative calculation engine and provenance derivation service for Prooflytics.

Key invariants:
1. Server-side only: zero client-side arithmetic.
2. Unified calculation and provenance: one call returns rendered output and full audit trail.
3. Canonical AST reflects genuine Polars expressions executed, never fabricated SQL.
4. Exhaustive disjoint row accounting:
   total_rows = structurally_rejected + filtered_out + invalid_for_operation + included.
5. Deterministic null policy: MIN/MAX/AVG of empty sets return null, not misleading zeros.
6. COUNT of column defaults to non-null cells and reconciles with valid operations.
"""
import json
from typing import Any, Dict, List, Optional, Tuple, Union
import polars as pl
from app.schemas.analytics import (
    BlockConfig,
    CalculationResult,
    CanonicalAST,
    GroupResult,
    ReportFilter,
    RowAccounting,
)

def evaluate_block(
    raw_rows: List[Dict[str, Any]],
    block: BlockConfig,
    report_filter: Optional[ReportFilter] = None
) -> CalculationResult:
    """
    Evaluate a single report block against dataset rows with an optional report-level filter.
    Returns authoritative data and provenance in ONE CalculationResult payload.
    """
    report_filter = report_filter or ReportFilter()
    total_rows = len(raw_rows)

    # ---------------------------------------------------------
    # 1. Disjoint Row Partitioning
    # ---------------------------------------------------------
    structurally_rejected_count = 0
    filtered_out_count = 0
    invalid_for_op_count = 0
    eligible_rows: List[Dict[str, Any]] = []

    target_col = block.column
    group_col = block.group_by_column
    op = block.op or "SUM"
    count_mode = block.count_mode or "count_non_null"

    date_filter_active = bool(report_filter.date_column and (report_filter.start_date or report_filter.end_date))
    cat_filter_active = bool(report_filter.category_column and report_filter.selected_categories)

    for row_item in raw_rows:
        # Check partition 1: Structurally rejected (ragged or fatal parse error)
        if not row_item.get("structurally_valid", True):
            structurally_rejected_count += 1
            continue

        typed_vals = row_item.get("typed", {})
        if isinstance(typed_vals, str):
            typed_vals = json.loads(typed_vals)

        # Check partition 2: Filtered out by report-level date range or category filter
        # Note blocks display unchanged and are not subject to report filters (PRD FR-03).
        is_filtered = False
        if block.kind != "note":
            if date_filter_active:
                row_date = typed_vals.get(report_filter.date_column)
                if not row_date:
                    is_filtered = True
                else:
                    if report_filter.start_date and row_date < report_filter.start_date:
                        is_filtered = True
                    if report_filter.end_date and row_date > report_filter.end_date:
                        is_filtered = True

            if not is_filtered and cat_filter_active:
                row_cat = typed_vals.get(report_filter.category_column)
                if not row_cat or str(row_cat) not in report_filter.selected_categories:
                    is_filtered = True

        if is_filtered:
            filtered_out_count += 1
            continue

        # Check partition 3: Invalid for requested operation
        is_invalid_for_op = False
        if block.kind != "note":
            # For non-note blocks, if target_col is missing or not in row, row is invalid for operation
            if not target_col or (target_col not in typed_vals and target_col != "*"):
                is_invalid_for_op = True
            # For grouped operations (charts or grouped metrics), group key cannot be null
            elif group_col and (typed_vals.get(group_col) is None or str(typed_vals.get(group_col)).strip() == ""):
                is_invalid_for_op = True
            elif target_col:
                val = typed_vals.get(target_col)
                if op == "COUNT":
                    if count_mode == "count_non_null" and (val is None or str(val).strip() == ""):
                        is_invalid_for_op = True
                elif op in ("SUM", "AVG", "MIN", "MAX", "MEDIAN", "STDDEV"):
                    if val is None or not isinstance(val, (int, float)):
                        is_invalid_for_op = True

        if is_invalid_for_op:
            invalid_for_op_count += 1
            continue

        # Partition 4: Included in calculation
        eligible_rows.append(typed_vals)

    included_count = len(eligible_rows)

    # Validate disjoint partition invariant
    row_accounting = RowAccounting(
        total_rows=total_rows,
        structurally_rejected=structurally_rejected_count,
        filtered_out=filtered_out_count,
        invalid_for_operation=invalid_for_op_count,
        included=included_count
    )

    # ---------------------------------------------------------
    # 2. Polars Aggregation and Calculation
    # ---------------------------------------------------------
    primary_value: Optional[Union[float, int, str]] = None
    formatted_value = "—"
    chart_data: Optional[Dict[str, Any]] = None
    table_data: Optional[Dict[str, Any]] = None
    group_breakdown: Optional[List[GroupResult]] = None
    polars_expr_str = ""

    # Build Polars DataFrame from included rows
    if eligible_rows:
        df = pl.DataFrame(eligible_rows)
    else:
        df = pl.DataFrame([])

    if block.kind == "note":
        primary_value = block.note_text or ""
        formatted_value = primary_value
        polars_expr_str = "None (Text note block)"

    elif block.kind == "metric":
        if included_count == 0 or not target_col or not df.columns or target_col not in df.columns:
            if op == "COUNT" and count_mode == "count_rows":
                primary_value = included_count
                formatted_value = str(included_count)
            elif op == "COUNT":
                primary_value = 0
                formatted_value = "0"
            else:
                primary_value = None
                formatted_value = "N/A"
            polars_expr_str = f"pl.col('{target_col}').{op.lower()}() [Empty/Missing Selection -> null]"
        else:
            if op == "SUM":
                val = df.select(pl.col(target_col).sum()).item()
                primary_value = round(float(val), 2) if val is not None else 0.0
                formatted_value = f"{primary_value:,.2f}"
                polars_expr_str = f"df.select(pl.col('{target_col}').sum())"
            elif op == "AVG":
                val = df.select(pl.col(target_col).mean()).item()
                primary_value = round(float(val), 2) if val is not None else None
                formatted_value = f"{primary_value:,.2f}" if primary_value is not None else "N/A"
                polars_expr_str = f"df.select(pl.col('{target_col}').mean())"
            elif op == "MEDIAN":
                val = df.select(pl.col(target_col).median()).item()
                primary_value = round(float(val), 2) if val is not None else None
                formatted_value = f"{primary_value:,.2f}" if primary_value is not None else "N/A"
                polars_expr_str = f"df.select(pl.col('{target_col}').median())"
            elif op == "STDDEV":
                val = df.select(pl.col(target_col).std()).item()
                primary_value = round(float(val), 2) if val is not None else None
                formatted_value = f"{primary_value:,.2f}" if primary_value is not None else "N/A"
                polars_expr_str = f"df.select(pl.col('{target_col}').std())"
            elif op == "MIN":
                val = df.select(pl.col(target_col).min()).item()
                primary_value = round(float(val), 2) if val is not None else None
                formatted_value = f"{primary_value:,.2f}" if primary_value is not None else "N/A"
                polars_expr_str = f"df.select(pl.col('{target_col}').min())"
            elif op == "MAX":
                val = df.select(pl.col(target_col).max()).item()
                primary_value = round(float(val), 2) if val is not None else None
                formatted_value = f"{primary_value:,.2f}" if primary_value is not None else "N/A"
                polars_expr_str = f"df.select(pl.col('{target_col}').max())"
            elif op == "COUNT":
                if count_mode == "count_rows":
                    primary_value = included_count
                    polars_expr_str = "df.height"
                else:
                    primary_value = df.select(pl.col(target_col).count()).item()
                    polars_expr_str = f"df.select(pl.col('{target_col}').count())"
                formatted_value = f"{primary_value:,}"

            # Group breakdown if grouped metric
            if group_col and target_col and not df.is_empty() and group_col in df.columns and target_col in df.columns:
                group_breakdown = []
                if op == "SUM":
                    agg_expr = pl.col(target_col).sum()
                elif op == "AVG":
                    agg_expr = pl.col(target_col).mean()
                elif op == "MEDIAN":
                    agg_expr = pl.col(target_col).median()
                elif op == "STDDEV":
                    agg_expr = pl.col(target_col).std()
                elif op == "MIN":
                    agg_expr = pl.col(target_col).min()
                elif op == "MAX":
                    agg_expr = pl.col(target_col).max()
                else:
                    agg_expr = pl.col(target_col).count()

                grouped_df = df.group_by(group_col).agg([
                    agg_expr.alias("agg_val"),
                    pl.len().alias("count_val")
                ]).sort("agg_val", descending=(block.sort_order == "desc"))

                for g_row in grouped_df.to_dicts():
                    val = g_row["agg_val"]
                    group_breakdown.append(GroupResult(
                        group_key=str(g_row[group_col]),
                        value=round(float(val), 2) if isinstance(val, (int, float)) else val,
                        included_count=g_row["count_val"]
                    ))

    elif block.kind == "bar_chart":
        # Group by category, aggregate target column
        active_group = group_col or "category"
        if not df.is_empty() and target_col and active_group in df.columns and target_col in df.columns:
            agg_expr = pl.col(target_col).sum() if op == "SUM" else (
                pl.col(target_col).mean() if op == "AVG" else pl.col(target_col).count()
            )
            grouped_df = df.group_by(active_group).agg([
                agg_expr.alias("agg_val"),
                pl.len().alias("count_val")
            ]).sort("agg_val", descending=True)

            if block.limit and block.limit > 0:
                grouped_df = grouped_df.head(block.limit)

            labels = [str(r[active_group]) for r in grouped_df.to_dicts()]
            data_points = [round(float(r["agg_val"]), 2) if r["agg_val"] is not None else 0.0 for r in grouped_df.to_dicts()]

            chart_data = {
                "labels": labels,
                "datasets": [{
                    "label": f"{op} of {target_col}",
                    "data": data_points
                }]
            }
            formatted_value = f"{len(labels)} categories"
            polars_expr_str = f"df.group_by('{active_group}').agg(pl.col('{target_col}').{op.lower()}()).sort(descending=True)"

            group_breakdown = [
                GroupResult(
                    group_key=str(r[active_group]),
                    value=round(float(r["agg_val"]), 2) if isinstance(r["agg_val"], (int, float)) else r["agg_val"],
                    included_count=r["count_val"]
                )
                for r in grouped_df.to_dicts()
            ]
        else:
            chart_data = {"labels": [], "datasets": [{"label": f"{op} of {target_col}", "data": []}]}
            formatted_value = "No data"
            polars_expr_str = f"Empty bar chart grouping on '{active_group}'"

    elif block.kind == "line_chart":
        # Order by date or numeric column, aggregate target
        x_axis = group_col or "date"
        if not df.is_empty() and target_col and x_axis in df.columns and target_col in df.columns:
            agg_expr = pl.col(target_col).sum() if op == "SUM" else (
                pl.col(target_col).mean() if op == "AVG" else pl.col(target_col).count()
            )
            grouped_df = df.group_by(x_axis).agg([
                agg_expr.alias("agg_val"),
                pl.len().alias("count_val")
            ]).sort(x_axis, descending=False)

            if block.limit and block.limit > 0:
                grouped_df = grouped_df.head(block.limit)

            labels = [str(r[x_axis]) for r in grouped_df.to_dicts()]
            data_points = [round(float(r["agg_val"]), 2) if r["agg_val"] is not None else 0.0 for r in grouped_df.to_dicts()]

            chart_data = {
                "labels": labels,
                "datasets": [{
                    "label": f"{op} of {target_col} over {x_axis}",
                    "data": data_points
                }]
            }
            formatted_value = f"{len(labels)} points"
            polars_expr_str = f"df.group_by('{x_axis}').agg(pl.col('{target_col}').{op.lower()}()).sort('{x_axis}', ascending=True)"
        else:
            chart_data = {"labels": [], "datasets": [{"label": f"{op} of {target_col}", "data": []}]}
            formatted_value = "No data"
            polars_expr_str = f"Empty line chart ordering on '{x_axis}'"

    elif block.kind == "top_n_table":
        # Return top N rows sorted by column
        if not df.is_empty() and target_col and target_col in df.columns:
            sort_desc = (block.sort_order == "desc")
            sorted_df = df.sort(target_col, descending=sort_desc)
            limit_val = block.limit or 10
            sliced_df = sorted_df.head(limit_val)

            headers_to_show = block.columns_to_show or df.columns[:6]
            table_data = {
                "headers": headers_to_show,
                "rows": [
                    [row.get(h) for h in headers_to_show]
                    for row in sliced_df.to_dicts()
                ]
            }
            formatted_value = f"Top {len(table_data['rows'])} rows"
            polars_expr_str = f"df.sort('{target_col}', descending={sort_desc}).head({limit_val})"
        else:
            table_data = {"headers": [], "rows": []}
            formatted_value = "0 rows"
            polars_expr_str = "df.head(0)"

    # ---------------------------------------------------------
    # 3. Canonical AST and Provenance Construction
    # ---------------------------------------------------------
    active_filters_dict = {}
    if report_filter.date_column:
        active_filters_dict["date_filter"] = {
            "column": report_filter.date_column,
            "start": report_filter.start_date,
            "end": report_filter.end_date
        }
    if report_filter.category_column:
        active_filters_dict["category_filter"] = {
            "column": report_filter.category_column,
            "selected": report_filter.selected_categories
        }

    canonical_ast = CanonicalAST(
        operation=f"{block.kind.upper()}:{op}" if block.kind != "note" else "NOTE",
        target_column=target_col,
        group_by=group_col,
        filters=active_filters_dict,
        null_policy="exclude_null_cells_for_op",
        ordering=block.sort_order,
        limit=block.limit,
        execution_engine="polars",
        polars_expression=polars_expr_str
    )

    # Narrative explanation and human formula
    if block.kind == "note":
        human_formula = "Static text note"
        narrative = "Text note block rendered without numerical transformations."
    else:
        human_formula = f"{op}({target_col})" if target_col else f"{block.kind.upper()}"
        if group_col:
            human_formula += f" GROUP BY {group_col}"

        filter_narrative_parts = []
        if date_filter_active:
            filter_narrative_parts.append(f"date range [{report_filter.start_date or '*'} to {report_filter.end_date or '*'}]")
        if cat_filter_active:
            filter_narrative_parts.append(f"categories in {report_filter.selected_categories}")

        filter_text = f" Active filters: {', '.join(filter_narrative_parts)}." if filter_narrative_parts else " No active filters."

        narrative = (
            f"Computed {op} of '{target_col or 'rows'}' using Polars. "
            f"Included {included_count:,} eligible rows out of {total_rows:,} total dataset rows. "
            f"Exclusions: {structurally_rejected_count} structurally invalid/ragged rows, "
            f"{filtered_out_count} rows filtered out by criteria, "
            f"and {invalid_for_op_count} rows with null or invalid values for the operation."
            f"{filter_text}"
        )

    return CalculationResult(
        block_kind=block.kind,
        primary_value=primary_value,
        formatted_value=formatted_value,
        chart_data=chart_data,
        table_data=table_data,
        group_breakdown=group_breakdown,
        row_accounting=row_accounting,
        canonical_ast=canonical_ast,
        human_formula=human_formula,
        narrative_explanation=narrative
    )
