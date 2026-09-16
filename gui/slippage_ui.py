# © 2026 The Johns Hopkins University Applied Physics Laboratory LLC

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from runtime_warnings import suppress_optional_dependency_warnings

suppress_optional_dependency_warnings()

import pandas as pd
import streamlit as st

from slippage_pipeline import (
    ExperimentPaths,
    SyntheticOptions,
    SlippagePaths,
    create_default_paths,
    load_scenario_dataframe,
    run_slippage_pipeline,
)

from slippage_model_utils.paths import DefaultPaths

# Define default paths object
default_paths = DefaultPaths()

TMP_CONFIG_PATH = default_paths.tmp_dir() / "config.yml"
TMP_PIS_PATH = default_paths.tmp_dir() / "contamination" / "fit_pis_data.csv"
TMP_RBS_PATH = default_paths.tmp_dir() / "consignments" / "consignment_uploaded_rbs_data.csv"
CONFIG_FILENAME = "config_rbs.yml"
SCENARIO_FILENAME = "scenario_table.csv"

STATE_KEY = "slippage_ui_state"
PREVIEW_ROWS = 10


def _safe_preview(df: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
    """Return a small preview (head) of a DataFrame or None.

    Args:
        df: Input DataFrame or None.

    Returns:
        First ``PREVIEW_ROWS`` rows of ``df``, the original empty DataFrame,
        or None if ``df`` is None.
    """
    if df is None:
        return None
    if df.empty:
        return df
    return df.head(PREVIEW_ROWS)


def _load_optional_scenario_dataframe(path: Optional[Path]) -> pd.DataFrame:
    """Load scenario data when available, otherwise return an empty DataFrame.

    Args:
        path: Path to the scenario-table file or None.

    Returns:
        Scenario table as a DataFrame, or an empty DataFrame if the path
        is missing or unreadable.
    """
    if path is None:
        return pd.DataFrame()
    try:
        path = Path(path)
        if not path.exists():
            return pd.DataFrame()
        return load_scenario_dataframe(path, dtype="object")
    except Exception:
        return pd.DataFrame()


def _replace_paths(paths: SlippagePaths, **updates: Path) -> SlippagePaths:
    """Return a copy of SlippagePaths with selected fields updated.

    Args:
        paths: Existing SlippagePaths instance.
        **updates: Field/value overrides keyed by SlippagePaths attribute names.

    Returns:
        New SlippagePaths instance with the updates applied.
    """
    return replace(paths, **updates)


def _default_paths_with_tmp_overrides() -> SlippagePaths:
    """Create default paths, overriding with temporary paths if present.

    Returns:
        SlippagePaths where config, PIS, and RBS paths are replaced by
        temporary versions when those files exist.
    """
    paths = create_default_paths()
    if TMP_CONFIG_PATH.exists():
        paths = _replace_paths(paths, config=TMP_CONFIG_PATH)
    if TMP_PIS_PATH.exists():
        paths = _replace_paths(paths, pis_data=TMP_PIS_PATH)
    if TMP_RBS_PATH.exists():
        paths = _replace_paths(paths, rbs_data=TMP_RBS_PATH, synthetic_seed=TMP_RBS_PATH)
    return paths


def _infer_num_consignments_from_path(consignment_path: Optional[Path]) -> Optional[int]:
    """Infer number of consignments from a consignment CSV path.

    Uses the number of unique INSPECTION_NUMBER or INSPECTION_ID values.

    Args:
        consignment_path: Optional path to a consignment CSV.

    Returns:
        Number of unique consignments or None if inference is not possible.
    """
    if not consignment_path or not consignment_path.exists():
        return None
    df = pd.read_csv(consignment_path)
    for col in ("INSPECTION_NUMBER", "INSPECTION_ID"):
        if col in df.columns:
            return int(df[col].nunique())
    return None


def _resolve_experiment_input_paths(
    experiment_dir: Path,
    scenario_path: Path,
) -> tuple[Optional[Path], Optional[Path]]:
    """Resolve consignment and compliance paths from an experiment scenario file.

    The scenario table is inspected for
    ``consignment/input_file/file_name`` and
    ``inspection/compliance_table/file_name`` columns. If relative paths
    are present, they are resolved relative to ``experiment_dir``.

    Args:
        experiment_dir: Path to the experiment directory.
        scenario_path: Path to the scenario CSV.

    Returns:
        Tuple ``(consignment_path, compliance_path)``, each possibly None.
    """
    consignment_path = None
    compliance_path = None
    scenario_df = pd.read_csv(scenario_path)

    def _first_value(col: str) -> Optional[Path]:
        if col not in scenario_df.columns:
            return None
        for val in scenario_df[col].dropna().tolist():
            if val:
                return Path(str(val))
        return None

    cons_val = _first_value("consignment/input_file/file_name")
    comp_val = _first_value("inspection/compliance_table/file_name")
    if cons_val:
        consignment_path = experiment_dir / cons_val.name if not cons_val.is_absolute() else cons_val
    if comp_val:
        compliance_path = experiment_dir / comp_val.name if not comp_val.is_absolute() else comp_val
    return consignment_path, compliance_path


def init_slippage_state() -> Dict[str, Any]:
    """Initialize and return the Streamlit session state for slippage UI.

    If state already exists under ``STATE_KEY``, it is returned as-is.
    Otherwise, default paths and options are created and stored.

    Returns:
        Dictionary representing the slippage UI state.
    """
    try:
        return st.session_state[STATE_KEY]
    except KeyError:
        paths = _default_paths_with_tmp_overrides()
        scenario_df = _load_optional_scenario_dataframe(paths.scenario_table)
        st.session_state[STATE_KEY] = {
            "paths": paths,
            "scenario_df": scenario_df,
            "synthetic_options": SyntheticOptions(),
            "engine_options": {"seed": 42, "num_simulations": 1},
            "synthetic_data": None,
            "synthetic_preview": _safe_preview(None),
            "pis_data": None,
            "pis_preview": _safe_preview(None),
            "rbs_data": None,
            "rbs_preview": _safe_preview(None),
            "fit": None,
            "results": None,
            "last_run": None,
            "run_error": None,
            "num_consignments": None,
        }
        return st.session_state[STATE_KEY]


def get_slippage_state() -> Dict[str, Any]:
    """Convenience accessor returning the current slippage state.

    Returns:
        The dictionary stored under ``STATE_KEY`` in Streamlit session state.
    """
    return init_slippage_state()


def set_paths(**kwargs: Path):
    """Update filesystem paths used by the slippage pipeline.

    Args:
        **kwargs: Path overrides keyed by SlippagePaths attribute names,
            e.g., ``config=Path("...")``, ``pis_data=...``.
    """
    state = get_slippage_state()
    current_paths: SlippagePaths = state["paths"]
    updated = _replace_paths(current_paths, **kwargs)
    state["paths"] = updated
    if "scenario_table" in kwargs:
        state["scenario_df"] = _load_optional_scenario_dataframe(updated.scenario_table)


def set_scenario_dataframe(df: pd.DataFrame):
    """Persist edits to the scenario table in session state.

    Args:
        df: Updated scenario table DataFrame.
    """
    state = get_slippage_state()
    state["scenario_df"] = df


def set_synthetic_options(options: SyntheticOptions):
    """Update synthetic data generation options in session state.

    Args:
        options: SyntheticOptions instance to store.
    """
    state = get_slippage_state()
    state["synthetic_options"] = options


def set_engine_options(**kwargs: Any):
    """Update engine (simulation) options in session state.

    Args:
        **kwargs: Key/value options to merge into ``engine_options``, e.g.,
            ``seed=123``, ``num_simulations=10``.
    """
    state = get_slippage_state()
    options = state["engine_options"]
    options.update(kwargs)


def record_pipeline_error(message: str):
    """Record an error message and timestamp for the last pipeline run.

    Args:
        message: Error message describing why the run failed.
    """
    state = get_slippage_state()
    state["run_error"] = message
    state["last_run"] = datetime.now(timezone.utc)


def run_pipeline(experiment_dir, progress_callback=None):
    """Execute the slippage pipeline for a given experiment directory.

    This function:

    * Resolves configuration, scenario, consignment, and compliance paths
      under ``experiment_dir``.
    * Calls :func:`run_slippage_pipeline` with these paths and engine
      options from the UI state.
    * Stores results and metadata (e.g., num_consignments, output paths)
      back into the Streamlit session state.

    Args:
        experiment_dir: Path to the experiment directory containing config,
            scenario, and input data.
        progress_callback: Optional callback for reporting progress, passed
            through to :func:`run_slippage_pipeline`.

    Returns:
        The :class:`PipelineResult` returned by :func:`run_slippage_pipeline`.

    Raises:
        Exception: Any exception raised by the underlying pipeline is
            re-raised after best-effort collection of ``num_consignments``.
    """
    state = get_slippage_state()
    paths: SlippagePaths = state["paths"]
    engine_options = state["engine_options"]

    cfg_path = experiment_dir / CONFIG_FILENAME
    scenario_path = experiment_dir / SCENARIO_FILENAME
    try:
        consignment_path, compliance_path = _resolve_experiment_input_paths(experiment_dir, scenario_path)
    except Exception:
        consignment_path, compliance_path = None, None

    exp_paths = ExperimentPaths(
        experiment_dir=experiment_dir,
        scenario_table=scenario_path,
        consignment=consignment_path if consignment_path and consignment_path.exists() else None,
        compliance=compliance_path if compliance_path and compliance_path.exists() else None,
        config=cfg_path if cfg_path.exists() else paths.config,
    )
    state["paths"] = _replace_paths(
        paths,
        scenario_table=scenario_path,
        config=exp_paths.config or paths.config,
        rbs_data=consignment_path if consignment_path and consignment_path.exists() else paths.rbs_data,
        compliance_lookup=compliance_path if compliance_path and compliance_path.exists() else paths.compliance_lookup,
    )

    # Track num_consignments even on failure (best-effort)
    state["num_consignments"] = None

    try:
        run_seed = engine_options.get("seed")
        if run_seed in (None, "", 0):
            from time import time  # pylint: disable=import-outside-toplevel

            run_seed = int(time())
        result = run_slippage_pipeline(
            exp_paths,
            seed=run_seed,
            num_simulations=engine_options.get("num_simulations", 1),
            progress_callback=progress_callback,
        )
    except Exception as exc:  # pylint: disable=broad-except
        try:
            state["num_consignments"] = _infer_num_consignments_from_path(exp_paths.consignment)
            if state["num_consignments"] is None:
                scen_df = pd.read_csv(exp_paths.scenario_table)
                val = scen_df.get("consignment/input_file/file_name", pd.Series()).dropna()
                if not val.empty:
                    cons_path = Path(str(val.iloc[0]))
                    if not cons_path.is_absolute():
                        cons_path = exp_paths.experiment_dir / cons_path.name
                    state["num_consignments"] = _infer_num_consignments_from_path(cons_path)
        except Exception:
            pass
        # Surface the underlying error directly
        print(f"Pipeline failed: {exc}")
        raise
    # Persist results so Page 5 can render visuals
    state["results"] = result.scenario_results
    state["num_consignments"] = result.num_consignments
    state["run_output_dir"] = str(result.output_dir)
    state["run_output_files"] = [str(path) for path in result.output_files]
    state["run_error"] = None
    return result


__all__ = [
    "STATE_KEY",
    "init_slippage_state",
    "get_slippage_state",
    "set_paths",
    "set_scenario_dataframe",
    "set_synthetic_options",
    "set_engine_options",
    "run_pipeline",
]
