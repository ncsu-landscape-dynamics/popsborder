# © 2026 The Johns Hopkins University Applied Physics Laboratory LLC

import math
from pathlib import Path
from typing import Optional

from gui.runtime_warnings import suppress_optional_dependency_warnings

suppress_optional_dependency_warnings()

import pandas as pd
import altair as alt
import numpy as np
import streamlit as st

from gui.models import init_state
from gui.navigation import render_sidebar_navigation
from gui.page_styles import (
    apply_shared_page_styles,
    render_labeled_help,
    render_metric_card,
    render_page_intro,
    render_section_header,
)
from gui.report_export import build_run_report_docx_bytes
from gui.slippage_ui import get_slippage_state, run_pipeline, set_engine_options
from gui.slippage_pipeline import create_default_paths


st.set_page_config(
    page_title="Run Simulation",
    page_icon=":arrow_forward:",
    layout="wide",
)
init_state()

state = get_slippage_state()
render_sidebar_navigation()
apply_shared_page_styles()
engine_options = state["engine_options"]
run_error = state.get("run_error")
paths = state["paths"]
TMP_DIR = Path("tmp")
MIN_REPLICATIONS_FOR_INTERVAL = 5


def _latest_output_run_dir(experiment_dir: Optional[Path]) -> Optional[Path]:
    """Return the latest output_* directory under an experiment directory.

    Args:
        experiment_dir: Experiment directory containing one or more
            ``output_*`` subdirectories.

    Returns:
        Path to the most recently modified output directory, or None.
    """
    if experiment_dir is None or not experiment_dir.exists():
        return None
    candidates = [p for p in experiment_dir.glob("output_*") if p.is_dir()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _load_all_runs_df(output_dir: Optional[Path]) -> Optional[pd.DataFrame]:
    """Load per-replication summary CSV from a run output directory.

    Args:
        output_dir: Output directory produced by a run.

    Returns:
        DataFrame from ``all_runs.csv`` or None if not found/invalid.
    """
    if output_dir is None:
        return None
    all_runs_path = output_dir / "all_runs.csv"
    if not all_runs_path.exists():
        return None
    try:
        return pd.read_csv(all_runs_path)
    except Exception:  # pylint: disable=broad-except
        return None


def _load_scenario_table_df(output_dir: Optional[Path]) -> Optional[pd.DataFrame]:
    """Load the scenario_table.csv associated with an output directory.

    Args:
        output_dir: Output directory produced by a run.

    Returns:
        Scenario table DataFrame or None if not found/invalid.
    """
    if output_dir is None:
        return None
    scenario_table_path = output_dir.parent / "scenario_table.csv"
    if not scenario_table_path.exists():
        return None
    try:
        return pd.read_csv(scenario_table_path)
    except Exception:  # pylint: disable=broad-except
        return None


def _load_inspection_action_runs_df(output_dir: Optional[Path]) -> Optional[pd.DataFrame]:
    """Aggregate inspection-level action metrics from synthetic result CSVs.

    This scans ``output_dir`` for CSVs named
    ``synthetic_commodity_line_results_data.csv`` under each scenario/rep
    and derives inspection- and consignment-level action counts.

    Args:
        output_dir: Output directory produced by a run.

    Returns:
        DataFrame with one row per (scenario, replication), or None if no
        valid records are found.
    """
    if output_dir is None or not output_dir.exists():
        return None
    records = []
    for csv_path in output_dir.glob("*/*/synthetic_commodity_line_results_data.csv"):
        try:
            scenario_name = csv_path.parent.parent.name
            rep_name = csv_path.parent.name
            replication = int(rep_name.replace("rep_", ""))
            df = pd.read_csv(csv_path)
        except Exception:  # pylint: disable=broad-except
            continue
        required_cols = {"is_infected", "is_detected"}
        if not required_cols.issubset(df.columns):
            continue
        infected = df["is_infected"].fillna(False).astype(bool)
        detected = df["is_detected"].fillna(False).astype(bool)
        inspected = df.get("was_inspected", pd.Series(False, index=df.index)).fillna(False).astype(bool)
        consignment_clean_inspected = 0
        consignment_clean_not_inspected = 0
        consignment_intercepted = 0
        consignment_slipped = 0
        if "inspection_number" in df.columns:
            consignment_df = (
                pd.DataFrame(
                    {
                        "inspection_number": df["inspection_number"],
                        "is_infected": infected,
                        "is_detected": detected,
                        "was_inspected": inspected,
                    }
                )
                .groupby("inspection_number", dropna=False)
                .agg(
                    is_infected=("is_infected", "any"),
                    is_detected=("is_detected", "any"),
                    was_inspected=("was_inspected", "any"),
                )
                .reset_index()
            )
            consignment_clean_inspected = int((~consignment_df["is_infected"] & consignment_df["was_inspected"]).sum())
            consignment_clean_not_inspected = int((~consignment_df["is_infected"] & ~consignment_df["was_inspected"]).sum())
            consignment_intercepted = int((consignment_df["is_infected"] & consignment_df["is_detected"]).sum())
            consignment_slipped = int((consignment_df["is_infected"] & ~consignment_df["is_detected"]).sum())
        records.append(
            {
                "name": scenario_name,
                "replication": replication,
                "total_intercepted_inspection_units": int((infected & detected).sum()),
                "total_slipped_inspection_units": int((infected & ~detected).sum()),
                "inspection_clean_inspected": int((~infected & inspected).sum()),
                "inspection_clean_not_inspected": int((~infected & ~inspected).sum()),
                "consignment_clean_inspected": consignment_clean_inspected,
                "consignment_clean_not_inspected": consignment_clean_not_inspected,
                "consignment_intercepted": consignment_intercepted,
                "consignment_slipped": consignment_slipped,
            }
        )
    if not records:
        return None
    return pd.DataFrame(records)


def _styled_summary_table(df: pd.DataFrame, mean_columns: list[str], interval_columns: list[str]):
    """Apply styling to summary tables showing means and intervals.

    Args:
        df: DataFrame to style.
        mean_columns: Columns containing mean values to highlight.
        interval_columns: Columns containing interval strings (e.g., 95% CI).

    Returns:
        pandas Styler with custom formatting applied.
    """
    label_columns = [col for col in ["Scenario", "Level"] if col in df.columns]
    return (
        df.style
        .set_properties(
            subset=label_columns,
            **{"font-weight": "600", "color": "#1f3b63", "min-width": "120px"},
        )
        .set_properties(
            subset=[col for col in mean_columns if col in df.columns],
            **{"background-color": "#eaf3fb", "font-weight": "600", "color": "#16324f"},
        )
        .set_properties(
            subset=[col for col in interval_columns if col in df.columns],
            **{"background-color": "#f5f9fd", "color": "#355070"},
        )
    )


def _safe_float(value) -> float:
    """Safely coerce a value to float, returning 0.0 on failure/NaN."""
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except Exception:  # pylint: disable=broad-except
        return 0.0


def _format_count(value) -> str:
    """Format a numeric count with 1 decimal place and thousands separator."""
    return f"{_safe_float(value):,.1f}"


def _format_percent(value) -> str:
    """Format a numeric value as a percentage string with 2 decimals."""
    if value is None or pd.isna(value):
        return "n/a"
    return f"{_safe_float(value):.2f}%"


def _interval_text(
    lower,
    upper,
    replications: int,
    *,
    digits: int = 2,
    suffix: str = "",
) -> str:
    """Format a 95% interval string or return 'n/a' if insufficient data.

    Args:
        lower: Lower interval bound or NaN.
        upper: Upper interval bound or NaN.
        replications: Number of replications used to compute the interval.
        digits: Number of decimal digits for formatting.
        suffix: Optional suffix appended to each bound (e.g., "%").

    Returns:
        Formatted interval string or "n/a".
    """
    if pd.isna(lower) or pd.isna(upper) or replications < MIN_REPLICATIONS_FOR_INTERVAL:
        return "n/a"
    return f"{float(lower):.{digits}f}{suffix} - {float(upper):.{digits}f}{suffix}"


def _maybe_warning_for_replications(all_runs_df: Optional[pd.DataFrame]) -> bool:
    """Warn if some scenarios have too few replications for intervals.

    Args:
        all_runs_df: Per-run summary DataFrame.

    Returns:
        True if a warning was shown, False otherwise.
    """
    if all_runs_df is not None and not all_runs_df.empty and "replication" in all_runs_df.columns:
        rep_counts = all_runs_df.groupby("name").size()
        if (rep_counts < MIN_REPLICATIONS_FOR_INTERVAL).any():
            st.warning(
                f"*Uncertainty bounds are hidden for scenarios with fewer than {MIN_REPLICATIONS_FOR_INTERVAL} replications."
            )
            return True
    return False


def _unique_non_empty_values(df: Optional[pd.DataFrame], column: str) -> list[str]:
    """Get unique non-empty string values from a column.

    Args:
        df: Input DataFrame or None.
        column: Column name.

    Returns:
        Sorted list of non-empty, non-'nan' strings from the column.
    """
    if df is None or df.empty or column not in df.columns:
        return []
    values = []
    for value in df[column].dropna().tolist():
        text = str(value).strip()
        if text and text.lower() != "nan":
            values.append(text)
    return sorted(set(values))


def _format_list_preview(values: list[str], *, max_items: int = 5) -> str:
    """Summarize a list of values for display.

    Args:
        values: List of values.
        max_items: Maximum number of items to show before truncating.

    Returns:
        Comma-separated string, with an indicator if items are omitted.
    """
    if not values:
        return "n/a"
    if len(values) <= max_items:
        return ", ".join(values)
    return f"{', '.join(values[:max_items])}, +{len(values) - max_items} more"


def _format_detail_number(value) -> str:
    """Format numeric-like values in param details (including 'inf')."""
    coerced = _coerce_numeric_like(value)
    if coerced is None:
        return "n/a"
    if isinstance(coerced, float):
        if math.isinf(coerced):
            return "inf"
        return f"{coerced:.4f}"
    return str(coerced)


def _load_param_snapshot(output_dir: Optional[Path]) -> dict:
    """Load contamination parameter snapshot near a run output directory.

    Args:
        output_dir: Run output directory.

    Returns:
        Dictionary of parameter sets or an empty dict if not found/invalid.
    """
    if output_dir is None:
        return {}
    candidate_paths = [
        output_dir / "contamination_parameter_sets.json",
        output_dir.parent / "contamination_parameter_sets.json",
    ]
    snapshot_path = next((path for path in candidate_paths if path.exists()), None)
    if snapshot_path is None:
        return {}
    try:
        import json  # pylint: disable=import-outside-toplevel

        return json.loads(snapshot_path.read_text(encoding="utf-8"))
    except Exception:  # pylint: disable=broad-except
        return {}


def _coerce_numeric_like(value):
    """Coerce various string/number values into floats or normalized strings.

    Handles NaNs, 'inf', 'infinity', and numeric strings.

    Args:
        value: Arbitrary value.

    Returns:
        Float, cleaned string, or None if the value is empty/NaN.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip().lower()
    if text in {"", "nan", "none"}:
        return None
    if text in {"inf", "infinity"}:
        return float("inf")
    try:
        return float(text)
    except Exception:  # pylint: disable=broad-except
        return text


def _values_match(left, right) -> bool:
    """Compare two values, treating numeric equivalence and 'inf' robustly.

    Args:
        left: First value.
        right: Second value.

    Returns:
        True if they match within tolerance, False otherwise.
    """
    left_value = _coerce_numeric_like(left)
    right_value = _coerce_numeric_like(right)
    if left_value is None or right_value is None:
        return False
    if isinstance(left_value, float) and isinstance(right_value, float):
        if math.isinf(left_value) and math.isinf(right_value):
            return True
        return abs(left_value - right_value) < 1e-12
    return left_value == right_value


def _find_matching_param_set(param_store: dict, scenario_row: pd.Series) -> str:
    """Find the name of a parameter set that matches scenario parameters.

    Args:
        param_store: Parameter-store dictionary.
        scenario_row: Scenario row (Series) with /alpha, /beta, /theta columns.

    Returns:
        Name of the matching parameter set, or an empty string if none match.
    """
    alpha_cols = [col for col in scenario_row.index if col.endswith("/alpha")]
    beta_cols = [col for col in scenario_row.index if col.endswith("/beta")]
    theta_cols = [col for col in scenario_row.index if col.endswith("/theta")]
    p_cols = [col for col in scenario_row.index if col.endswith("/p")]
    if not alpha_cols or not beta_cols:
        return ""

    alpha_values = [scenario_row[col] for col in alpha_cols if pd.notna(scenario_row[col])]
    beta_values = [scenario_row[col] for col in beta_cols if pd.notna(scenario_row[col])]
    theta_values = [scenario_row[col] for col in theta_cols if pd.notna(scenario_row[col])]
    p_values = [scenario_row[col] for col in p_cols if pd.notna(scenario_row[col])]

    for param_name, param_value in param_store.items():
        if not isinstance(param_value, dict):
            continue
        if {"alpha", "beta"}.issubset(param_value.keys()):
            if any(_values_match(param_value.get("alpha"), value) for value in alpha_values) and any(
                _values_match(param_value.get("beta"), value) for value in beta_values
            ):
                theta_value = param_value.get("theta")
                p_value = param_value.get("p")
                theta_matches = (not theta_values) or any(_values_match(theta_value, value) for value in theta_values)
                p_matches = (not p_values) or any(_values_match(p_value, value) for value in p_values)
                if theta_matches and p_matches:
                    return str(param_name)
        elif param_value:
            nested_values = [entry for entry in param_value.values() if isinstance(entry, dict)]
            if not nested_values:
                continue
            if any(
                any(_values_match(entry.get("alpha"), value) for value in alpha_values)
                and any(_values_match(entry.get("beta"), value) for value in beta_values)
                and ((not theta_values) or any(_values_match(entry.get("theta"), value) for value in theta_values))
                and ((not p_values) or any(_values_match(entry.get("p"), value) for value in p_values))
                for entry in nested_values
            ):
                return str(param_name)
    return ""


def _format_param_details(param_store: dict, param_name: str) -> str:
    """Format contamination parameter details for display.

    Args:
        param_store: Parameter-store dictionary.
        param_name: Name of the parameter set.

    Returns:
        A human-readable description combining alpha, beta, theta,
        and average contamination rate when available.
    """
    if not param_name:
        return "n/a"
    param_value = param_store.get(param_name)
    if not isinstance(param_value, dict):
        return param_name

    if {"alpha", "beta"}.issubset(param_value.keys()):
        theta_value = param_value.get("theta")
        p_value = param_value.get("p")
        avg_rate = param_value.get("average_contamination_rate")
        if avg_rate in (None, ""):
            raw_rate = param_value.get("sample_unit_contamination_rate")
            if raw_rate not in (None, ""):
                try:
                    avg_rate = float(raw_rate) * 100.0
                except Exception:  # pylint: disable=broad-except
                    avg_rate = None
        details = [
            f"alpha={_format_detail_number(param_value.get('alpha'))}",
            f"beta={_format_detail_number(param_value.get('beta'))}",
            f"theta={_format_detail_number(theta_value)}",
        ]
        if p_value not in (None, ""):
            details.append(f"p={_format_detail_number(p_value)}")
        if avg_rate not in (None, ""):
            details.append(f"avg contamination rate={float(avg_rate):.2f}%")
        return f"{param_name} ({', '.join(details)})"

    nested_entries = [entry for entry in param_value.values() if isinstance(entry, dict)]
    if nested_entries:
        first_entry = nested_entries[0]
        theta_value = first_entry.get("theta")
        p_value = first_entry.get("p")
        avg_rate = first_entry.get("average_contamination_rate")
        if avg_rate in (None, ""):
            raw_rate = first_entry.get("mu")
            if raw_rate not in (None, ""):
                try:
                    avg_rate = float(raw_rate) * 100.0
                except Exception:  # pylint: disable=broad-except
                    avg_rate = None
        details = [
            f"alpha={_format_detail_number(first_entry.get('alpha'))}",
            f"beta={_format_detail_number(first_entry.get('beta'))}",
            f"theta={_format_detail_number(theta_value)}",
        ]
        if p_value not in (None, ""):
            details.append(f"p={_format_detail_number(p_value)}")
        if avg_rate not in (None, ""):
            details.append(f"avg contamination rate={float(avg_rate):.2f}%")
        if len(nested_entries) > 1:
            details.append(f"{len(nested_entries)} ranges")
        return f"{param_name} ({', '.join(details)})"

    return param_name


def _render_run_details(results_df: pd.DataFrame, all_runs_df: Optional[pd.DataFrame]) -> None:
    """Render a summary of the scenario setup used for the current run.

    Uses the scenario_table.csv (if available) plus the parameter store
    to show which consignment file, parameter set, and compliance policy
    were applied for each scenario.

    Args:
        results_df: Scenario-level results DataFrame from the pipeline.
        all_runs_df: Per-run DataFrame (unused here, included for signature consistency).
    """
    output_dir = Path(state["run_output_dir"]) if state.get("run_output_dir") else None
    scenario_table_path = output_dir.parent / "scenario_table.csv" if output_dir is not None else None
    param_store = _load_param_snapshot(output_dir)

    scenario_rows = []
    scenario_source = None
    if scenario_table_path is not None and scenario_table_path.exists():
        try:
            scenario_source = pd.read_csv(scenario_table_path)
        except Exception:  # pylint: disable=broad-except
            scenario_source = None
    if scenario_source is None or scenario_source.empty:
        scenario_source = results_df

    for _, row in scenario_source.iterrows():
        param_name = _find_matching_param_set(param_store, row)
        scenario_rows.append(
            {
                "Scenario label": row.get("name", "n/a"),
                "Consignment (RBS) file": Path(str(row.get("consignment/input_file/file_name", "n/a"))).name,
                "Contamination parameter set": _format_param_details(param_store, param_name),
                "RBS compliance policy name": Path(str(row.get("inspection/compliance_table/file_name", "n/a"))).name,
            }
        )

    with st.expander("Run details", expanded=False):
        render_labeled_help(
            "Run details",
            "Shows the saved Page 4 scenario setup used for the current run.",
        )
        st.dataframe(pd.DataFrame(scenario_rows), use_container_width=True, hide_index=True)


def _render_consignments_visual(
    action_results_source: pd.DataFrame,
    total_consignments,
    inspection_action_runs_df: Optional[pd.DataFrame] = None,
    statistic_label: str = "Mean",
    record_agg: str = "mean",
) -> None:
    """Render stacked bar charts of action outcomes by level and scenario.

    Levels include Consignment, Inspection (if available), Sample (if
    available), and Plant.

    Args:
        action_results_source: DataFrame with scenario-level metrics.
        total_consignments: Total consignments per replication (for derived metrics).
        inspection_action_runs_df: Optional record-level action DataFrame.
        statistic_label: Label describing the aggregation (e.g., "Mean").
        record_agg: Aggregation method for record-level metrics (e.g., "mean").
    """
    render_labeled_help(
        "Simulation summary",
        f"Shows the {statistic_label.lower()} percentage of clean inspected, clean not inspected, intercepted, and slipped items across consignment, inspection, sample, and plant levels for each scenario.",
    )
    record_level_summary = None
    if inspection_action_runs_df is not None and not inspection_action_runs_df.empty:
        record_level_summary = (
            inspection_action_runs_df.groupby("name")
            .agg(
                consignment_clean_inspected=("consignment_clean_inspected", record_agg),
                consignment_clean_not_inspected=("consignment_clean_not_inspected", record_agg),
                consignment_intercepted=("consignment_intercepted", record_agg),
                consignment_slipped=("consignment_slipped", record_agg),
                inspection_clean_inspected=("inspection_clean_inspected", record_agg),
                inspection_clean_not_inspected=("inspection_clean_not_inspected", record_agg),
                total_intercepted_inspection_units=("total_intercepted_inspection_units", record_agg),
                total_slipped_inspection_units=("total_slipped_inspection_units", record_agg),
            )
            .reset_index()
        )
    action_visual_rows = []
    has_inspection_level = {
        "total_intercepted_inspection_units",
        "total_slipped_inspection_units",
    }.issubset(action_results_source.columns)
    has_sample_level = {
        "total_contaminated_sample_units",
        "total_slipped_sample_units",
        "avg_sample_units_inspected_completion",
        "num_sample_units",
    }.issubset(action_results_source.columns)
    for _, selected_row in action_results_source.iterrows():
        record_row = None
        if record_level_summary is not None:
            record_matches = record_level_summary[record_level_summary["name"] == selected_row["name"]]
            if not record_matches.empty:
                record_row = record_matches.iloc[0]

        consignment_clean_inspected = (
            _safe_float(record_row["consignment_clean_inspected"])
            if record_row is not None
            else max(
                _safe_float(selected_row["num_inspections"]) - _safe_float(selected_row["intercepted"]) - _safe_float(selected_row["false_neg"]),
                0.0,
            )
        )
        consignment_clean_not_inspected = (
            _safe_float(record_row["consignment_clean_not_inspected"])
            if record_row is not None
            else (max(_safe_float(total_consignments) - _safe_float(selected_row["num_inspections"]), 0.0) if total_consignments is not None else 0.0)
        )
        consignment_intercepted = (
            _safe_float(record_row["consignment_intercepted"])
            if record_row is not None
            else _safe_float(selected_row["intercepted"])
        )
        consignment_slipped = (
            _safe_float(record_row["consignment_slipped"])
            if record_row is not None
            else _safe_float(selected_row["false_neg"])
        )
        action_visual_rows.append(
            {
                "Scenario": selected_row["name"],
                "Level": "Consignment",
                "Clean inspected": consignment_clean_inspected,
                "Clean not inspected": consignment_clean_not_inspected,
                "Intercepted": consignment_intercepted,
                "Slipped": consignment_slipped,
            }
        )
        if has_inspection_level:
            inspection_clean_inspected = (
                _safe_float(record_row["inspection_clean_inspected"])
                if record_row is not None
                else max(
                    _safe_float(selected_row["avg_inspection_units_opened_completion"])
                    - _safe_float(selected_row.get("total_intercepted_inspection_units", 0.0)),
                    0.0,
                )
            )
            inspection_clean_not_inspected = (
                _safe_float(record_row["inspection_clean_not_inspected"])
                if record_row is not None
                else max(
                    _safe_float(selected_row["num_inspection_units"])
                    - _safe_float(selected_row.get("total_slipped_inspection_units", 0.0))
                    - _safe_float(selected_row.get("total_intercepted_inspection_units", 0.0))
                    - inspection_clean_inspected,
                    0.0,
                )
            )
            action_visual_rows.append(
                {
                    "Scenario": selected_row["name"],
                    "Level": "Inspection",
                    "Clean inspected": inspection_clean_inspected,
                    "Clean not inspected": inspection_clean_not_inspected,
                    "Intercepted": (
                        _safe_float(record_row["total_intercepted_inspection_units"])
                        if record_row is not None
                        else _safe_float(selected_row.get("total_intercepted_inspection_units", 0.0))
                    ),
                    "Slipped": (
                        _safe_float(record_row["total_slipped_inspection_units"])
                        if record_row is not None
                        else _safe_float(selected_row.get("total_slipped_inspection_units", 0.0))
                    ),
                }
            )
        if has_sample_level:
            sample_clean_inspected = max(
                _safe_float(selected_row["avg_sample_units_inspected_completion"])
                - max(
                    _safe_float(selected_row["total_contaminated_sample_units"])
                    - _safe_float(selected_row.get("total_slipped_sample_units", 0.0)),
                    0.0,
                ),
                0.0,
            )
            sample_clean_not_inspected = max(
                _safe_float(selected_row["num_sample_units"])
                - _safe_float(selected_row["total_contaminated_sample_units"])
                - sample_clean_inspected,
                0.0,
            )
            action_visual_rows.append(
                {
                    "Scenario": selected_row["name"],
                    "Level": "Sample",
                    "Clean inspected": sample_clean_inspected,
                    "Clean not inspected": sample_clean_not_inspected,
                    "Intercepted": max(
                        _safe_float(selected_row["total_contaminated_sample_units"])
                        - _safe_float(selected_row.get("total_slipped_sample_units", 0.0)),
                        0.0,
                    ),
                    "Slipped": _safe_float(selected_row.get("total_slipped_sample_units", 0.0)),
                }
            )
        action_visual_rows.append(
            {
                "Scenario": selected_row["name"],
                "Level": "Plant",
                "Clean inspected": max(
                    _safe_float(selected_row["avg_plant_units_inspected_completion"])
                    - max(
                        _safe_float(selected_row["total_contaminated_units"]) - _safe_float(selected_row["total_slipped_units"]),
                        0.0,
                    ),
                    0.0,
                ),
                "Clean not inspected": max(
                    _safe_float(selected_row["num_plants"])
                    - _safe_float(selected_row["total_contaminated_units"])
                    - max(
                        _safe_float(selected_row["avg_plant_units_inspected_completion"])
                        - max(
                            _safe_float(selected_row["total_contaminated_units"]) - _safe_float(selected_row["total_slipped_units"]),
                            0.0,
                        ),
                        0.0,
                    ),
                    0.0,
                ),
                "Intercepted": max(
                    _safe_float(selected_row["total_contaminated_units"]) - _safe_float(selected_row["total_slipped_units"]),
                    0.0,
                ),
                "Slipped": _safe_float(selected_row["total_slipped_units"]),
            }
        )
    if not action_visual_rows:
        return
    action_mix_chart_df = pd.DataFrame(action_visual_rows)
    level_order = ["Consignment", "Inspection", "Sample", "Plant"]
    available_levels = [level for level in level_order if level in set(action_mix_chart_df["Level"])]
    for scenario_name in action_mix_chart_df["Scenario"].dropna().unique().tolist():
        scenario_chart_df = action_mix_chart_df[action_mix_chart_df["Scenario"] == scenario_name].copy()
        scenario_chart_df = scenario_chart_df[scenario_chart_df["Level"].isin(available_levels)]
        scenario_chart_df = scenario_chart_df.melt(
            id_vars=["Scenario", "Level"],
            value_vars=["Clean inspected", "Clean not inspected", "Intercepted", "Slipped"],
            var_name="Status",
            value_name="Count",
        )
        totals_by_level = scenario_chart_df.groupby("Level")["Count"].transform("sum")
        scenario_chart_df["Percent"] = np.where(
            totals_by_level > 0,
            (scenario_chart_df["Count"] / totals_by_level) * 100.0,
            0.0,
        )
        scenario_chart_df["Status order"] = scenario_chart_df["Status"].map(
            {
                "Slipped": 0,
                "Intercepted": 1,
                "Clean inspected": 2,
                "Clean not inspected": 3,
            }
        )
        st.caption(scenario_name)
        chart_height = max(280, 75 * len(available_levels))
        action_mix_chart = (
            alt.Chart(scenario_chart_df)
            .mark_bar()
            .encode(
                y=alt.Y(
                    "Level:N",
                    sort=available_levels,
                    title=None,
                    scale=alt.Scale(domain=available_levels),
                    axis=alt.Axis(labelLimit=200, labelPadding=12),
                ),
                x=alt.X(
                    "Percent:Q",
                    stack="zero",
                    title="Percent of level",
                    scale=alt.Scale(domain=[0, 100]),
                ),
                color=alt.Color(
                    "Status:N",
                    scale=alt.Scale(
                        domain=["Slipped", "Intercepted", "Clean inspected", "Clean not inspected"],
                        range=["#de2d26", "#2b8cbe", "#d9e2ec", "#9fb3c8"],
                    ),
                    legend=alt.Legend(title=None, orient="bottom"),
                ),
                order=alt.Order("Status order:Q", sort="ascending"),
                tooltip=[
                    "Scenario",
                    "Level",
                    "Status",
                    alt.Tooltip("Percent:Q", title="Percent of level", format=".1f"),
                    alt.Tooltip("Count:Q", title="Mean count", format=".1f"),
                ],
            )
            .properties(height=chart_height, width="container")
            .configure_view(stroke=None)
        )
        st.altair_chart(action_mix_chart, use_container_width=True)


st.warning(
    "**Test Deployment Notice: This is a test deployment with limited functionality and is under active development. "
    "Features may be incomplete and subject to change. Results have not been validated.**"
)
st.title("Page 5 - Run Simulation")
render_page_intro("Execute the slippage pipeline and compare policies based on slippage metrics.")

selected_experiment = None
with st.sidebar:
    st.subheader("Execution options")
    st.write("Choose the replication count and pick which saved experiment package to run.")
    simulations = st.number_input(
        "Simulation replications",
        min_value=1,
        max_value=500,
        value=int(engine_options.get("num_simulations", 1)),
        step=1,
    )
    if simulations != engine_options.get("num_simulations"):
        set_engine_options(num_simulations=int(simulations))

    experiment_sets = sorted(Path("tmp/experiments").glob("*/scenario_table.csv"))
    if experiment_sets:
        labels = [p.parent.name for p in experiment_sets]
        selected_label = st.selectbox("Experiment to run", labels, index=0)
        selected_experiment = dict(zip(labels, experiment_sets)).get(selected_label)
        if selected_experiment:
            try:
                scenario_df = pd.read_csv(selected_experiment)
                state["scenario_df"] = scenario_df
                state["paths"] = state["paths"].__class__(**{**state["paths"].__dict__, "scenario_table": selected_experiment})
                st.caption(f"Loaded experiment: {selected_experiment}")
       
            except Exception as exc:  # pylint: disable=broad-except
                st.warning(f"Unable to load selected experiment: {exc}")
    else:
        st.info("No experiments saved yet on Page 4.")
    st.divider()
    run_button_placeholder = st.empty()

    def _render_run_button() -> bool:
        run_in_progress = bool(st.session_state.get("_run_pipeline_in_progress", False))
        awaiting_results_display = bool(st.session_state.get("_awaiting_results_display", False))
        has_completed_run = bool(state.get("run_output_dir") or state.get("run_output_files"))
        if run_in_progress or awaiting_results_display:
            run_button_placeholder.markdown(
                """
                <div style="
                    width: 100%;
                    padding: 0.65rem 1rem;
                    border-radius: 0.5rem;
                    background: rgba(151, 166, 195, 0.35);
                    color: rgba(44, 62, 80, 0.85);
                    text-align: center;
                    font-weight: 600;
                    cursor: not-allowed;
                    user-select: none;
                ">
                    Running experiment...
                </div>
                """,
                unsafe_allow_html=True,
            )
            return False

        run_label = "Rerun experiment" if has_completed_run else "Run experiment"
        with run_button_placeholder.container():
            return st.button(
                run_label,
                use_container_width=True,
                disabled=not experiment_sets,
                key="run_experiment_button",
            )

    if _render_run_button():
        # Defer execution to main pane to show spinner there
        state["run_request_experiment"] = selected_experiment.parent if selected_experiment else None
        st.session_state["_run_pipeline_in_progress"] = True
        st.session_state["_awaiting_results_display"] = True
        st.session_state["_trigger_run_pipeline"] = True
        st.rerun()

# Main-pane run handler with spinner
run_placeholder = st.empty()
if st.session_state.get("_trigger_run_pipeline"):
    st.session_state["_trigger_run_pipeline"] = False
    exp_dir = state.pop("run_request_experiment", None)
    with run_placeholder.container():
        progress_status = st.markdown("**Starting simulation**")
        progress_percent = st.markdown("### **0%**")
        overall_progress_bar = st.progress(0)
        last_progress_details = {}

        def _update_progress(percent: int, message: str, details: Optional[dict] = None) -> None:
            safe_percent = max(0, min(100, int(percent)))
            details = details or {}
            last_progress_details.clear()
            last_progress_details.update(details)
            replications_completed = int(details.get("replications_completed", 0) or 0)
            replications_total = int(details.get("replications_total", 0) or 0)
            shipments_processed = int(details.get("shipments_processed", 0) or 0)
            shipments_total = int(details.get("shipments_total", 0) or 0)
            progress_label = f"{message} ({safe_percent}%)"
            if replications_total > 0 or shipments_total > 0:
                progress_parts = []
                if replications_total > 0:
                    progress_parts.append(
                        f"Replications {replications_completed:,}/{replications_total:,}"
                    )
                if shipments_total > 0:
                    progress_parts.append(
                        f"Consignments {shipments_processed:,}/{shipments_total:,}"
                    )
                progress_label = f"{message} | {' | '.join(progress_parts)}"
            overall_progress_bar.progress(safe_percent)
            progress_status.markdown(f"**{progress_label}**")
            progress_percent.markdown(f"### **{safe_percent}%**")

        try:
            st.info(f"Running experiment at: {exp_dir}")
            _update_progress(0, "Starting simulation", {})
            results = run_pipeline(exp_dir, progress_callback=_update_progress)
            state["run_error"] = None
            state.pop("run_error_message", None)
            _update_progress(100, "Simulation complete", last_progress_details)
            st.success("Pipeline finished.")
        except Exception as exc:  # pylint: disable=broad-except
            state["run_error"] = exc
            detail = getattr(exc, "stderr", None) or getattr(exc, "output", None)
            state["run_error_message"] = f"{exc}\n{detail}" if detail else str(exc)
            failure_label = "Simulation failed (100%)"
            if last_progress_details:
                replications_completed = int(last_progress_details.get("replications_completed", 0) or 0)
                replications_total = int(last_progress_details.get("replications_total", 0) or 0)
                shipments_processed = int(last_progress_details.get("shipments_processed", 0) or 0)
                shipments_total = int(last_progress_details.get("shipments_total", 0) or 0)
                progress_parts = []
                if replications_total > 0:
                    progress_parts.append(f"Replications {replications_completed:,}/{replications_total:,}")
                if shipments_total > 0:
                    progress_parts.append(f"Consignments {shipments_processed:,}/{shipments_total:,}")
                if progress_parts:
                    failure_label = f"Simulation failed | {' | '.join(progress_parts)}"
            overall_progress_bar.progress(100)
            progress_status.markdown(f"**{failure_label}**")
            progress_percent.markdown("### **100%**")
        finally:
            st.session_state["_run_pipeline_in_progress"] = False
        _render_run_button()

if run_error:
    msg = state.get("run_error_message") or str(run_error)
    st.error("Pipeline failed")
    st.code(msg, language="text")
    st.caption(
        "Common fixes: confirm the selected experiment folder has a scenario_table.csv with non-empty inspection fields, "
        "RBS data in tmp/consignments, and PIS action data on Page 2. Check the full message above for the failing file."
    )
    # Surface current paths to help debugging
    paths_obj = state.get("paths")
    st.write(
        {
            "scenario_table": str(paths_obj.scenario_table) if paths_obj else None,
            "rbs_data": str(getattr(paths_obj, "rbs_data", None)) if paths_obj else None,
            "compliance_lookup": str(getattr(paths_obj, "compliance_lookup", None)) if paths_obj else None,
            "config": str(getattr(paths_obj, "config", None)) if paths_obj else None,
            "num_consignments": state.get("num_consignments"),
        }
    )

results_df = state.get("results")

if results_df is None or results_df.empty:
    st.info("Run the pipeline to generate scenario results.")
    st.stop()

saved_output_files = state.get("run_output_files") or []
selected_experiment_dir = selected_experiment.parent if selected_experiment else None
latest_output_dir = _latest_output_run_dir(selected_experiment_dir)
all_runs_df = _load_all_runs_df(latest_output_dir)
scenario_table_df = _load_scenario_table_df(latest_output_dir)
inspection_action_runs_df = _load_inspection_action_runs_df(latest_output_dir)
saved_output_dir = state.get("run_output_dir")
if latest_output_dir is not None:
    saved_output_dir = str(latest_output_dir)
    latest_output_files = sorted(p for p in latest_output_dir.glob("*.csv") if p.is_file())
    if latest_output_files:
        saved_output_files = [str(path) for path in latest_output_files]
if saved_output_dir:
    output_dir_path = Path(saved_output_dir)
    output_file_names = ", ".join(Path(path).name for path in saved_output_files) if saved_output_files else "none"
    st.caption(
        f"Latest output: `{output_dir_path.name}` in `tmp/experiments/{output_dir_path.parent.parent.name}`. "
        f"Files: {output_file_names}."
    )
    try:
        report_bytes = build_run_report_docx_bytes(
            results_df=results_df,
            all_runs_df=all_runs_df,
            scenario_table_df=scenario_table_df,
            inspection_action_runs_df=inspection_action_runs_df,
            metadata={
                "experiment": output_dir_path.parent.name,
                "output_dir": str(output_dir_path),
            },
        )
        st.download_button(
            "Download Run Report (.docx)",
            data=report_bytes,
            file_name=f"{output_dir_path.parent.name}_run_report.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            type="primary",
        )
    except ImportError:
        st.info("Word report export is currently unavailable.")
    except Exception as exc:  # pylint: disable=broad-except
        st.warning(f"Unable to build run report: {exc}")

_render_run_details(results_df, all_runs_df)

render_labeled_help(
    "Run summary",
    "Summarizes how many scenarios were run, the total inspections performed, and the mean slipped plant units aggregated across the scenario results.",
)
summary = results_df.copy()
scenario_count = len(summary)
total_inspections = int(summary["num_inspections"].sum()) if "num_inspections" in summary.columns else 0
shipments_per_replication = int(state.get("num_consignments") or 0)

kpi_cols = st.columns(5)
replications_per_scenario = 0
if all_runs_df is not None and "replication" in all_runs_df.columns:
    replications_per_scenario = int(all_runs_df.groupby("name")["replication"].nunique().min())
elif state.get("engine_options", {}).get("num_simulations") is not None:
    replications_per_scenario = int(state["engine_options"]["num_simulations"])
total_shipments_run = scenario_count * replications_per_scenario * shipments_per_replication if shipments_per_replication else 0
with kpi_cols[0]:
    render_metric_card("Scenarios", f"{len(summary):,}", "Number of scenarios included in the current results.")
with kpi_cols[1]:
    render_metric_card(
        "Replications per scenario",
        f"{replications_per_scenario:,}",
        "Number of simulation replications used for each scenario in the current results.",
    )
with kpi_cols[2]:
    render_metric_card(
        "Consignments per replication",
        f"{shipments_per_replication:,}",
        "Configured number of consignments processed in each replication.",
    )
with kpi_cols[3]:
    render_metric_card(
        "Inspected consignments",
        f"{total_inspections:,}",
        "Total number of consignments inspected across the displayed scenario results.",
    )
with kpi_cols[4]:
    render_metric_card(
        "Total shipments run",
        f"{total_shipments_run:,}",
        "Estimated total consignments processed across all scenarios and replications.",
    )

simulation_summary_source = results_df.copy()
if inspection_action_runs_df is not None and not {
    "total_intercepted_inspection_units",
    "total_slipped_inspection_units",
}.issubset(simulation_summary_source.columns):
    inspection_summary_df = (
        inspection_action_runs_df.groupby("name")
        .agg(
            total_intercepted_inspection_units=("total_intercepted_inspection_units", "mean"),
            total_slipped_inspection_units=("total_slipped_inspection_units", "mean"),
        )
        .reset_index()
    )
    simulation_summary_source = simulation_summary_source.merge(inspection_summary_df, on="name", how="left")
if all_runs_df is not None and "total_slipped_sample_units" in all_runs_df.columns and "total_slipped_sample_units" not in simulation_summary_source.columns:
    sample_summary_df = (
        all_runs_df.groupby("name")
        .agg(total_slipped_sample_units=("total_slipped_sample_units", "mean"))
        .reset_index()
    )
    simulation_summary_source = simulation_summary_source.merge(sample_summary_df, on="name", how="left")

simulation_summary_record_runs = inspection_action_runs_df.copy() if inspection_action_runs_df is not None else None
simulation_summary_runs_source = all_runs_df.copy() if all_runs_df is not None else None
if simulation_summary_runs_source is not None and simulation_summary_record_runs is not None and not {
    "total_intercepted_inspection_units",
    "total_slipped_inspection_units",
}.issubset(simulation_summary_runs_source.columns):
    simulation_summary_runs_source = simulation_summary_runs_source.merge(
        simulation_summary_record_runs[
            [
                "name",
                "replication",
                "total_intercepted_inspection_units",
                "total_slipped_inspection_units",
            ]
        ],
        on=["name", "replication"],
        how="left",
    )


st.header("Results Summary")
st.write("Review the scenario-level results, progress details, and aggregated slippage outcomes from the completed run.")
expand_all_summary_sections = st.toggle(
    "Expand all sections",
    value=False,
    key="expand_all_summary_sections",
)
simulation_summary_view = "Mean"
simulation_summary_record_agg = "mean"
if simulation_summary_runs_source is not None and not simulation_summary_runs_source.empty and "replication" in simulation_summary_runs_source.columns:
    available_replications = sorted(
        int(replication)
        for replication in simulation_summary_runs_source["replication"].dropna().unique().tolist()
    )
    summary_view_options = ["Mean", "Median"] + [f"Replication {replication + 1}" for replication in available_replications]
    render_labeled_help(
        "Simulation summary view",
        "Choose whether the summary uses scenario means, scenario medians, or the results from one replication only.",
    )
    simulation_summary_view = st.selectbox(
        "Simulation summary view",
        options=summary_view_options,
        key="simulation_summary_view",
        label_visibility="collapsed",
    )
    if simulation_summary_view == "Mean":
        numeric_cols = simulation_summary_runs_source.select_dtypes(include=[np.number]).columns.tolist()
        simulation_summary_source = (
            simulation_summary_runs_source.groupby("name")[numeric_cols].mean().reset_index()
        )
        simulation_summary_record_agg = "mean"
    elif simulation_summary_view == "Median":
        numeric_cols = simulation_summary_runs_source.select_dtypes(include=[np.number]).columns.tolist()
        simulation_summary_source = (
            simulation_summary_runs_source.groupby("name")[numeric_cols].median().reset_index()
        )
        simulation_summary_record_agg = "median"
    else:
        selected_replication = int(simulation_summary_view.replace("Replication ", "")) - 1
        simulation_summary_source = simulation_summary_runs_source[
            simulation_summary_runs_source["replication"] == selected_replication
        ].copy()
        if simulation_summary_record_runs is not None:
            simulation_summary_record_runs = simulation_summary_record_runs[
                simulation_summary_record_runs["replication"] == selected_replication
            ].copy()
        simulation_summary_record_agg = "mean"

if all(
    col in simulation_summary_source.columns
    for col in [
        "name",
        "intercepted",
        "false_neg",
        "num_inspections",
        "num_plants",
        "num_sample_units",
        "num_inspection_units",
        "avg_inspection_units_opened_completion",
        "avg_sample_units_inspected_completion",
        "avg_plant_units_inspected_completion",
        "total_contaminated_units",
        "total_slipped_units",
        "total_contaminated_sample_units",
    ]
):
    _render_consignments_visual(
        simulation_summary_source,
        state.get("num_consignments"),
        simulation_summary_record_runs,
        statistic_label=simulation_summary_view,
        record_agg=simulation_summary_record_agg,
    )

with st.expander("Slippage Level", expanded=expand_all_summary_sections):

    # Slippage across scenarios (contaminated plant units that slipped)
    if "total_slipped_units" in results_df.columns and "name" in results_df.columns:
        render_labeled_help(
            "Slippage by scenario",
            f"Bars show the mean number of contaminated plant units missed for each scenario across simulation replications. When at least {MIN_REPLICATIONS_FOR_INTERVAL} replications are available, error bars show the 2.5%-97.5% quantile range across replications within that same scenario.",
        )
        slip_df = results_df[["name", "total_slipped_units"]]
        slip_chart = (
            alt.Chart(slip_df)
            .mark_bar(color="#1f77b4")
            .encode(
                y=alt.Y("name:N", title="Scenario"),
                x=alt.X("total_slipped_units:Q", title="Slipped plant units"),
                tooltip=[
                    "name",
                    alt.Tooltip("total_slipped_units:Q", title="Slipped plant units", format=".2f"),
                ],
            )
        )
        if all_runs_df is not None and {"name", "total_slipped_units"}.issubset(all_runs_df.columns):
            slip_interval_df = (
                all_runs_df[["name", "total_slipped_units"]]
                .dropna()
                .groupby("name")["total_slipped_units"]
                .agg(
                    lower=lambda s: s.quantile(0.025),
                    upper=lambda s: s.quantile(0.975),
                    n="size",
                )
                .reset_index()
            )
            slip_interval_df = slip_interval_df[slip_interval_df["n"] >= MIN_REPLICATIONS_FOR_INTERVAL]
            if not slip_interval_df.empty:
                slip_error_bars = (
                    alt.Chart(slip_interval_df)
                    .mark_errorbar(color="#08306b", ticks=True)
                    .encode(
                        y=alt.Y("name:N", title="Scenario"),
                        x=alt.X("lower:Q"),
                        x2=alt.X2("upper:Q"),
                        tooltip=[
                            "name",
                            alt.Tooltip("lower:Q", title="95% interval lower", format=".2f"),
                            alt.Tooltip("upper:Q", title="95% interval upper", format=".2f"),
                        ],
                    )
                )
                slip_chart = slip_chart + slip_error_bars
        st.altair_chart(slip_chart, use_container_width=True)
        if not _maybe_warning_for_replications(all_runs_df):
            st.caption(
                f"Bars show scenario means. Error bars show 95% intervals across replications within the same scenario when at least {MIN_REPLICATIONS_FOR_INTERVAL} replications are available."
            )
        slip_summary_df = results_df[["name", "total_slipped_units"]].rename(
            columns={"name": "Scenario", "total_slipped_units": "Mean slipped plant units"}
        )
        if all_runs_df is not None and {"name", "total_slipped_units"}.issubset(all_runs_df.columns):
            slip_table_intervals = (
                all_runs_df[["name", "total_slipped_units"]]
                .dropna()
                .groupby("name")["total_slipped_units"]
                .agg(
                    lower=lambda s: s.quantile(0.025),
                    upper=lambda s: s.quantile(0.975),
                    replications="size",
                )
                .reset_index()
            )
            slip_summary_df = slip_summary_df.merge(slip_table_intervals, left_on="Scenario", right_on="name", how="left")
            slip_summary_df["2.5% Quantile - 97.5% Quantile"] = slip_summary_df.apply(
                lambda row: _interval_text(row.get("lower"), row.get("upper"), int(row.get("replications", 0))),
                axis=1,
            )
            if "name" in slip_summary_df.columns:
                slip_summary_df = slip_summary_df.drop(columns=["name"])
        if "Mean slipped plant units" in slip_summary_df.columns:
            slip_summary_df["Mean slipped plant units"] = slip_summary_df["Mean slipped plant units"].map(
                lambda value: f"{_safe_float(value):,.2f}"
            )
        st.dataframe(
            _styled_summary_table(
                slip_summary_df,
                mean_columns=["Mean slipped plant units"],
                interval_columns=["2.5% Quantile - 97.5% Quantile"],
            ),
            use_container_width=True,
            height=min(420, 70 + 38 * max(len(slip_summary_df), 1)),
        )

def render_inspection_workload_level():
    if all(
        col in results_df.columns
        for col in [
            "name",
            "avg_plant_units_inspected_completion",
            "avg_sample_units_inspected_completion",
            "avg_inspection_units_opened_completion",
        ]
    ):
        render_labeled_help(
            "Number of units inspected",
            (
                "Shows the mean number of inspection units opened, sample units inspected, "
                "and plant units inspected for each scenario. When available, 95% intervals "
                f"are computed across replications within the same scenario using at least {MIN_REPLICATIONS_FOR_INTERVAL} replications."
            ),
        )
        inspected_df = results_df[
            [
                "name",
                "avg_plant_units_inspected_completion",
                "avg_sample_units_inspected_completion",
                "avg_inspection_units_opened_completion",
            ]
        ].rename(
            columns={
                "avg_plant_units_inspected_completion": "Plants inspected",
                "avg_sample_units_inspected_completion": "Sample units inspected",
                "avg_inspection_units_opened_completion": "Inspection units opened",
            }
        )

        if all_runs_df is not None and {
            "name",
            "avg_plant_units_inspected_completion",
            "avg_sample_units_inspected_completion",
            "avg_inspection_units_opened_completion",
        }.issubset(all_runs_df.columns):
            inspected_intervals = (
                all_runs_df[
                    [
                        "name",
                        "avg_plant_units_inspected_completion",
                        "avg_sample_units_inspected_completion",
                        "avg_inspection_units_opened_completion",
                    ]
                ]
                .dropna()
                .groupby("name")
                .agg(
                    plant_lower=("avg_plant_units_inspected_completion", lambda s: s.quantile(0.025)),
                    plant_upper=("avg_plant_units_inspected_completion", lambda s: s.quantile(0.975)),
                    sample_lower=("avg_sample_units_inspected_completion", lambda s: s.quantile(0.025)),
                    sample_upper=("avg_sample_units_inspected_completion", lambda s: s.quantile(0.975)),
                    inspection_lower=("avg_inspection_units_opened_completion", lambda s: s.quantile(0.025)),
                    inspection_upper=("avg_inspection_units_opened_completion", lambda s: s.quantile(0.975)),
                    replications=("avg_plant_units_inspected_completion", "size"),
                )
                .reset_index()
            )
            inspected_df = inspected_df.merge(inspected_intervals, on="name", how="left")
            inspected_df["Plants 95% interval"] = inspected_df.apply(
                lambda row: f"{row['plant_lower']:.1f} - {row['plant_upper']:.1f}"
                if pd.notna(row.get("plant_lower")) and row.get("replications", 0) >= MIN_REPLICATIONS_FOR_INTERVAL
                else "n/a",
                axis=1,
            )
            inspected_df["Sample units 95% interval"] = inspected_df.apply(
                lambda row: f"{row['sample_lower']:.1f} - {row['sample_upper']:.1f}"
                if pd.notna(row.get("sample_lower")) and row.get("replications", 0) >= MIN_REPLICATIONS_FOR_INTERVAL
                else "n/a",
                axis=1,
            )
            inspected_df["Inspection units 95% interval"] = inspected_df.apply(
                lambda row: f"{row['inspection_lower']:.1f} - {row['inspection_upper']:.1f}"
                if pd.notna(row.get("inspection_lower")) and row.get("replications", 0) >= MIN_REPLICATIONS_FOR_INTERVAL
                else "n/a",
                axis=1,
            )

        display_cols = [
            "name",
            "Plants inspected",
            "Plants 95% interval",
            "Sample units inspected",
            "Sample units 95% interval",
            "Inspection units opened",
            "Inspection units 95% interval",
        ]
        available_cols = [col for col in display_cols if col in inspected_df.columns]
        display_df = inspected_df[available_cols].rename(columns={"name": "Scenario"}).copy()
        numeric_cols = [
            col for col in ["Plants inspected", "Sample units inspected", "Inspection units opened"]
            if col in display_df.columns
        ]
        for col in numeric_cols:
            display_df[col] = display_df[col].map(_format_count)
        styled_inspected = _styled_summary_table(
            display_df,
            mean_columns=["Plants inspected", "Sample units inspected", "Inspection units opened"],
            interval_columns=["Plants 95% interval", "Sample units 95% interval", "Inspection units 95% interval"],
        )
        st.dataframe(styled_inspected, use_container_width=True, height=min(420, 70 + 38 * max(len(display_df), 1)))

        inspected_pct_df = results_df[
            [
                "name",
                "pct_plant_units_inspected_completion",
                "pct_sample_units_inspected_completion",
                "pct_inspection_units_opened_completion",
            ]
        ].copy()
        inspected_pct_df = inspected_pct_df.rename(
            columns={
                "pct_plant_units_inspected_completion": "Plant units inspected %",
                "pct_sample_units_inspected_completion": "Sample units inspected %",
                "pct_inspection_units_opened_completion": "Inspection units opened %",
            }
        )
        if all_runs_df is not None and {
            "name",
            "pct_plant_units_inspected_completion",
            "pct_sample_units_inspected_completion",
            "pct_inspection_units_opened_completion",
        }.issubset(all_runs_df.columns):
            inspected_pct_runs = all_runs_df[
                [
                    "name",
                    "pct_plant_units_inspected_completion",
                    "pct_sample_units_inspected_completion",
                    "pct_inspection_units_opened_completion",
                ]
            ].copy()
            inspected_pct_intervals = (
                inspected_pct_runs.groupby("name")
                .agg(
                    plant_lower=("pct_plant_units_inspected_completion", lambda s: s.quantile(0.025)),
                    plant_upper=("pct_plant_units_inspected_completion", lambda s: s.quantile(0.975)),
                    sample_lower=("pct_sample_units_inspected_completion", lambda s: s.quantile(0.025)),
                    sample_upper=("pct_sample_units_inspected_completion", lambda s: s.quantile(0.975)),
                    inspection_lower=("pct_inspection_units_opened_completion", lambda s: s.quantile(0.025)),
                    inspection_upper=("pct_inspection_units_opened_completion", lambda s: s.quantile(0.975)),
                    replications=("pct_plant_units_inspected_completion", "size"),
                )
                .reset_index()
            )
            inspected_pct_df = inspected_pct_df.merge(inspected_pct_intervals, on="name", how="left")
            inspected_pct_df["Plant units 95% interval"] = inspected_pct_df.apply(
                lambda row: _interval_text(row.get("plant_lower"), row.get("plant_upper"), int(row.get("replications", 0)), suffix="%"),
                axis=1,
            )
            inspected_pct_df["Sample units 95% interval"] = inspected_pct_df.apply(
                lambda row: _interval_text(row.get("sample_lower"), row.get("sample_upper"), int(row.get("replications", 0)), suffix="%"),
                axis=1,
            )
            inspected_pct_df["Inspection units 95% interval"] = inspected_pct_df.apply(
                lambda row: _interval_text(row.get("inspection_lower"), row.get("inspection_upper"), int(row.get("replications", 0)), suffix="%"),
                axis=1,
            )
        render_labeled_help(
            "Percent of units inspected",
            f"Shows the mean percentage of plant, sample, and inspection units inspected for each scenario. When at least {MIN_REPLICATIONS_FOR_INTERVAL} replications are available, 95% intervals are computed across replications within the same scenario.",
        )
        inspected_pct_display_cols = [
            "name",
            "Plant units inspected %",
            "Plant units 95% interval",
            "Sample units inspected %",
            "Sample units 95% interval",
            "Inspection units opened %",
            "Inspection units 95% interval",
        ]
        inspected_pct_display = inspected_pct_df[
            [col for col in inspected_pct_display_cols if col in inspected_pct_df.columns]
        ].rename(columns={"name": "Scenario"}).copy()
        inspected_pct_mean_cols = [
            col
            for col in [
                "Plant units inspected %",
                "Sample units inspected %",
                "Inspection units opened %",
            ]
            if col in inspected_pct_display.columns
        ]
        for col in inspected_pct_mean_cols:
            inspected_pct_display[col] = inspected_pct_display[col].map(_format_percent)
        st.dataframe(
            _styled_summary_table(
                inspected_pct_display,
                mean_columns=inspected_pct_mean_cols,
                interval_columns=[
                    "Plant units 95% interval",
                    "Sample units 95% interval",
                    "Inspection units 95% interval",
                ],
            ),
            use_container_width=True,
            height=min(420, 70 + 38 * max(len(inspected_pct_display), 1)),
        )
        _maybe_warning_for_replications(all_runs_df)

with st.expander("Interceptions", expanded=expand_all_summary_sections):

    if all(
        col in results_df.columns
        for col in [
            "name",
            "intercepted",
            "false_neg",
            "num_inspections",
            "num_plants",
            "num_sample_units",
            "num_inspection_units",
            "total_contaminated_units",
            "total_slipped_units",
            "total_contaminated_sample_units",
        ]
    ):
        inspection_results_df = None
        sample_results_df = None
        if inspection_action_runs_df is not None and not {
            "total_intercepted_inspection_units",
            "total_slipped_inspection_units",
        }.issubset(results_df.columns):
            inspection_results_df = (
                inspection_action_runs_df.groupby("name")
                .agg(
                    total_intercepted_inspection_units=("total_intercepted_inspection_units", "mean"),
                    total_slipped_inspection_units=("total_slipped_inspection_units", "mean"),
                )
                .reset_index()
            )
        if all_runs_df is not None and "total_slipped_sample_units" in all_runs_df.columns and "total_slipped_sample_units" not in results_df.columns:
            sample_results_df = (
                all_runs_df.groupby("name")
                .agg(total_slipped_sample_units=("total_slipped_sample_units", "mean"))
                .reset_index()
            )

        def _action_level_rows(df):
            rows = []
            has_inspection_level = {
                "total_intercepted_inspection_units",
                "total_slipped_inspection_units",
            }.issubset(df.columns)
            has_sample_level = {
                "total_contaminated_sample_units",
                "total_slipped_sample_units",
            }.issubset(df.columns)
            for _, row in df.iterrows():
                scenario = row["name"]
                level_metrics = [
                    ("Consignment", float(row["intercepted"]), float(row["false_neg"])),
                    (
                        "Plant",
                        max(float(row["total_contaminated_units"]) - float(row["total_slipped_units"]), 0.0),
                        float(row["total_slipped_units"]),
                    ),
                ]
                if has_sample_level:
                    level_metrics.insert(
                        1 if not has_inspection_level else 2,
                        (
                            "Sample",
                            max(
                                float(row["total_contaminated_sample_units"]) - float(row["total_slipped_sample_units"]),
                                0.0,
                            ),
                            float(row["total_slipped_sample_units"]),
                        ),
                    )
                if has_inspection_level:
                    level_metrics.insert(
                        1,
                        (
                            "Inspection",
                            float(row["total_intercepted_inspection_units"]),
                            float(row["total_slipped_inspection_units"]),
                        ),
                    )
                for level_name, intercepted_count, slipped_count in level_metrics:
                    total_count = intercepted_count + slipped_count
                    rows.append(
                        {
                            "name": scenario,
                            "Level": level_name,
                            "Intercepted": intercepted_count,
                            "Slipped": slipped_count,
                            "Intercepted %": (intercepted_count / total_count) * 100.0 if total_count > 0 else np.nan,
                            "Slipped %": (slipped_count / total_count) * 100.0 if total_count > 0 else np.nan,
                        }
                    )
            return pd.DataFrame(rows)

        action_results_source = results_df.copy()
        if inspection_results_df is not None:
            action_results_source = action_results_source.merge(inspection_results_df, on="name", how="left")
        if sample_results_df is not None:
            action_results_source = action_results_source.merge(sample_results_df, on="name", how="left")

        action_counts_base_df = _action_level_rows(action_results_source)
        inspection_level_available = "Inspection" in set(action_counts_base_df["Level"])

        render_labeled_help(
            "Counts of interceptions",
            (
                "Shows the mean intercepted and slipped counts for contaminated consignments, plant units, "
                "sample units, and inspection units for each scenario. When available, "
                f"95% intervals are computed across replications within the same scenario using at least {MIN_REPLICATIONS_FOR_INTERVAL} replications."
            ),
        )
        action_counts_df = action_counts_base_df.copy()
        action_runs_source = all_runs_df.copy() if all_runs_df is not None else None
        if action_runs_source is not None and inspection_action_runs_df is not None and not {
            "total_intercepted_inspection_units",
            "total_slipped_inspection_units",
        }.issubset(action_runs_source.columns):
            action_runs_source = action_runs_source.merge(
                inspection_action_runs_df,
                on=["name", "replication"],
                how="left",
            )

        if action_runs_source is not None and {
            "name",
            "intercepted",
            "false_neg",
            "total_contaminated_units",
            "total_slipped_units",
            "total_contaminated_sample_units",
        }.issubset(action_runs_source.columns):
            action_runs_df = _action_level_rows(action_runs_source)
            action_count_intervals = (
                action_runs_df[["name", "Level", "Intercepted", "Slipped"]]
                .dropna()
                .groupby(["name", "Level"])
                .agg(
                    intercepted_lower=("Intercepted", lambda s: s.quantile(0.025)),
                    intercepted_upper=("Intercepted", lambda s: s.quantile(0.975)),
                    slipped_lower=("Slipped", lambda s: s.quantile(0.025)),
                    slipped_upper=("Slipped", lambda s: s.quantile(0.975)),
                    replications=("Intercepted", "size"),
                )
                .reset_index()
            )
            action_counts_df = action_counts_df.merge(action_count_intervals, on=["name", "Level"], how="left")
            action_counts_df["Intercepted 95% interval"] = action_counts_df.apply(
                lambda row: f"{row['intercepted_lower']:.1f} - {row['intercepted_upper']:.1f}"
                if pd.notna(row.get("intercepted_lower")) and row.get("replications", 0) >= MIN_REPLICATIONS_FOR_INTERVAL
                else "n/a",
                axis=1,
            )
            action_counts_df["Slipped 95% interval"] = action_counts_df.apply(
                lambda row: f"{row['slipped_lower']:.1f} - {row['slipped_upper']:.1f}"
                if pd.notna(row.get("slipped_lower")) and row.get("replications", 0) >= MIN_REPLICATIONS_FOR_INTERVAL
                else "n/a",
                axis=1,
        )
        action_count_display = action_counts_df.rename(columns={"name": "Scenario"}).copy()
        action_count_display = action_count_display[
            [
                col
                for col in [
                    "Scenario",
                    "Level",
                    "Intercepted",
                    "Intercepted 95% interval",
                    "Slipped",
                    "Slipped 95% interval",
                ]
                if col in action_count_display.columns
            ]
        ]
        for col in ["Intercepted", "Slipped"]:
            if col in action_count_display.columns:
                action_count_display[col] = action_count_display[col].map(_format_count)
        st.dataframe(
            _styled_summary_table(
                action_count_display,
                mean_columns=["Intercepted", "Slipped"],
                interval_columns=["Intercepted 95% interval", "Slipped 95% interval"],
            ),
            use_container_width=True,
            height=min(420, 70 + 38 * max(len(action_count_display), 1)),
        )
        if not inspection_level_available:
            st.info("Inspection-level action metrics are unavailable in the current output files.")

        render_labeled_help(
            "Interceptions Metrics by Percentage",
            (
                "Shows the mean share of contaminated consignments, plant units, sample units, and inspection units "
                "that were intercepted versus slipped for each scenario. Percentages are computed within each replication and then averaged "
                f"across replications. When available, 95% intervals are computed across replications within the same scenario using at least {MIN_REPLICATIONS_FOR_INTERVAL} replications."
            ),
        )
        action_pct_df = action_counts_base_df.copy()
        if action_runs_source is not None and {
            "name",
            "intercepted",
            "false_neg",
            "total_contaminated_units",
            "total_slipped_units",
            "total_contaminated_sample_units",
        }.issubset(action_runs_source.columns):
            action_pct_runs = _action_level_rows(action_runs_source)
            action_pct_intervals = (
                action_pct_runs.groupby(["name", "Level"])
                .agg(
                    intercepted_lower=("Intercepted %", lambda s: s.quantile(0.025)),
                    intercepted_upper=("Intercepted %", lambda s: s.quantile(0.975)),
                    slipped_lower=("Slipped %", lambda s: s.quantile(0.025)),
                    slipped_upper=("Slipped %", lambda s: s.quantile(0.975)),
                    replications=("Intercepted %", "size"),
                )
                .reset_index()
            )
            action_pct_df = action_pct_df.merge(action_pct_intervals, on=["name", "Level"], how="left")
            action_pct_df["Intercepted 95% interval"] = action_pct_df.apply(
                lambda row: _interval_text(row.get("intercepted_lower"), row.get("intercepted_upper"), int(row.get("replications", 0)), suffix="%"),
                axis=1,
            )
            action_pct_df["Slipped 95% interval"] = action_pct_df.apply(
                lambda row: _interval_text(row.get("slipped_lower"), row.get("slipped_upper"), int(row.get("replications", 0)), suffix="%"),
                axis=1,
            )
        action_pct_display = action_pct_df[
            [
                col
                for col in [
                    "name",
                    "Level",
                    "Intercepted %",
                    "Intercepted 95% interval",
                    "Slipped %",
                    "Slipped 95% interval",
                ]
                if col in action_pct_df.columns
            ]
        ].rename(columns={"name": "Scenario"}).copy()
        action_pct_display = action_pct_display[
            [
                col
                for col in [
                    "Scenario",
                    "Level",
                    "Intercepted %",
                    "Intercepted 95% interval",
                    "Slipped %",
                    "Slipped 95% interval",
                ]
                if col in action_pct_display.columns
            ]
        ]
        for col in ["Intercepted %", "Slipped %"]:
            action_pct_display[col] = action_pct_display[col].map(_format_percent)
        st.dataframe(
            _styled_summary_table(
                action_pct_display,
                mean_columns=["Intercepted %", "Slipped %"],
                interval_columns=["Intercepted 95% interval", "Slipped 95% interval"],
            ),
            use_container_width=True,
            height=min(420, 70 + 38 * max(len(action_pct_display), 1)),
        )
        _maybe_warning_for_replications(all_runs_df)

with st.expander("Contamination Level", expanded=expand_all_summary_sections):

    required_cols = [
        "name",
        "total_contaminated_units",
        "total_contaminated_sample_units",
        "total_contaminated_inspection_units",
        "num_plants",
        "num_sample_units",
        "num_inspection_units",
    ]
    if all(col in results_df.columns for col in required_cols):
        render_labeled_help(
            "Contamination totals by level",
            f"For each scenario, bars show the mean contaminated and not-contaminated counts across simulation replications at the plant, sample unit, and inspection unit levels. Error bars show 95% intervals across replications within the same scenario when at least {MIN_REPLICATIONS_FOR_INTERVAL} replications are available.",
        )

        def level_chart(level_label, contam_col, total_col):
            data = results_df[["name", contam_col, total_col]].copy()
            data = data.rename(columns={contam_col: "contaminated", total_col: "total"})
            data["not_contaminated"] = data["total"] - data["contaminated"]
            data = data.melt(
                id_vars="name",
                value_vars=["contaminated", "not_contaminated"],
                var_name="metric",
                value_name="value",
            )
            interval_df = None
            if all_runs_df is not None and contam_col in all_runs_df.columns and total_col in all_runs_df.columns:
                interval_source = all_runs_df[["name", contam_col, total_col]].dropna()
                if not interval_source.empty:
                    interval_source = interval_source.rename(columns={contam_col: "contaminated", total_col: "total"})
                    interval_source["not_contaminated"] = interval_source["total"] - interval_source["contaminated"]
                    interval_source = interval_source.melt(
                        id_vars="name",
                        value_vars=["contaminated", "not_contaminated"],
                        var_name="metric",
                        value_name="value",
                    )
                    interval_df = (
                        interval_source.groupby(["name", "metric"])["value"]
                        .agg(
                            lower=lambda s: s.quantile(0.025),
                            upper=lambda s: s.quantile(0.975),
                            n="size",
                        )
                        .reset_index()
                    )
                    interval_df = interval_df[interval_df["n"] >= MIN_REPLICATIONS_FOR_INTERVAL]

            charts = []
            for metric_name, metric_title, metric_color in [
                ("contaminated", "Contaminated", "#1f77b4"),
                ("not_contaminated", "Not contaminated", "#9ecae1"),
            ]:
                metric_data = data[data["metric"] == metric_name]
                base = alt.Chart(metric_data).encode(
                    y=alt.Y("name:N", title="Scenario"),
                    x=alt.X("value:Q", title="Count"),
                    tooltip=[
                        "name",
                        alt.Tooltip("value:Q", title="Count", format=".2f"),
                    ],
                )
                metric_chart = base.mark_bar(color=metric_color).properties(title=metric_title)
                if interval_df is not None and not interval_df.empty:
                    metric_intervals = interval_df[interval_df["metric"] == metric_name]
                    if not metric_intervals.empty:
                        error_bars = (
                            alt.Chart(metric_intervals)
                            .mark_errorbar(color="#08306b", ticks=True)
                            .encode(
                                y=alt.Y("name:N", title="Scenario"),
                                x=alt.X("lower:Q"),
                                x2=alt.X2("upper:Q"),
                                tooltip=[
                                    "name",
                                    alt.Tooltip("lower:Q", title="95% interval lower", format=".2f"),
                                    alt.Tooltip("upper:Q", title="95% interval upper", format=".2f"),
                                ],
                            )
                        )
                        metric_chart = metric_chart + error_bars
                charts.append(metric_chart)
            return alt.hconcat(*charts).properties(title=level_label)

        st.altair_chart(
            level_chart("PLANT UNITS", "total_contaminated_units", "num_plants"),
            use_container_width=True,
        )
        st.altair_chart(
            level_chart(
                "SAMPLE UNITS", "total_contaminated_sample_units", "num_sample_units"
            ),
            use_container_width=True,
        )
        st.altair_chart(
            level_chart(
                "INSPECTION UNITS", "total_contaminated_inspection_units", "num_inspection_units",
            ),
            use_container_width=True,
        )
        if not _maybe_warning_for_replications(all_runs_df):
            st.caption(
                f"Bars show scenario means. Error bars show 95% intervals across replications within the same scenario when at least {MIN_REPLICATIONS_FOR_INTERVAL} replications are available."
            )
        contam_summary_df = results_df[
            [
                "name",
                "total_contaminated_units",
                "total_contaminated_sample_units",
                "total_contaminated_inspection_units",
            ]
        ].rename(
            columns={
                "name": "Scenario",
                "total_contaminated_units": "Plant contaminated mean",
                "total_contaminated_sample_units": "Sample unit contaminated mean",
                "total_contaminated_inspection_units": "Inspection unit contaminated mean",
            }
        )
        if all_runs_df is not None and {
            "name",
            "total_contaminated_units",
            "total_contaminated_sample_units",
            "total_contaminated_inspection_units",
        }.issubset(all_runs_df.columns):
            contam_intervals = (
                all_runs_df[
                    [
                        "name",
                        "total_contaminated_units",
                        "total_contaminated_sample_units",
                        "total_contaminated_inspection_units",
                    ]
                ]
                .dropna()
                .groupby("name")
                .agg(
                    plant_lower=("total_contaminated_units", lambda s: s.quantile(0.025)),
                    plant_upper=("total_contaminated_units", lambda s: s.quantile(0.975)),
                    sample_lower=("total_contaminated_sample_units", lambda s: s.quantile(0.025)),
                    sample_upper=("total_contaminated_sample_units", lambda s: s.quantile(0.975)),
                    inspection_lower=("total_contaminated_inspection_units", lambda s: s.quantile(0.025)),
                    inspection_upper=("total_contaminated_inspection_units", lambda s: s.quantile(0.975)),
                    replications=("total_contaminated_units", "size"),
                )
                .reset_index()
            )
            contam_summary_df = contam_summary_df.merge(contam_intervals, left_on="Scenario", right_on="name", how="left")
            contam_summary_df["Plant 95% interval"] = contam_summary_df.apply(
                lambda row: _interval_text(row.get("plant_lower"), row.get("plant_upper"), int(row.get("replications", 0))),
                axis=1,
            )
            contam_summary_df["Sample unit 95% interval"] = contam_summary_df.apply(
                lambda row: _interval_text(row.get("sample_lower"), row.get("sample_upper"), int(row.get("replications", 0))),
                axis=1,
            )
            contam_summary_df["Inspection unit 95% interval"] = contam_summary_df.apply(
                lambda row: _interval_text(row.get("inspection_lower"), row.get("inspection_upper"), int(row.get("replications", 0))),
                axis=1,
            )
            if "name" in contam_summary_df.columns:
                contam_summary_df = contam_summary_df.drop(columns=["name"])
        contam_mean_cols = [
            "Plant contaminated mean",
            "Sample unit contaminated mean",
            "Inspection unit contaminated mean",
        ]
        for col in [col for col in contam_mean_cols if col in contam_summary_df.columns]:
            contam_summary_df[col] = contam_summary_df[col].map(lambda value: f"{_safe_float(value):,.2f}")
        contam_display_cols = [
            "Scenario",
            "Plant contaminated mean",
            "Plant 95% interval",
            "Sample unit contaminated mean",
            "Sample unit 95% interval",
            "Inspection unit contaminated mean",
            "Inspection unit 95% interval",
        ]
        contam_summary_df = contam_summary_df[[col for col in contam_display_cols if col in contam_summary_df.columns]]
        st.dataframe(
            _styled_summary_table(
                contam_summary_df,
                mean_columns=contam_mean_cols,
                interval_columns=["Plant 95% interval", "Sample unit 95% interval", "Inspection unit 95% interval"],
            ),
            use_container_width=True,
            height=min(420, 70 + 38 * max(len(contam_summary_df), 1)),
        )

        pct_df = results_df[
            [
                "name",
                "total_contaminated_units",
                "total_contaminated_sample_units",
                "total_contaminated_inspection_units",
                "num_plants",
                "num_sample_units",
                "num_inspection_units",
            ]
        ].copy()
        pct_df["Plant contamination %"] = np.where(
            pct_df["num_plants"] > 0,
            (pct_df["total_contaminated_units"] / pct_df["num_plants"]) * 100.0,
            np.nan,
        )
        pct_df["Sample unit contamination %"] = np.where(
            pct_df["num_sample_units"] > 0,
            (pct_df["total_contaminated_sample_units"] / pct_df["num_sample_units"]) * 100.0,
            np.nan,
        )
        pct_df["Inspection unit contamination %"] = np.where(
            pct_df["num_inspection_units"] > 0,
            (pct_df["total_contaminated_inspection_units"] / pct_df["num_inspection_units"]) * 100.0,
            np.nan,
        )

        if all_runs_df is not None and {
            "name",
            "total_contaminated_units",
            "total_contaminated_sample_units",
            "total_contaminated_inspection_units",
            "num_plants",
            "num_sample_units",
            "num_inspection_units",
        }.issubset(all_runs_df.columns):
            pct_runs = all_runs_df[
                [
                    "name",
                    "total_contaminated_units",
                    "total_contaminated_sample_units",
                    "total_contaminated_inspection_units",
                    "num_plants",
                    "num_sample_units",
                    "num_inspection_units",
                ]
            ].copy()
            pct_runs["plant_pct"] = np.where(
                pct_runs["num_plants"] > 0,
                (pct_runs["total_contaminated_units"] / pct_runs["num_plants"]) * 100.0,
                np.nan,
            )
            pct_runs["sample_pct"] = np.where(
                pct_runs["num_sample_units"] > 0,
                (pct_runs["total_contaminated_sample_units"] / pct_runs["num_sample_units"]) * 100.0,
                np.nan,
            )
            pct_runs["inspection_pct"] = np.where(
                pct_runs["num_inspection_units"] > 0,
                (pct_runs["total_contaminated_inspection_units"] / pct_runs["num_inspection_units"]) * 100.0,
                np.nan,
            )
            pct_intervals = (
                pct_runs.groupby("name")
                .agg(
                    plant_lower=("plant_pct", lambda s: s.quantile(0.025)),
                    plant_upper=("plant_pct", lambda s: s.quantile(0.975)),
                    sample_lower=("sample_pct", lambda s: s.quantile(0.025)),
                    sample_upper=("sample_pct", lambda s: s.quantile(0.975)),
                    inspection_lower=("inspection_pct", lambda s: s.quantile(0.025)),
                    inspection_upper=("inspection_pct", lambda s: s.quantile(0.975)),
                    replications=("plant_pct", "size"),
                )
                .reset_index()
            )
            pct_df = pct_df.merge(pct_intervals, on="name", how="left")
            pct_df["Plant 95% interval"] = pct_df.apply(
                lambda row: _interval_text(row.get("plant_lower"), row.get("plant_upper"), int(row.get("replications", 0)), suffix="%"),
                axis=1,
            )
            pct_df["Sample unit 95% interval"] = pct_df.apply(
                lambda row: _interval_text(row.get("sample_lower"), row.get("sample_upper"), int(row.get("replications", 0)), suffix="%"),
                axis=1,
            )
            pct_df["Inspection unit 95% interval"] = pct_df.apply(
                lambda row: _interval_text(row.get("inspection_lower"), row.get("inspection_upper"), int(row.get("replications", 0)), suffix="%"),
                axis=1,
            )

        render_labeled_help(
            "Contamination percentages by level",
            f"Shows the mean percentage contaminated at the plant, sample unit, and inspection unit levels for each scenario. When at least {MIN_REPLICATIONS_FOR_INTERVAL} replications are available, 95% intervals are computed across replications within the same scenario.",
        )
        pct_display_cols = [
            "name",
            "Plant contamination %",
            "Plant 95% interval",
            "Sample unit contamination %",
            "Sample unit 95% interval",
            "Inspection unit contamination %",
            "Inspection unit 95% interval",
        ]
        pct_available_cols = [col for col in pct_display_cols if col in pct_df.columns]
        pct_display_df = pct_df[pct_available_cols].rename(columns={"name": "Scenario"}).copy()
        pct_numeric_cols = [
            col
            for col in [
                "Plant contamination %",
                "Sample unit contamination %",
                "Inspection unit contamination %",
            ]
            if col in pct_display_df.columns
        ]
        for col in pct_numeric_cols:
            pct_display_df[col] = pct_display_df[col].map(_format_percent)
        styled_pct = _styled_summary_table(
            pct_display_df,
            mean_columns=pct_numeric_cols,
            interval_columns=[
                "Plant 95% interval",
                "Sample unit 95% interval",
                "Inspection unit 95% interval",
            ],
        )
        st.dataframe(styled_pct, use_container_width=True, height=min(420, 70 + 38 * max(len(pct_display_df), 1)))
    else:
        st.info("Contamination totals by level are unavailable in the current results.")

with st.expander("Inspection Workload Level", expanded=expand_all_summary_sections):
    render_inspection_workload_level()

# st.header("Raw output")
# st.dataframe(state["results"], use_container_width=True)

st.divider()
nav_cols = st.columns(3)
with nav_cols[0]:
    if st.button("Reset and Return Home", type="secondary", key="nav_reset_page5"):
        try:
            # Use safe reset utility to clear temporary directory
            from .tmp_utils import reset_tmp_directory
            reset_tmp_directory(TMP_DIR)
            st.session_state.clear()
            state["paths"] = create_default_paths()
            st.switch_page("frontend.py")
        except Exception as exc:  # pylint: disable=broad-except
            st.error(f"Unable to reset temporary files: {exc}")
with nav_cols[1]:
    if st.button("Previous Page", type="primary", key="nav_back_page5"):
        st.switch_page("pages/4_Scenario_Experiments.py")
with nav_cols[2]:
    if st.button("Next Page", type="primary", key="nav_forward_page6"):
        st.switch_page("pages/6_Glossary.py")

if st.session_state.get("_awaiting_results_display"):
    st.session_state["_awaiting_results_display"] = False
