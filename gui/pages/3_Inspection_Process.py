# © 2026 The Johns Hopkins University Applied Physics Laboratory LLC

from pathlib import Path
from typing import Optional
import pickle
import shutil

from gui.runtime_warnings import suppress_optional_dependency_warnings

suppress_optional_dependency_warnings()

import pandas as pd
import streamlit as st


from gui.models import init_state
from gui.navigation import render_sidebar_navigation
from gui.page_styles import apply_shared_page_styles, render_labeled_help, render_page_intro
from gui.slippage_ui import get_slippage_state, set_paths, create_default_paths
from popsborder.generator import create_producer_mapping, preprocess_producer_name
from popsborder.inputs import build_compliance_lookup_table, load_compliance_lookup_csv
from popsborder.inspections import normalize_rbs_variables_using_risk_unit_config


st.set_page_config(
    page_title="Inspection Process",
    page_icon=":mag_right:",
    layout="wide",
)
init_state()

state = get_slippage_state()
render_sidebar_navigation()
apply_shared_page_styles()
state.setdefault("compliance_mapping_path", Path("data_input/compliance_mapping_detection_confidence_levels.csv"))
TMP_DIR = Path("tmp")
TMP_DIR.mkdir(exist_ok=True)
COMPLIANCE_ROOT = TMP_DIR / "compliance"
COMPLIANCE_ROOT.mkdir(parents=True, exist_ok=True)
COMPLIANCE_SOURCE_ROOT = COMPLIANCE_ROOT / "_sources"
COMPLIANCE_SOURCE_ROOT.mkdir(parents=True, exist_ok=True)


def _pick_compliance_column(df: pd.DataFrame) -> Optional[str]:
    """Heuristically pick a column that represents compliance categories.

    The function first looks for any column whose name contains
    ``"compliance"`` (case-insensitive). If none is found, it returns
    the first string (object dtype) column.

    Args:
        df: DataFrame to search.

    Returns:
        Column name or None if no suitable column is found.
    """
    for col in df.columns:
        if "compliance" in col.lower():
            return col
    string_columns = [col for col in df.columns if df[col].dtype == "object"]
    return string_columns[0] if string_columns else None


def _first_matching_column(df: pd.DataFrame, candidates: list[str]) -> Optional[str]:
    """Return the first column matching one of the candidate names.

    A case-insensitive comparison is used to match against ``candidates``.

    Args:
        df: DataFrame whose columns will be searched.
        candidates: List of candidate column names.

    Returns:
        Matching column name from ``df`` or None if no match is found.
    """
    lower_map = {c.lower(): c for c in df.columns}
    for candidate in candidates:
        if candidate.lower() in lower_map:
            return lower_map[candidate.lower()]
    return None


def _compliance_cell_style(value: object) -> str:
    """Return CSS style string for a compliance-level cell.

    Colors cells based on qualitative compliance descriptors such as
    "tissue", "high", "medium", "low", "poor".

    Args:
        value: Cell value to style.

    Returns:
        CSS style string usable in a pandas Styler context.
    """
    text = str(value).strip().lower()
    if "tissue" in text:
        return "background-color: #6a994e; color: white; font-weight: 600;"
    if "high" in text:
        return "background-color: #386641; color: white; font-weight: 600;"
    if "medium" in text:
        return "background-color: #f2cc8f; color: #222; font-weight: 600;"
    if "low" in text:
        return "background-color: #f4a261; color: #222; font-weight: 600;"
    if "poor" in text:
        return "background-color: #bc4749; color: white; font-weight: 600;"
    return ""


def _numeric_heat_style(value: object, base_color: str) -> str:
    """Return a background color style based on a numeric value in [0, 1].

    Args:
        value: Cell value (expected numeric).
        base_color: RGB triplet string (e.g., ``"31, 119, 180"``).

    Returns:
        CSS style string with an alpha-scaled background color.
    """
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return ""
    numeric = max(0.0, min(1.0, numeric))
    alpha = 0.15 + (0.75 * numeric)
    return f"background-color: rgba({base_color}, {alpha:.3f}); font-weight: 600;"


def _read_uploaded_csv(uploaded_file) -> Optional[pd.DataFrame]:
    """Read a CSV file from a Streamlit upload widget into a DataFrame.

    Args:
        uploaded_file: File-like object from ``st.file_uploader``.

    Returns:
        DataFrame if parsing succeeds, otherwise None.
    """
    if uploaded_file is None:
        return None
    try:
        uploaded_file.seek(0)
        return pd.read_csv(uploaded_file)
    except Exception:  # pylint: disable=broad-except
        return None


def _style_policy_dataframe(df: pd.DataFrame):
    """Apply styling to a policy DataFrame for interactive preview.

    Styles:

    * Compliance column using qualitative shading.
    * Detection and confidence columns using numeric heatmaps.

    Args:
        df: DataFrame containing one or more of the columns:
            "Compliance", "Detection Level", "Confidence Level(s)".

    Returns:
        pandas Styler with applied styles.
    """
    compliance_col = _first_matching_column(df, ["Compliance"])
    detection_col = _first_matching_column(df, ["Detection Level"])
    confidence_col = _first_matching_column(df, ["Confidence Levels", "Confidence Level"])
    styled_df = df.style
    if compliance_col:
        styled_df = styled_df.map(_compliance_cell_style, subset=[compliance_col])
    if detection_col:
        styled_df = styled_df.map(
            lambda v: _numeric_heat_style(v, "31, 119, 180"),
            subset=[detection_col],
        )
    if confidence_col:
        styled_df = styled_df.map(
            lambda v: _numeric_heat_style(v, "76, 149, 108"),
            subset=[confidence_col],
        )
    return styled_df


def _save_policy_artifact(
    policy_name: str,
    compliance_csv_path: Path,
    mapping_csv_path: Optional[Path] = None,
    *,
    direct_lookup_csv: bool = False,
    producer_grouping_path: Optional[Path] = None,
) -> Path:
    """Create and persist a combined RBS compliance policy artifact.

    Steps:

    1. Normalize producer values (if a producer grouping file is provided).
    2. Optionally load detection/confidence mapping from a mapping CSV and
       build a lookup table.
    3. Normalize RBS variables using :func:`normalize_rbs_variables_using_risk_unit_config`.
    4. Store the resulting compliance table and policy preview as a
       pickled dictionary in ``COMPLIANCE_ROOT``.

    Args:
        policy_name: Desired base name for the policy file (without extension).
        compliance_csv_path: Path to the base compliance CSV.
        mapping_csv_path: Optional mapping CSV for detection/confidence levels.
        direct_lookup_csv: If True, treat the compliance CSV as already
            containing detection/confidence data and skip the mapping step.
        producer_grouping_path: Optional path to a producer grouping CSV
            used to normalize producer values.

    Returns:
        Path to the created ``.pkl`` policy artifact.

    Raises:
        FileNotFoundError: If mapping CSV is required but missing.
    """
    policy_name = policy_name.strip() or "rbs_compliance_policy"
    policy_path = COMPLIANCE_ROOT / f"{policy_name}.pkl"
    compliance_preview_df = pd.read_csv(compliance_csv_path)
    compliance_preview_df = _normalize_policy_producer_values(
        compliance_preview_df,
        producer_grouping_path=producer_grouping_path,
    )
    normalized_compliance_path = COMPLIANCE_SOURCE_ROOT / f"{policy_name}_normalized_compliance_table.csv"
    normalized_compliance_path.parent.mkdir(parents=True, exist_ok=True)
    compliance_preview_df.to_csv(normalized_compliance_path, index=False)
    if direct_lookup_csv:
        compliance_table = load_compliance_lookup_csv(normalized_compliance_path)
        preview_df = compliance_preview_df
    else:
        if mapping_csv_path is None or not mapping_csv_path.exists():
            raise FileNotFoundError("Compliance mapping detection/confidence file is required.")
        mapping_preview_df = pd.read_csv(mapping_csv_path)
        compliance_table = build_compliance_lookup_table(
            compliance_table_filepath=normalized_compliance_path,
            mapping_filepath=mapping_csv_path,
        )
        preview_df = compliance_preview_df.merge(
            mapping_preview_df,
            on="Compliance",
            how="left",
        )
        ordered_preview_cols = compliance_preview_df.columns.tolist() + [
            col for col in mapping_preview_df.columns.tolist() if col not in compliance_preview_df.columns
        ]
        preview_df = preview_df[[col for col in ordered_preview_cols if col in preview_df.columns]]
    updated_vars, _, _ = normalize_rbs_variables_using_risk_unit_config(
        compliance_table.get("rbs_variables", [])
    )
    compliance_table["rbs_variables"] = updated_vars
    compliance_table["_policy_preview"] = preview_df.to_dict(orient="records")
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    with open(policy_path, "wb") as handle:
        pickle.dump(compliance_table, handle, protocol=pickle.HIGHEST_PROTOCOL)
    return policy_path


def _normalize_policy_producer_values(
    compliance_df: pd.DataFrame,
    *,
    producer_grouping_path: Optional[Path] = None,
) -> pd.DataFrame:
    """Normalize producer-related columns in a compliance table.

    Uses RiskUnitConfig aliasing to identify producer-group columns and,
    if a grouping file is available, maps raw producer names to the
    desired group labels.

    Args:
        compliance_df: Compliance table with a "Compliance" column and
            one or more producer-like columns.
        producer_grouping_path: Optional path to a producer grouping CSV
            used by :func:`create_producer_mapping`.

    Returns:
        DataFrame with normalized producer columns (if applicable).
    """
    if compliance_df is None or compliance_df.empty or "Compliance" not in compliance_df.columns:
        return compliance_df
    key_cols = compliance_df.columns[:compliance_df.columns.get_loc("Compliance")].tolist()
    if not key_cols:
        return compliance_df
    _, mapping, _ = normalize_rbs_variables_using_risk_unit_config(key_cols)
    producer_cols = [original for original, canonical in mapping.items() if canonical == "producer_group"]
    if not producer_cols:
        return compliance_df

    normalized = compliance_df.copy()
    producer_mapping = None
    if producer_grouping_path is not None and Path(producer_grouping_path).exists():
        producer_grouping_df = pd.read_csv(producer_grouping_path)
        producer_mapping = create_producer_mapping(producer_grouping_df, use_shortest_name=True)

    for col in producer_cols:
        if col not in normalized.columns:
            continue

        def _map_value(value: object) -> object:
            if pd.isna(value):
                return value
            if producer_mapping is None:
                return value
            return producer_mapping.get(preprocess_producer_name(value), str(value).strip())

        normalized[col] = normalized[col].map(_map_value)

    return normalized


st.warning(
    "**Test Deployment Notice: This is a test deployment with limited functionality and is under active development. "
    "Features may be incomplete and subject to change. Results have not been validated.**"
)
st.title("Page 3 - Inspection Process")
render_page_intro(
    "Ingest the compliance lookup table, configure low/medium/high types, and review RBS parameters."
)

# tabs = st.tabs(["Saved RBS Compliance Policy", "Upload Table", "Create Policy Manually"]) # UNCOMMENT FOR MANUAL POLICY CREATION
tabs = st.tabs(["Saved RBS Compliance Policy", "Upload Table"]) # COMMENT OUT FOR MANUAL POLICY CREATION

with tabs[0]:
    st.subheader("Saved RBS compliance policy")
    st.write("Open an existing policy file to review the stored rules and preview the generated table.")
    saved_files = sorted(COMPLIANCE_ROOT.glob("*.pkl"))
    if not saved_files:
        st.info("No RBS compliance policies saved yet in tmp/compliance.")
    else:
        render_labeled_help(
            "Select a saved RBS compliance policy",
            "Choose a previously saved compliance policy file to inspect its stored rules and preview table.",
        )
        sel = st.selectbox(
            "Select a saved RBS compliance policy",
            saved_files,
            format_func=lambda p: p.name,
            label_visibility="collapsed",
        )
        try:
            with open(sel, "rb") as handle:
                policy = pickle.load(handle)
            rbs_variables = policy.get("rbs_variables", [])
            st.caption(f"RBS variables: {', '.join(rbs_variables) if rbs_variables else 'none'}")
            preview_rows = policy.get("_policy_preview")
            if preview_rows:
                policy_df = pd.DataFrame(preview_rows)
                styled_policy = _style_policy_dataframe(policy_df)
                st.dataframe(styled_policy, use_container_width=True, height=360)
            else:
                policy_rows = []
                for key, value in policy.items():
                    if key in {"rbs_variables", "_policy_preview"}:
                        continue
                    if isinstance(key, tuple):
                        row = {rbs_variables[idx]: key[idx] for idx in range(min(len(rbs_variables), len(key)))}
                        row["Detection Level"] = value[0] if isinstance(value, tuple) and len(value) > 0 else ""
                        row["Confidence Level"] = value[1] if isinstance(value, tuple) and len(value) > 1 else ""
                        policy_rows.append(row)
                policy_df = pd.DataFrame(policy_rows)
                if not policy_df.empty:
                    st.dataframe(policy_df, use_container_width=True, height=320)
            st.caption(f"Location: {sel}")
            if st.button("Delete this policy", type="secondary"):
                try:
                    sel.unlink()
                    st.success(f"Deleted {sel.name}")
                    st.rerun()
                except Exception as exc:  # pylint: disable=broad-except
                    st.error(f"Unable to delete policy: {exc}")
        except Exception as exc:  # pylint: disable=broad-except
            st.info(f"Unable to preview this policy file: {exc}")

with tabs[1]:
    st.subheader("Upload table")
    st.write("Upload compliance tables and their detection or confidence mappings for a new policy.")
    render_labeled_help(
        "Compliance level upload",
        "Upload the table that defines the compliance category assigned to each policy combination, such as origin and propagative material type.",
    )
    compliance_upload = st.file_uploader(
        "Upload CSV with compliance levels",
        type=["csv"],
        key="base_compliance_upload",
        label_visibility="collapsed",
    )
    upload_preview = None
    if compliance_upload is not None:
        upload_preview = _read_uploaded_csv(compliance_upload)
        if upload_preview is None:
            st.info("Unable to preview upload.")
    if upload_preview is not None:
        selected_column = _pick_compliance_column(upload_preview)
        styled_base = upload_preview.copy()
        if selected_column and selected_column in styled_base.columns:
            styled_base = styled_base.style.applymap(_compliance_cell_style, subset=[selected_column])
        st.markdown("**Compliance policy table**")
        st.dataframe(styled_base, use_container_width=True, height=360)

    render_labeled_help(
        "Detection/confidence mapping upload",
        "Upload the table that maps each compliance category to its detection level and confidence level values used by the inspection policy.",
    )
    mapping_upload = st.file_uploader(
        "Upload CSV with compliance level mapping of detection/confidence values",
        type=["csv"],
        key="compliance_mapping_upload",
        label_visibility="collapsed",
    )
    mapping_preview = None
    if mapping_upload is not None:
        mapping_preview = _read_uploaded_csv(mapping_upload)
        if mapping_preview is None:
            st.info("Unable to preview mapping upload.")

    if mapping_preview is not None:
        detection_col = _first_matching_column(mapping_preview, ["Detection Level"])
        confidence_col = _first_matching_column(mapping_preview, ["Confidence Levels", "Confidence Level"])
        compliance_col = _first_matching_column(mapping_preview, ["Compliance"])
        if compliance_col and detection_col and confidence_col:
            mapping_table = mapping_preview[[compliance_col, detection_col, confidence_col]].copy()
            mapping_table.columns = ["Compliance", "Detection Level", "Confidence Level"]
            styled_mapping = _style_policy_dataframe(mapping_table).format(
                {"Detection Level": "{:.2f}", "Confidence Level": "{:.2f}"}
            )
            st.markdown("**Detection/confidence mapping policy table**")
            st.dataframe(styled_mapping, use_container_width=True, height=260)
    render_labeled_help(
        "Save as name",
        "Name of the consolidated RBS compliance policy file that will be saved and used on downstream pages.",
    )
    save_name = st.text_input(
        "Save as name",
        value="rbs_compliance_policy",
        label_visibility="collapsed",
    )
    can_save_uploaded_policy = compliance_upload is not None and mapping_upload is not None
    render_labeled_help(
        "Save policy",
        "Create and persist a combined compliance policy file from the uploaded table and mapping inputs.",
    )
    if st.button("Save policy", type="primary", disabled=not can_save_uploaded_policy):
        try:
            if compliance_upload is None or mapping_upload is None:
                raise ValueError("Both the compliance table and the detection/confidence mapping file are required.")
            compliance_upload.seek(0)
            new_compliance_df = pd.read_csv(compliance_upload)
            compliance_csv_path = COMPLIANCE_SOURCE_ROOT / f"{save_name}_compliance_table.csv"
            compliance_csv_path.parent.mkdir(parents=True, exist_ok=True)
            new_compliance_df.to_csv(compliance_csv_path, index=False)

            mapping_upload.seek(0)
            mapping_df = pd.read_csv(mapping_upload)
            mapping_path = COMPLIANCE_SOURCE_ROOT / f"{save_name}_mapping.csv"
            mapping_path.parent.mkdir(parents=True, exist_ok=True)
            mapping_df.to_csv(mapping_path, index=False)
            state["compliance_mapping_path"] = mapping_path

            policy_path = _save_policy_artifact(
                save_name,
                compliance_csv_path,
                mapping_path,
                producer_grouping_path=state.get("producer_grouping_path"),
            )
            set_paths(compliance_lookup=policy_path)
            st.success(f"Saved RBS compliance policy to {policy_path}")
        except Exception as exc:  # pylint: disable=broad-except
            st.error(f"Failed to save compliance table: {exc}")


################################################################################
# Manual Consignment Generation Tab - begin
# UNCOMMENT BELOW FOR MANUAL POLICY CREATION
################################################################################

# with tabs[2]:
#     st.subheader("Manual Creation of RBS Compliance Policy ")
#     st.write("Build a custom compliance policy by selecting feature values and assigning policy levels.")

#     rbs_path = state["paths"].rbs_data
#     rbs_cols = []
#     if rbs_path and Path(rbs_path).exists():
#         try:
#             rbs_df = pd.read_csv(rbs_path, nrows=2000)
#             rbs_cols = [c for c in rbs_df.columns if rbs_df[c].dtype == "object"]
#         except Exception:  # pylint: disable=broad-except
#             rbs_cols = []
#     if not rbs_cols:
#         rbs_cols = ["Origin Location Country Name", "Propagative Material type", "Pathway", "Inspection Location"]

#     render_labeled_help(
#         "Select feature columns to combine",
#         "Choose the compliance feature columns that will be cross-joined into manually created policy rows.",
#     )
#     multi_cols = st.multiselect(
#         "Select feature columns to combine",
#         options=rbs_cols,
#         default=rbs_cols[:2],
#         label_visibility="collapsed",
#     )
#     selections = []
#     for col_name in multi_cols:
#         values = []
#         if rbs_path and Path(rbs_path).exists():
#             try:
#                 values = sorted(rbs_df[col_name].dropna().astype(str).unique().tolist())
#             except Exception:  # pylint: disable=broad-except
#                 values = []
#         render_labeled_help(
#             f"Values for {col_name}",
#             f"Choose the values for {col_name} that should be included in the manual compliance policy.",
#         )
#         selected_vals = st.multiselect(
#             f"Values for {col_name}",
#             options=values or [],
#             key=f"comb_vals_{col_name}",
#             label_visibility="collapsed",
#         )
#         selections.append({"column": col_name, "values": selected_vals})

#     render_labeled_help(
#         "Compliance level for the new rows",
#         "Assign one compliance level to every row generated from the selected feature combinations.",
#     )
#     level_choice = st.selectbox("Compliance level for the new rows", ["Low", "Medium", "High"], label_visibility="collapsed")

#     detection_value = st.slider(
#         "Detection Level",
#         min_value=0.0,
#         max_value=1.,
#         step=.01,
#         value=0.1,          
#         help="Detection Level for Hypergeometric Sampling."
#     )

#     confidence_value = st.slider(
#         "Confidence Level",
#         min_value=0.0,
#         max_value=1.0,
#         value=0.95,
#         step=0.01,
#         help="Confidence Level for Hypergeometric Sampling."
#     )

#     render_labeled_help(
#         "Add rows to compliance table",
#         "Generate manual compliance rows from the selected feature combinations and append them to the working table below.",
#     )
#     if st.button("Add rows to compliance table", type="primary"):
#         rows = []
#         selected_cols = [s["column"] for s in selections]
#         from itertools import product

#         value_lists = []
#         for sel in selections:
#             vals = sel.get("values", [])
#             if not vals:
#                 value_lists = []
#                 break
#             value_lists.append(vals)
#         if not value_lists:
#             st.warning("Select at least one value for each chosen feature before adding rows.")
#         else:
#             for combo in product(*value_lists):
#                 row = {c: "" for c in selected_cols}
#                 for col, val in zip(selected_cols, combo):
#                     row[col] = val
#                 row["Compliance"] = level_choice
#                 row["Detection Level"] = detection_value
#                 row["Confidence Levels"] = confidence_value
#                 rows.append(row)
#             manual_df = state.get("manual_compliance_df")
#             new_df = pd.DataFrame(rows)
#             if manual_df is None:
#                 manual_df = new_df
#             else:
#                 # Align columns
#                 all_cols = list(set(manual_df.columns).union(set(new_df.columns)))
#                 manual_df = manual_df.reindex(columns=all_cols, fill_value="")
#                 new_df = new_df.reindex(columns=all_cols, fill_value="")
#                 manual_df = pd.concat([manual_df, new_df], ignore_index=True)
#             state["manual_compliance_df"] = manual_df
#             st.success(f"Added {len(rows)} rows at level {level_choice}.")
#             st.dataframe(manual_df, use_container_width=True)


#     manual_df = state.get("manual_compliance_df")
#     render_labeled_help(
#         "Save as name (manual)",
#         "File name used when saving the manually built compliance policy.",
#     )
#     manual_name = st.text_input(
#         "Save as name (manual)",
#         value="manual_compliance_policy",
#         label_visibility="collapsed",
#     )
#     can_save_manual_policy = manual_df is not None and not manual_df.empty
#     render_labeled_help(
#         "Save manual policy",
#         "Write the manually assembled compliance policy to disk so it can be reused on downstream pages.",
#     )
#     if st.button("Save manual policy", type="primary", disabled=not can_save_manual_policy):
#         target_path = COMPLIANCE_SOURCE_ROOT / f"{manual_name}.csv"
#         target_path.parent.mkdir(parents=True, exist_ok=True)
#         manual_df.to_csv(target_path, index=False)
#         policy_path = _save_policy_artifact(
#             manual_name,
#             target_path,
#             direct_lookup_csv=True,
#             producer_grouping_path=state.get("producer_grouping_path"),
#         )
#         set_paths(compliance_lookup=policy_path)
#         st.success(f"Manual RBS compliance policy saved to {policy_path}")


################################################################################
# Manual Consignment Generation Tab - end
# UNCOMMENT ABOVE FOR MANUAL POLICY CREATION
################################################################################

st.divider()
nav_cols = st.columns(3)
with nav_cols[0]:
    if st.button(
        "Reset and Return Home",
        type="secondary",
        key="nav_reset_page4",
        help="Delete temporary files and restart from the home page",
    ):
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
    if st.button("Previous Page", type="primary", key="nav_back_page3_proc"):
        st.switch_page("pages/2_Contamination_Fit.py")
with nav_cols[2]:
    if st.button("Next Page", type="primary", key="nav_forward_page5_proc"):
        st.switch_page("pages/4_Scenario_Experiments.py")

st.info("Inspection scenarios are managed on the experiment setup page.")
