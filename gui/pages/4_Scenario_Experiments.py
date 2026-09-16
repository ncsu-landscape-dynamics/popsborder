# © 2026 The Johns Hopkins University Applied Physics Laboratory LLC

from dataclasses import replace
from pathlib import Path
import json
import re
import shutil

from gui.runtime_warnings import suppress_optional_dependency_warnings

suppress_optional_dependency_warnings()

import pandas as pd
import streamlit as st

from gui.models import init_state
from gui.navigation import render_sidebar_navigation
from gui.page_styles import apply_shared_page_styles, render_labeled_help, render_page_intro
from gui.slippage_ui import get_slippage_state
from slippage_model_utils.references import engineered_features
from slippage_model_utils.paths import DefaultPaths

# --- Constants / setup --------------------------------------------------------
default_paths = DefaultPaths()
TMP_DIR = default_paths.tmp_dir()
SCENARIO_ROOT = TMP_DIR / "experiments"
TEMPLATE_SCENARIO = default_paths.input_data_dir() / "pis_contaminate_scenarios.csv"
CONTAM_PARAM_PATH = TMP_DIR / "contamination" / "contamination_parameter_sets.json"
SCENARIO_FILENAME = "scenario_table.csv"
CONFIG_FILENAME = "config.yml"

TMP_DIR.mkdir(exist_ok=True)
SCENARIO_ROOT.mkdir(parents=True, exist_ok=True)

st.set_page_config(
    page_title="Scenario & Experiment Builder",
    page_icon=":test_tube:",
    layout="wide",
)

init_state()
state = get_slippage_state()
render_sidebar_navigation()
apply_shared_page_styles()

st.warning(
    "**Test Deployment Notice: This is a test deployment with limited functionality and is under active development. "
    "Features may be incomplete and subject to change. Results have not been validated.**"
)
st.title("Page 4 - Scenario Experiments")
render_page_intro(
    "Build, review, and save experiment-ready scenario tables. "
    "Scenario bundles are written to <i>tmp/experiments</i> for execution on Page 5."
)
if st.session_state.get("page4_save_success"):
    st.success(st.session_state.pop("page4_save_success"))

# --- Helpers ------------------------------------------------------------------
def _slugify(name: str) -> str:
    """Convert an experiment name into a filesystem-friendly slug.

    Non-alphanumeric characters (other than ``_`` and ``-``) are replaced
    with underscores. If the result is empty, ``"scenario"`` is returned.

    Args:
        name: Arbitrary experiment or scenario name.

    Returns:
        Slugified string safe for use as a folder name.
    """
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", name.strip())
    return slug or "scenario"


def _list_files(folder: Path, pattern: str) -> list[Path]:
    """List files in a folder matching a glob pattern.

    Args:
        folder: Directory to search.
        pattern: Glob pattern (e.g., ``"*.csv"``).

    Returns:
        Sorted list of Path objects if the folder exists, else an empty list.
    """
    return sorted(folder.glob(pattern)) if folder.exists() else []


def _load_param_sets() -> dict:
    """Load contamination parameter sets from the parameter store JSON.

    Returns:
        Dictionary mapping parameter-set names to their parameter data.
        Returns an empty dict if the store does not exist or cannot be read.
    """
    if not CONTAM_PARAM_PATH.exists():
        return {}
    try:
        return json.loads(CONTAM_PARAM_PATH.read_text())
    except Exception:  # pylint: disable=broad-except
        return {}


def _update_state_paths(**updates) -> None:
    """Update path-related entries in the global slippage state.

    Args:
        **updates: Keyword updates for the `paths` dataclass stored in state.
    """
    state["paths"] = replace(state["paths"], **updates)


def _copy_first_existing_file(name: str, scenario_dir: Path, candidates: list[Path], copied_files: list[str], missing: list[str]) -> None:
    """Copy the first existing candidate file into the scenario directory.

    Args:
        name: Target filename to use within ``scenario_dir``.
        scenario_dir: Destination experiment directory.
        candidates: Ordered list of candidate source paths to check.
        copied_files: List to append the successfully copied filename to.
        missing: List to append the filename to if no candidates exist.
    """
    src = next((p for p in candidates if p.exists()), None)
    if src:
        dest = scenario_dir / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())
        copied_files.append(dest.name)
    else:
        missing.append(name)


def _scenario_row_to_portable_paths(rows_df: pd.DataFrame, set_slug: str) -> pd.DataFrame:
    """Rewrite scenario row paths to be portable within a given experiment set.

    Paths in critical columns are rewritten to use a relative prefix
    under ``tmp/experiments/<set_slug>``.

    Args:
        rows_df: Scenario rows DataFrame.
        set_slug: Experiment set slug used as folder name.

    Returns:
        DataFrame with updated file path strings.
    """
    df = rows_df.copy()
    base_prefix = f"tmp/experiments/{set_slug}"
    for col in ("consignment/input_file/file_name", "inspection/compliance_table/file_name"):
        if col in df.columns:
            df[col] = df[col].apply(lambda v: f"{base_prefix}/{Path(str(v)).name}".replace("\\", "/") if v else v)
    return df


def _apply_scenario_defaults(rows_df: pd.DataFrame) -> pd.DataFrame:
    """Apply default contamination and unit settings to a scenario table.

    Ensures contamination unit and rate columns have reasonable defaults
    before normalization.

    Args:
        rows_df: Scenario table DataFrame.

    Returns:
        Normalized DataFrame ready for downstream use.
    """
    df = rows_df.copy()
    cont_rate_col = "contamination/contamination_rate/value"
    cont_unit_col = "contamination/contamination_unit"
    if cont_rate_col in df.columns:
        df[cont_rate_col] = df[cont_rate_col].fillna("None")
    if cont_unit_col in df.columns:
        df[cont_unit_col] = df[cont_unit_col].replace("", "plant").fillna("plant")
    else:
        df[cont_unit_col] = "plant"
    return _normalize_rows(df)


def _normalize_proportion_value(val) -> float:
    """Normalize inspection proportion values for scenario tables.

    Values less than or equal to zero are replaced with 0.02 (2%).

    Args:
        val: Raw value (string or numeric).

    Returns:
        Normalized float value.
    """
    try:
        normalized = float(val)
    except Exception:
        normalized = 0.0
    return 0.02 if normalized <= 0 else normalized


def _default_template_columns(rows_df: pd.DataFrame) -> list[str]:
    """Infer default scenario-table column order from the template.

    Args:
        rows_df: Current scenario rows.

    Returns:
        List of column names. Uses the template scenario CSV if present,
        otherwise falls back to current DataFrame columns.
    """
    if TEMPLATE_SCENARIO.exists():
        return pd.read_csv(TEMPLATE_SCENARIO, nrows=0).columns.tolist()
    return rows_df.columns.tolist()


def _build_scenario_row(scenario_label: str, consignment_choice: Path, compliance_choice: Path, param_choice: str, param_sets: dict) -> dict:
    """Construct a single scenario row from chosen inputs.

    Args:
        scenario_label: Scenario name to use in the row.
        consignment_choice: Path to selected consignment (RBS) CSV file.
        compliance_choice: Path to selected compliance policy file.
        param_choice: Key of the parameter set selected from ``param_sets``.
        param_sets: Dictionary of saved contamination parameter sets.

    Returns:
        Dictionary representing one scenario row suitable for a scenario table.
    """
    param_snapshot = param_sets.get(param_choice, {})
    scenario_row = {
        "name": scenario_label,
        "consignment/input_file/file_name": consignment_choice.name,
        "inspection/compliance_table/file_name": compliance_choice.name,
        "consignment/generation_method": "RBS",
        "consignment/input_file/file_type": "RBS",
        "contamination/contamination_unit": "plant",
        "contamination/contamination_rate/distribution": "beta-binomial",
        "contamination/contamination_rate/value": "",
        "contamination/arrangement": "random",
        "inspection/sample_strategy": "rbs",
        "inspection/proportion/value": 0.02,
        "inspection/unit": "sample_units",
        "inspection/min_boxes": 0,
        "inspection/selection_strategy": "random",
        "inspection/within_box_proportion": 1,
    }

    if isinstance(param_snapshot, dict) and param_snapshot and all(isinstance(v, dict) for v in param_snapshot.values()):
        for key, pdict in param_snapshot.items():
            base = f"contamination/contamination_rate/beta_binomial_parameters/{key}"
            scenario_row[f"{base}/alpha"] = pdict.get("alpha")
            scenario_row[f"{base}/beta"] = pdict.get("beta")
            scenario_row[f"{base}/mu"] = pdict.get("mu")
            scenario_row[f"{base}/rho"] = pdict.get("rho")
            scenario_row[f"{base}/D"] = pdict.get("D")
            scenario_row[f"{base}/theta"] = pdict.get("theta")
            scenario_row[f"{base}/J"] = pdict.get("J")
            if "p" in pdict:
                scenario_row[f"{base}/p"] = pdict.get("p")
    else:
        base = "contamination/contamination_rate/beta_binomial_parameters/default"
        scenario_row[f"{base}/alpha"] = param_snapshot.get("alpha")
        scenario_row[f"{base}/beta"] = param_snapshot.get("beta")
        scenario_row[f"{base}/theta"] = param_snapshot.get("theta")
        if "p" in param_snapshot:
            scenario_row[f"{base}/p"] = param_snapshot.get("p")
    return scenario_row


def _render_file_inventory(label: str, values, formatter) -> None:
    """Render a compact inventory line for available files.

    Args:
        label: Category label (e.g., "Consignments").
        values: Iterable of values (e.g., Paths or strings).
        formatter: Callable that formats the values into a display string.
    """
    st.write(f"**{label} ({len(values)}):** {formatter(values) if values else 'none'}")


def _copy_inputs(rows_df: pd.DataFrame, scenario_dir: Path) -> None:
    """Copy referenced input files into an experiment directory.

    The function copies:

    * Consignment (RBS) CSVs.
    * Compliance policy pickles.
    * Contamination parameter sets snapshot.
    * A config.yml file (from various candidate locations).

    Args:
        rows_df: DataFrame of scenario rows with consignment/compliance paths.
        scenario_dir: Destination directory for the experiment.

    Returns:
        List of filenames that were successfully copied.

    Raises:
        FileNotFoundError: If required consignment/compliance/config files
            cannot be located.
    """
    missing: list[str] = []
    copied_files: list[str] = []
    cons_col = "consignment/input_file/file_name"
    if cons_col in rows_df.columns:
        vals = [v for v in rows_df[cons_col].dropna().tolist() if v]
        if vals:
            for val in vals:
                name = Path(str(val)).name
                _copy_first_existing_file(
                    name,
                    scenario_dir,
                    [Path(str(val)), default_paths.tmp_dir() / "consignments" / name, Path(name)],
                    copied_files,
                    missing,
                )
        else:
            missing.append("consignment file (none listed)")
    else:
        missing.append("consignment file column missing")

    comp_col = "inspection/compliance_table/file_name"
    if comp_col in rows_df.columns:
        vals = [v for v in rows_df[comp_col].dropna().tolist() if v]
        if vals:
            for val in vals:
                name = Path(str(val)).name
                _copy_first_existing_file(
                    name,
                    scenario_dir,
                    [Path(str(val)), default_paths.tmp_dir() / "compliance" / name, Path(name)],
                    copied_files,
                    missing,
                )
        else:
            missing.append("compliance file (none listed)")
    else:
        missing.append("compliance file column missing")

    # Copy contamination parameter sets snapshot
    if CONTAM_PARAM_PATH.exists():
        (scenario_dir / "contamination_parameter_sets.json").write_bytes(
            CONTAM_PARAM_PATH.read_bytes()
        )

    # Copy config
    config_candidates = []
    if state.get("paths") and getattr(state["paths"], "config", None):
        config_candidates.append(Path(state["paths"].config))
    config_candidates.append(default_paths.tmp_dir() / "config.yml")
    config_candidates.append(default_paths.input_data_dir() / "config.yml")
    config_src = next((p for p in config_candidates if p.exists()), None)
    if config_src:
        (scenario_dir / CONFIG_FILENAME).write_bytes(config_src.read_bytes())
        copied_files.append(CONFIG_FILENAME)
    else:
        missing.append("config.yml")
    if missing:
        raise FileNotFoundError("; ".join(missing))
    return copied_files


def _normalize_rows(rows_df: pd.DataFrame) -> pd.DataFrame:
    """Normalize scenario rows to avoid RBS runtime errors.

    This function enforces:

    * ``inspection/unit`` = "sample_units"
    * ``inspection/sample_strategy`` defaults to "rbs"
    * ``inspection/proportion/value`` is positive (defaults to 0.02)
    * Beta-binomial alpha/beta parameters are positive and non-zero.

    Args:
        rows_df: Scenario table DataFrame.

    Returns:
        Normalized DataFrame.
    """
    df = rows_df.copy()
    if "inspection/unit" in df.columns:
        df["inspection/unit"] = "sample_units"
    if "inspection/sample_strategy" in df.columns:
        df["inspection/sample_strategy"] = df["inspection/sample_strategy"].replace("", "rbs").fillna("rbs")
    if "inspection/proportion/value" in df.columns:
        df["inspection/proportion/value"] = df["inspection/proportion/value"].apply(_normalize_proportion_value)
    alpha_col = "contamination/contamination_rate/beta_binomial_parameters/alpha"
    beta_col = "contamination/contamination_rate/beta_binomial_parameters/beta"
    if alpha_col in df.columns:
        df[alpha_col] = df[alpha_col].apply(lambda v: 0.01 if pd.isna(v) or float(v) <= 0 else float(v))
    if beta_col in df.columns:
        df[beta_col] = df[beta_col].apply(lambda v: 5.0 if pd.isna(v) or float(v) <= 0 else float(v))
    return df



import pandas as pd
import streamlit as st

def _load_policy_df(pkl_path):
    """Load the RBS Policy pickle into a DataFrame, handling several common dict shapes."""
    try:
        obj = pd.read_pickle(pkl_path)
    except Exception as exc:  # pylint: disable=broad-except
        st.error(f"Unable to read RBS policy file: {exc}")
        return None

    # Case 1: already a DataFrame
    if isinstance(obj, pd.DataFrame):
        return obj

    # Case 2: list of dicts -> DataFrame
    if isinstance(obj, list) and obj and isinstance(obj[0], dict):
        try:
            return pd.DataFrame(obj)
        except Exception as exc:  # pylint: disable=broad-except
            st.error(f"Could not convert list-of-dicts policy to DataFrame: {exc}")
            return None

    # Case 3: dict; try a few patterns
    if isinstance(obj, dict):
        # a) dict-of-dicts: treat values as row dicts
        if all(isinstance(v, dict) for v in obj.values()):
            try:
                return pd.DataFrame.from_dict(obj, orient="index")
            except Exception as exc:  # pylint: disable=broad-except
                st.error(f"Could not convert dict-of-dicts policy to DataFrame: {exc}")
                return None

        # b) dict-of-lists/scalars: try DataFrame() directly
        try:
            return pd.DataFrame(obj)
        except Exception:
            # c) as a last resort, treat the whole dict as one row
            try:
                return pd.DataFrame([obj])
            except Exception as exc:  # pylint: disable=broad-except
                st.error(f"Could not convert dict policy to DataFrame: {exc}")
                return None

    st.error(f"Unsupported RBS policy object type: {type(obj)}")
    return None





tabs = st.tabs(["Saved Experiment Packages", "Upload Custom Scenario", "Build Experiments"])

# --- Tab 1: Upload custom scenario -------------------------------------------
with tabs[0]:
    st.write("Review saved experiment packages, preview their scenario tables, or remove a package you no longer need.")
    saved_files = list(SCENARIO_ROOT.glob("*/scenario_table.csv"))

    if not saved_files:
        st.info("No experiments saved yet.")
    else:
        render_labeled_help(
            "Select an experiment package",
            "Choose a saved experiment package to preview its scenario table and optionally delete the entire package directory.",
        )
        sel = st.selectbox(
            "Select an experiment set",
            saved_files,
            format_func=lambda p: p.parent.name,
            label_visibility="collapsed",
        )
        try:
            preview = pd.read_csv(sel)
            st.dataframe(preview, use_container_width=True)
            st.caption(f"Path: {sel}")
            if st.button("Delete this experiment package", type="secondary"):
                try:
                    shutil.rmtree(sel.parent)
                    st.success(f"Deleted {sel.parent}")
                    st.rerun()
                except Exception as exc:  # pylint: disable=broad-except
                    st.error(f"Unable to delete experiment: {exc}")
        except Exception as exc:  # pylint: disable=broad-except
            st.error(f"Unable to preview experiment: {exc}")

with tabs[1]:
    st.subheader("Upload custom scenario table")
    st.write("Upload a scenario CSV and save it as a new experiment package under tmp/experiments.")
    render_labeled_help(
        "Upload custom scenario table",
        "Upload a scenario CSV to create a new experiment package under tmp/experiments.",
    )
    uploaded = st.file_uploader(
        "Upload scenario CSV",
        type=["csv"],
        key="custom_scenario_upload",
        label_visibility="collapsed",
    )
    render_labeled_help(
        "Save as experiment package name",
        "Name used for the experiment package folder when the uploaded scenario table is saved.",
    )
    custom_name = st.text_input("Save as experiment package name", value="custom_experiment", label_visibility="collapsed")

    if uploaded:
        try:
            uploaded.seek(0)
            df_preview = pd.read_csv(uploaded)
            st.dataframe(df_preview.head(50), use_container_width=True)
        except Exception:  # pylint: disable=broad-except
            st.info("Unable to preview upload.")

    render_labeled_help(
        "Save custom scenario table",
        "Write the uploaded scenario table into a new experiment package in tmp/experiments.",
    )
    if st.button("Save custom scenario table", type="primary", disabled=uploaded is None):
        try:
            uploaded.seek(0)
            df = pd.read_csv(uploaded)
            set_slug = _slugify(custom_name)
            scenario_dir = SCENARIO_ROOT / set_slug
            scenario_dir.mkdir(parents=True, exist_ok=True)
            dest = scenario_dir / "scenario_table.csv"
            df.to_csv(dest, index=False)
            _update_state_paths(scenario_table=dest)
            st.success(f"Saved custom scenario table to {dest}")
        except Exception as exc:  # pylint: disable=broad-except
            st.error(f"Failed to save custom scenario table: {exc}")

# --- Tab 2: Build experiments -------------------------------------------------
with tabs[2]:
    st.subheader("Build experiments")
    st.write("Combine consignment files, contamination settings, and compliance policies into runnable scenario rows.")
    state.setdefault("experiment_rows", [])
    col_left, col_right = st.columns([2, 1])

    consignment_files = _list_files(TMP_DIR / "consignments", "*.csv")
    compliance_files = _list_files(TMP_DIR / "compliance", "*.pkl")
    param_sets = _load_param_sets()
    param_keys = list(param_sets.keys())

    with col_left:
        render_labeled_help(
            "Scenario label",
            "Unique label for the experiment (i.e., scenario). Existing scenarios with the same label are replaced when added.",
        )
        scenario_label = st.text_input(
            "Scenario label",
            value=f"scenario_{len(state.get('experiment_rows', [])) + 1}",
            label_visibility="collapsed",
        )

        render_labeled_help(
            "Consignments",
            "Choose the .csv file of consignments generated on Page 1.",
        )
        consignment_choice = (
            st.selectbox(
                "Consignment (RBS) file",
                consignment_files,
                format_func=lambda p: p.name,
                label_visibility="collapsed",
            )
            if consignment_files
            else None
        )

        render_labeled_help(
            "Contamination parameter set",
            "Choose the contamination parameter set generated on Page 2 that should be used in this experiment.",
        )
        param_choice = (
            st.selectbox("Contamination parameter set", param_keys, label_visibility="collapsed")
            if param_keys
            else None
        )

        render_labeled_help(
            "RBS Policy",
            "Choose the compliance policy saved on Page 3 that the simulation will use for this scenario.",
        )
        compliance_choice = (
            st.selectbox(
                "RBS compliance policy",
                compliance_files,
                format_func=lambda p: p.name,
                label_visibility="collapsed",
            )
            if compliance_files
            else None
        )

    with col_right:
        render_labeled_help(
            "Files available",
            "Inspect the files currently available for scenario construction before adding a row.",
        )
        with st.expander("Files available", expanded=True):
            _render_file_inventory("Consignments", consignment_files, lambda files: ", ".join(p.name for p in files))
            _render_file_inventory("Contamination", param_keys, lambda files: ", ".join(files))
            _render_file_inventory("RBS Compliance Policies", compliance_files, lambda files: ", ".join(p.name for p in files))

    add_ready = all([scenario_label, consignment_choice, compliance_choice, param_choice])
    render_labeled_help(
        "Add scenario row",
        "Append the current selections as a scenario row, or replace an existing row with the same label.",
    )
    if st.button("Add scenario row", type="primary", disabled=not add_ready):
        scenario_row = _build_scenario_row(scenario_label, consignment_choice, compliance_choice, param_choice, param_sets)

        # If a scenario with this label exists, replace it; otherwise append
        replaced = False
        for idx, row in enumerate(state["experiment_rows"]):
            if row.get("name") == scenario_label:
                state["experiment_rows"][idx] = scenario_row
                replaced = True
                break
        if not replaced:
            state["experiment_rows"].append(scenario_row)
            st.success(f"Added scenario row '{scenario_label}'")
        else:
            st.success(f"Updated scenario row '{scenario_label}'")

    rows_df = pd.DataFrame(state["experiment_rows"])
    if not rows_df.empty:
        st.dataframe(rows_df, use_container_width=True)
    else:
        st.info("Add at least one scenario row.")

    col_actions = st.columns(2)
    with col_actions[0]:
        render_labeled_help(
            "Clear current rows",
            "Remove every scenario row currently staged in this session.",
        )
        if st.button("Clear current rows", type="secondary", disabled=rows_df.empty):
            state["experiment_rows"] = []
            st.rerun()
    with col_actions[1]:
        render_labeled_help(
            "Remove last row",
            "Drop only the most recently added scenario row from the current session.",
        )
        if st.button("Remove last row", type="secondary", disabled=rows_df.empty):
            if state["experiment_rows"]:
                state["experiment_rows"].pop()
            st.rerun()

    render_labeled_help(
        "Experiment set name (CSV)",
        "Folder and file name used when saving the assembled experiment package.",
    )
    scenario_set = st.text_input("Experiment set name (CSV)", value="experiment_set_1", label_visibility="collapsed")
    can_save = bool(scenario_set) and not rows_df.empty

    render_labeled_help(
        "Save experiment package",
        "Write the current scenario rows and any referenced inputs into tmp/experiments as a runnable package.",
    )
    if st.button("Save experiment package", type="primary", disabled=not can_save):
        set_slug = _slugify(scenario_set)
        scenario_dir = SCENARIO_ROOT / set_slug
        try:
            scenario_dir.mkdir(parents=True, exist_ok=True)
            scenario_path = scenario_dir / SCENARIO_FILENAME
            raw_rows_df = rows_df.copy()
            template_cols = _default_template_columns(rows_df)
            if "consignment name" in template_cols and "consignment/input_file/file_name" not in template_cols:
                template_cols = [c for c in template_cols if c != "consignment name"]
                template_cols.append("consignment/input_file/file_name")
            if "inspection name" in template_cols and "inspection/compliance_table/file_name" not in template_cols:
                template_cols = [c for c in template_cols if c != "inspection name"]
                template_cols.append("inspection/compliance_table/file_name")

            ordered_targets = [
                "consignment/input_file/file_name",
                "inspection/compliance_table/file_name",
            ]
            filtered_cols = [c for c in template_cols if c not in ordered_targets]
            anchor = next(
                (i for i, c in enumerate(filtered_cols) if str(c).startswith("Unnamed")),
                len(filtered_cols),
            )
            template_cols = (
                filtered_cols[:anchor]
                + [c for c in ordered_targets if c in template_cols]
                + filtered_cols[anchor:]
            )

            rows_df = _apply_scenario_defaults(_scenario_row_to_portable_paths(rows_df, set_slug))
            scenario_table = rows_df.reindex(columns=template_cols, fill_value="")
            scenario_table.to_csv(scenario_path, index=False)

            copied = _copy_inputs(raw_rows_df, scenario_dir)
            st.caption(f"Copied files to {scenario_dir}: {', '.join(copied)}")

            _update_state_paths(scenario_table=scenario_path)
            st.session_state["page4_save_success"] = f"Experiment saved to {scenario_path}"
            st.rerun()
        except Exception as exc:  # pylint: disable=broad-except
            st.error(f"Failed to save experiment: {exc}")


# --- Bottom navigation --------------------------------------------------------
st.divider()
nav_cols = st.columns(2)

with nav_cols[0]:
    if st.button("Reset and Return Home", type="secondary"):
        try:
            from .tmp_utils import reset_tmp_directory
            reset_tmp_directory(TMP_DIR)
        except Exception:
            pass
        st.session_state.clear()
        init_state()
        st.switch_page("frontend.py")

with nav_cols[1]:
    prev_next = st.columns(2)
    with prev_next[0]:
        if st.button("Previous Page", type="primary", key="nav_back_page4"):
            st.switch_page("pages/3_Inspection_Process.py")
    with prev_next[1]:
        if st.button("Next Page", type="primary", key="nav_forward_page5"):
            st.switch_page("pages/5_Run_Simulation.py")
