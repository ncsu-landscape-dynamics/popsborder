# © 2026 The Johns Hopkins University Applied Physics Laboratory LLC

from pathlib import Path
import itertools
import shutil
import yaml
from typing import Optional

import altair as alt
import numpy as np
from gui.runtime_warnings import suppress_optional_dependency_warnings

suppress_optional_dependency_warnings()

import pandas as pd
import streamlit as st

from gui.models import init_state
from gui.navigation import render_sidebar_navigation
from gui.page_styles import (
    apply_shared_page_styles,
    render_labeled_help,
    render_metric_card,
    render_page_intro,
)
from gui.slippage_pipeline import SyntheticOptions, generate_synthetic_data
from gui.slippage_ui import (
    get_slippage_state,
    set_paths,
    set_synthetic_options,
)
from slippage_model_utils.references import GENERATOR_TARGET_COLUMNS

# Specify directory structure
APP_DIR = Path(__file__).parent.parent
TOP_LEVEL_DIR = APP_DIR.parent
TMP_DIR = Path(TOP_LEVEL_DIR / "tmp")
print(TMP_DIR)
TMP_DIR.mkdir(parents=True, exist_ok=True)
CONSIGNMENT_ROOT = TMP_DIR / "consignments"
CONSIGNMENT_ROOT.mkdir(parents=True, exist_ok=True)


def _consignment_dir() -> Path:
    """Return the root directory for consignment files under tmp.

    Ensures the base directory exists before returning it.

    Returns:
        Path to the consignment root directory.
    """
    base = CONSIGNMENT_ROOT
    base.mkdir(parents=True, exist_ok=True)
    return base

def _consignment_source_dir() -> Path:
    """Return the directory used to store seed/source RBS files.

    Ensures ``tmp/consignments/source`` exists before returning it.

    Returns:
        Path to the source directory for consignment seeds.
    """
    temp_dir = _consignment_dir() / "source"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def _consignment_paths(base_name: Optional[str] = None) -> dict[str, Path]:
    """Build canonical paths for consignment-related CSVs.

    Args:
        base_name: Base filename, without extension. Defaults to
            ``st.session_state["consignment_base_name"]`` or "consignment".

    Returns:
        Dictionary mapping keys (e.g., "uploaded_rbs", "manual_rbs") to
        CSV paths under the consignment directory.
    """
    base = _consignment_dir()
    base_name = base_name or st.session_state.get("consignment_base_name", "consignment") or "consignment"
    return {
        "uploaded_rbs": base / f"{base_name}.csv",
        "manual_rbs": base / f"{base_name}.csv",
    }


def _unique_path(path: Path) -> Path:
    """Return a path that does not conflict with existing files.

    If ``path`` already exists, an incrementing suffix (``_1``, ``_2``, ...)
    is appended to the stem before the extension until a free name is found.

    Args:
        path: Desired output path.

    Returns:
        A path guaranteed not to exist yet.
    """
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    for i in itertools.count(1):
        candidate = path.with_name(f"{stem}_{i}{suffix}")
        if not candidate.exists():
            return candidate


def _save_rbs_to_tmp(
    current_rbs: Optional[Path],
    pending_manual_rbs: Optional[pd.DataFrame],
    pending_upload_rbs: Optional[pd.DataFrame] = None,
    *,
    base_name: Optional[str] = None,
    producer_grouping_path: Optional[Path] = None,
    status=None,
) -> tuple[bool, str]:
    """Save or generate RBS data into tmp/consignments.

    Depending on the current consignment source in state
    (synthetic vs historical), this helper either:

    * Generates synthetic RBS records using ``generate_synthetic_data``,
      or
    * Saves manual/historical RBS data as-is.

    Args:
        current_rbs: Existing RBS CSV path in use, if any.
        pending_manual_rbs: Manual RBS DataFrame pending save (for
            historical mode).
        pending_upload_rbs: RBS DataFrame uploaded via UI (for seed or
            direct save).
        base_name: Base filename used when saving to tmp/consignments.
        producer_grouping_path: Optional producer-grouping CSV path used
            when generating synthetic data.

    Returns:
        Tuple ``(ok, message)`` where ``ok`` indicates success and
        ``message`` contains a human-readable status message.
    """
    paths_map = _consignment_paths(base_name)
    base_name = base_name or st.session_state.get("consignment_base_name", "consignment") or "consignment"
    if current_rbs is None and pending_manual_rbs is None and pending_upload_rbs is None:
        return False, "No RBS data available. Upload a calculator file or create consignments manually first."
    try:
        state = get_slippage_state()
        cons_source = state.get("consignment_source", "synthetic")

        if cons_source == "synthetic":
            # Always generate a new synthetic file into a unique output
            dest_rbs = _unique_path(paths_map["uploaded_rbs"])
            dest_rbs.parent.mkdir(parents=True, exist_ok=True)
            if pending_upload_rbs is not None:
                seed_path = _consignment_source_dir() / f"{base_name}_seed_rbs.csv"
                pending_upload_rbs.to_csv(seed_path, index=False)
                state["pending_rbs_upload"] = None
            elif current_rbs and Path(current_rbs).exists():
                seed_path = Path(current_rbs)
            elif paths_map["uploaded_rbs"].exists():
                seed_path = paths_map["uploaded_rbs"]
            else:
                return False, "No RBS seed available for synthetic generation. Upload/select an RBS file first."

            options: SyntheticOptions = state.get("synthetic_options", SyntheticOptions())

            synth_df = generate_synthetic_data(
                seed_path,
                dest_rbs,
                options,
                producer_grouping_path=producer_grouping_path,
                status=status,  # pass through
            )
            state["rbs_preview"] = synth_df.head(10)
            set_paths(rbs_data=dest_rbs, synthetic_seed=seed_path)
            return True, f"Generated and saved RBS file with base '{base_name}' to tmp/consignments."

        # Historical/manual: write exactly what is provided
        dest_rbs = _unique_path(paths_map["uploaded_rbs"])
        dest_rbs.parent.mkdir(parents=True, exist_ok=True)
        if pending_upload_rbs is not None:
            pending_upload_rbs.to_csv(dest_rbs, index=False)
            state["rbs_preview"] = pending_upload_rbs.head(10)
            state["pending_rbs_upload"] = None
            set_paths(rbs_data=dest_rbs)
            return True, f"Saved RBS file with base '{base_name}' to tmp/consignments."
        if pending_manual_rbs is not None:
            pending_manual_rbs.to_csv(dest_rbs, index=False)
            state["rbs_preview"] = pending_manual_rbs.head(10)
            set_paths(rbs_data=dest_rbs)
            return True, f"Saved RBS file with base '{base_name}' to tmp/consignments."
        if current_rbs is not None and Path(current_rbs).exists():
            if Path(current_rbs).resolve() != dest_rbs.resolve():
                shutil.copy(current_rbs, dest_rbs)
            state["rbs_preview"] = pd.read_csv(dest_rbs).head(10)
            set_paths(rbs_data=dest_rbs)
            return True, f"Saved RBS file with base '{base_name}' to tmp/consignments."

        return False, "No RBS source file found."

    except Exception as exc:  # pylint: disable=broad-except
        return False, f"Unable to save consignment files: {exc}"


def _save_historical_rbs(
    current_rbs: Optional[Path],
    pending_upload_rbs: Optional[pd.DataFrame],
    *,
    base_name: Optional[str] = None,
) -> tuple[bool, str]:
    """Persist uploaded historical RBS data to tmp/consignments.

    This function does not generate new data; it simply saves the uploaded
    or existing RBS file under a unique filename.

    Args:
        current_rbs: Existing RBS CSV path, if any.
        pending_upload_rbs: RBS DataFrame uploaded via the UI.
        base_name: Base filename to use when writing to tmp/consignments.

    Returns:
        Tuple ``(ok, message)`` indicating success and a status message.
    """
    base_name = base_name or st.session_state.get("consignment_base_name", "Historical") or "Historical"
    paths_map = _consignment_paths(base_name)
    dest_rbs = _unique_path(paths_map["uploaded_rbs"])
    dest_rbs.parent.mkdir(parents=True, exist_ok=True)

    try:
        if pending_upload_rbs is not None and not pending_upload_rbs.empty:
            pending_upload_rbs.to_csv(dest_rbs, index=False)
            state = get_slippage_state()
            state["rbs_preview"] = pending_upload_rbs.head(10)
            state["pending_rbs_upload"] = None
            set_paths(rbs_data=dest_rbs)
            return True, f"Saved uploaded RBS file with base '{base_name}' to tmp/consignments."

        if current_rbs is not None and Path(current_rbs).exists():
            if Path(current_rbs).resolve() != dest_rbs.resolve():
                shutil.copy(current_rbs, dest_rbs)
            state = get_slippage_state()
            state["rbs_preview"] = pd.read_csv(dest_rbs).head(10)
            set_paths(rbs_data=dest_rbs)
            return True, f"Saved RBS file with base '{base_name}' to tmp/consignments."

        return False, "No RBS source file found."
    except Exception as exc:  # pylint: disable=broad-except
        return False, f"Unable to save consignment files: {exc}"


def _save_manual_rbs(
    pending_manual_rbs: Optional[pd.DataFrame],
    *,
    base_name: Optional[str] = None,
) -> tuple[bool, str]:
    """Save a manually constructed RBS DataFrame to tmp/consignments.

    Args:
        pending_manual_rbs: Combined manual RBS dataset to save.
        base_name: Base filename used for the saved CSV.

    Returns:
        Tuple ``(ok, message)`` indicating success and a status message.
    """
    if pending_manual_rbs is None or pending_manual_rbs.empty:
        return False, "No manual RBS data to save."
    try:
        paths_map = _consignment_paths(base_name)
        dest_rbs = _unique_path(paths_map["manual_rbs"])
        dest_rbs.parent.mkdir(parents=True, exist_ok=True)
        pending_manual_rbs.to_csv(dest_rbs, index=False)
        state = get_slippage_state()
        state["rbs_preview"] = pending_manual_rbs.head(10)
        set_paths(rbs_data=dest_rbs)
        return True, f"Saved manual RBS file with base '{base_name or st.session_state.get('consignment_base_name', 'consignment')}' to tmp/consignments."
    except Exception as exc:  # pylint: disable=broad-except
        return False, f"Unable to save manual RBS file: {exc}"


def _build_rbs_dataset(seed_df: pd.DataFrame) -> pd.DataFrame:
    """Convert an internal seed DataFrame into an RBS-like dataset.

    Args:
        seed_df: Seed DataFrame with specific columns (e.g., producer,
            pathway, etc.) created by
            :func:`_build_manual_consignment_seed`.

    Returns:
        A new DataFrame with RBS calculator-compatible columns.
    """
    rows = []
    for _, row in seed_df.iterrows():
        rows.append(
            {
                "INSPECTION_ID": row["INSPECTION_ID"],
                "INSPECTION_NUMBER": row["INSPECTION_NUMBER"],
                "INSPECTION_LOCATION_NAME": row["INSPECTION_LOCATION_NAME"],
                "COUNTRY_OF_ORIGIN_NAME": row["COUNTRY_OF_ORIGIN_NAME"],
                "PATHWAY": row["PATHWAY"],
                "PROPAGATIVE_MATERIAL_TYPE": row["PROPAGATIVE_MATERIAL_TYPE"],
                "PRODUCER_NAME": row["PRODUCER"],
                "TOTAL_SAMPLING_UNITS": row["TOTAL_SAMPLING_UNITS"],
                "TOTAL_PLANT_QUANTITY": row["TOTAL_PLANT_QUANTITY"],
                "CONFIDENCE_LEVEL": row["CONFIDENCE_LEVEL"],
                "DETECTION_LEVEL": row["DETECTION_LEVEL"],
                "REQUIRED_NUMBER_OF_BOXES": row["REQUIRED_NUMBER_OF_BOXES"],
            }
        )
    return pd.DataFrame(rows)


def _init_page_state(state: dict) -> None:
    """Initialize per-page state keys with defaults.

    Args:
        state: Mutable dictionary derived from Streamlit session state.
    """
    state.setdefault("consignment_source", "synthetic")
    state.setdefault("consignment_base_name", "consignment")
    state.setdefault("pending_rbs_upload", None)
    state.setdefault("use_custom_producer_grouping", True)
    state.setdefault("manual_consignments", [])
    state.setdefault("manual_units", [])


def _load_reference_config() -> tuple[list[str], list[str], list[str]]:
    """Load reference origins, ports, and materials from config.yml.

    Returns:
        Tuple of three lists:
            * origins,
            * ports,
            * flowers/material types.
    """
    config = yaml.safe_load(Path("config.yml").read_text())
    parameter_based = config.get("consignment", {}).get("parameter_based", {})
    return (
        parameter_based.get("origins", []),
        parameter_based.get("ports", []),
        parameter_based.get("flowers", []),
    )


def _render_consignment_summary(df: pd.DataFrame, *, include_info_message: bool = False) -> None:
    """Render summary metrics for a consignment DataFrame.

    Shows counts of consignments, pathways, locations, countries, and
    total plant and sampling units.

    Args:
        df: Consignment DataFrame with RBS-like columns.
        include_info_message: If True, shows an info message about where
            to view richer plots.
    """
    if df is None or df.empty:
        return

    summary_specs = [
        ("INSPECTION_NUMBER", "Consignments", "Number of unique consignments in the dataset."),
        ("PATHWAY", "Pathways", "Number of unique shipment pathways represented in the dataset."),
        ("INSPECTION_LOCATION_NAME", "Locations", "Number of unique inspection locations represented in the dataset."),
        ("COUNTRY_OF_ORIGIN_NAME", "Countries", "Number of unique countries of origin represented in the dataset."),
    ]
    metric_cols = st.columns(4)
    for idx, (column, label, help_text) in enumerate(summary_specs):
        if column in df.columns:
            with metric_cols[idx]:
                render_metric_card(label, f"{df[column].nunique():,}", help_text)

    totals_specs = [
        ("TOTAL_PLANT_QUANTITY", "Total plant units", "Total plant units across all rows in the dataset."),
        ("TOTAL_SAMPLING_UNITS", "Total sampling units", "Total sampling units across all rows in the dataset."),
    ]
    totals_cols = st.columns(2)
    for idx, (column, label, help_text) in enumerate(totals_specs):
        if column in df.columns:
            with totals_cols[idx]:
                render_metric_card(label, f"{int(df[column].sum()):,}", help_text)

    if include_info_message:
        st.info("Save or generate to view rich plots in the Saved consignments tab.")


def _render_quantity_sampling_heatmap(df: pd.DataFrame) -> None:
    """Render a heatmap of quantity vs sampling units for inspection units.

    Uses Altair to show a 2D histogram of plant units versus sample units.

    Args:
        df: DataFrame containing either ``QUANTITY`` and
            ``SAMPLING_UNITS_FOR_INSPECTION_UNIT`` or
            ``TOTAL_PLANT_QUANTITY`` and ``TOTAL_SAMPLING_UNITS``.
    """
    quantity_col = None
    sampling_units_col = None
    if "QUANTITY" in df.columns and "SAMPLING_UNITS_FOR_INSPECTION_UNIT" in df.columns:
        quantity_col = "QUANTITY"
        sampling_units_col = "SAMPLING_UNITS_FOR_INSPECTION_UNIT"
    elif "TOTAL_PLANT_QUANTITY" in df.columns and "TOTAL_SAMPLING_UNITS" in df.columns:
        quantity_col = "TOTAL_PLANT_QUANTITY"
        sampling_units_col = "TOTAL_SAMPLING_UNITS"

    if not quantity_col or not sampling_units_col:
        st.info("Need both quantity and sampling units for inspection unit to render the heat map.")
        return

    heatmap_source = df[[quantity_col, sampling_units_col]].dropna()
    quantities = heatmap_source[quantity_col].to_numpy()
    sampling_units = heatmap_source[sampling_units_col].to_numpy()
    if quantities.size == 0 or sampling_units.size != quantities.size:
        st.info("Need both quantity and sampling units for inspection unit to render the heat map.")
        return

    q_min, q_max = float(quantities.min()), float(quantities.max())
    s_min, s_max = float(sampling_units.min()), float(sampling_units.max())
    q_bins = np.linspace(q_min, q_max, num=21) if q_min != q_max else np.array([q_min, q_max + 1])
    s_bins = np.linspace(s_min, s_max, num=11) if s_min != s_max else np.array([s_min, s_max + 1])
    heat, q_edges, s_edges = np.histogram2d(quantities, sampling_units, bins=[q_bins, s_bins])
    heat_df = pd.DataFrame(
        {
            "plant_bin_start": np.repeat(q_edges[:-1], len(s_edges) - 1),
            "plant_bin_end": np.repeat(q_edges[1:], len(s_edges) - 1),
            "sample_bin_start": np.tile(s_edges[:-1], len(q_edges) - 1),
            "sample_bin_end": np.tile(s_edges[1:], len(q_edges) - 1),
            "frequency": heat.flatten(),
        }
    )
    chart = (
        alt.Chart(heat_df)
        .mark_rect()
        .encode(
            x=alt.X(
                "plant_bin_start:Q",
                bin=alt.Bin(binned=True, step=float(q_bins[1] - q_bins[0])),
                title="Plant units",
            ),
            x2="plant_bin_end:Q",
            y=alt.Y(
                "sample_bin_start:Q",
                bin=alt.Bin(binned=True, step=float(s_bins[1] - s_bins[0])),
                title="Sample units",
            ),
            y2="sample_bin_end:Q",
            color=alt.Color(
                "frequency:Q",
                title="Number of inspection units",
                scale=alt.Scale(
                    domain=[0, 1, float(heat_df["frequency"].max()) if not heat_df.empty else 1.0],
                    range=["#d9d9d9", "#deebf7", "#08519c"],
                ),
            ),
        )
    )
    st.altair_chart(chart, use_container_width=True)


def _render_saved_consignment_preview(df: pd.DataFrame) -> None:
    """Render a rich preview for a saved consignment DataFrame.

    Displays:

    * DataFrame preview.
    * Summary statistics.
    * Distribution plots for top origins, locations, and material types.
    * Quantity vs sampling-unit heatmap.

    Args:
        df: Consignment DataFrame loaded from a saved CSV.
    """
    render_labeled_help(
        "Saved consignment preview",
        "Shows the rows stored in the selected saved consignment file from tmp/consignments.",
    )
    st.dataframe(df, use_container_width=True, height=500)
    render_labeled_help(
        "Summary statistics",
        "Summarizes unique consignments, pathways, locations, countries, and the total plant and sampling units in the selected file.",
    )
    _render_consignment_summary(df)

    render_labeled_help(
        "Distributions",
        "Shows the most common origins, inspection locations, and material types, plus the relationship between plant units and sample units.",
    )
    plots_two_col = st.columns(2)
    with plots_two_col[0]:
        plot_subcols = st.columns(3)
        if "COUNTRY_OF_ORIGIN_NAME" in df.columns:
            plot_subcols[0].markdown("**Top origins**")
            plot_subcols[0].bar_chart(df["COUNTRY_OF_ORIGIN_NAME"].value_counts().head(10).rename("Count"))
        if "INSPECTION_LOCATION_NAME" in df.columns:
            plot_subcols[1].markdown("**Top inspection locations**")
            plot_subcols[1].bar_chart(df["INSPECTION_LOCATION_NAME"].value_counts().head(10).rename("Count"))
        if "PROPAGATIVE_MATERIAL_TYPE" in df.columns:
            plot_subcols[2].markdown("**Top material types**")
            plot_subcols[2].bar_chart(df["PROPAGATIVE_MATERIAL_TYPE"].value_counts().head(10).rename("Count"))
    with plots_two_col[1]:
        st.markdown("**Plant units vs sample units**")
        _render_quantity_sampling_heatmap(df)


def _build_manual_consignment_seed(
    manual_units: list[dict],
    consignment_uid: str,
    *,
    detection_level: float,
    confidence_level: float,
) -> pd.DataFrame:
    """Construct an internal seed DataFrame from manual inspection units.

    Args:
        manual_units: List of dictionaries describing manual inspection
            units (port, origin, material, pathway, sample_units,
            plants_per_sample, producer).
        consignment_uid: Unique identifier for the combined consignment.
        detection_level: Detection level used to approximate required boxes.
        confidence_level: Confidence level used to approximate required boxes.

    Returns:
        Seed DataFrame with columns suitable for conversion to an RBS
        dataset via :func:`_build_rbs_dataset`.
    """
    rows = []
    for unit in manual_units:
        total_sampling_units = int(unit["sample_units"])
        total_plants = total_sampling_units * int(unit["plants_per_sample"])
        required_boxes = max(1, int(total_sampling_units * detection_level * confidence_level))
        rows.append(
            {
                "INSPECTION_NUMBER": consignment_uid,
                "INSPECTION_ID": consignment_uid,
                "INSPECTION_LOCATION_NAME": unit["port"],
                "PATHWAY": unit["pathway"],
                "COUNTRY_OF_ORIGIN_NAME": unit["origin"],
                "PROPAGATIVE_MATERIAL_TYPE": unit["material"],
                "TOTAL_SAMPLING_UNITS": total_sampling_units,
                "TOTAL_PLANT_QUANTITY": total_plants,
                "TOTAL_PLANTS_CONTAMINATED": int(round(total_plants * 0.02)),
                "PRODUCER": unit["producer"],
                "CREATED_DATETIME": "00:00.0",
                "IS_RBS": 1,
                "RBS_STATUS": "RBS",
                "SIMULATED_CONTAMINATION_RATE": 0.02,
                "DETECTION_LEVEL": detection_level,
                "CONFIDENCE_LEVEL": confidence_level,
                "REQUIRED_NUMBER_OF_BOXES": int(required_boxes),
                "action": 0,
            }
        )
    return pd.DataFrame(rows)


# --- Page setup and main UI logic below this line (no function docstrings needed) ---
st.set_page_config(page_title="Consignment Generation", layout="wide")
init_state()

state = get_slippage_state()
render_sidebar_navigation()
apply_shared_page_styles()
paths = state["paths"]
_init_page_state(state)
default_producer_grouping = Path("gui/data_input/producer_grouping.csv")
if "producer_grouping_path" not in state:
    state["producer_grouping_path"] = default_producer_grouping if default_producer_grouping.exists() else None
# Normalize current RBS references for later save buttons
_state_rbs = state.get("rbs_data")
current_rbs = None
if isinstance(_state_rbs, (str, Path)):
    current_rbs = Path(_state_rbs)
elif isinstance(state["paths"].rbs_data, (str, Path)):
    current_rbs = Path(state["paths"].rbs_data)

pending_manual_rbs = state.get("pending_manual_rbs") if isinstance(state.get("pending_manual_rbs"), pd.DataFrame) else None
config_origins, config_ports, config_materials = _load_reference_config()

st.warning(
    "**Test Deployment Notice: This is a test deployment with limited functionality and is under active development. "
    "Features may be incomplete and subject to change. Results have not been validated.**"
)
st.title("Page 1 - Consignment Generation")
render_page_intro(
    "Ingest curated consignment data or define consignments from scratch. "
    "Use the <i>Generate consignments based on data</i> tab to upload data and create synthetic consignments. "
    "Generated outputs are written to <i>tmp/consignments</i>."
)

# saved_tab, ingest_tab, manual_tab, producer_grouping_tab = st.tabs( # UNCOMMENT FOR MANUAL CONSIGMENT GENERATION
saved_tab, ingest_tab, producer_grouping_tab = st.tabs(
    [
        "Saved Consignments",
        "Data-Driven Generation",
        # "Manual Generation", # UNCOMMENT FOR MANUAL CONSIGMENT GENERATION
        "Producer Grouping",
    ]
)

with ingest_tab:
    if "data_updated" not in st.session_state:
        st.session_state["data_updated"] = False

    pis_df: Optional[pd.DataFrame] = state.get("pis_data")
    rbs_df: Optional[pd.DataFrame] = state.get("pending_rbs_upload")

    st.subheader("Generate consignments based on data")
    st.write("Upload a CSV, map any missing fields, and save or generate consignments for downstream pages.")
    render_labeled_help(
        "Upload consignment data",
        "Upload data (as .csv file) that will be saved directly or used as input for synthetic consignment generation.",
    )
    rbs_upload = st.file_uploader(
        "RBS calculator CSV",
        type=["csv"],
        key="rbs_upload_ingest",
        label_visibility="collapsed",
    )
    if rbs_upload is not None:
        rbs_df = pd.read_csv(rbs_upload)

        # Reset flag on new upload
        st.session_state["data_updated"] = False

        # Perform column check
        required_cols = set(GENERATOR_TARGET_COLUMNS)
        missing_cols = [col for col in required_cols if col not in rbs_df.columns]

        if missing_cols and not st.session_state["data_updated"]:
            st.error(
                f"The following required columns are missing from your file: {', '.join(missing_cols)}"
            )

            # Initialize mapping dictionary for session persistence
            if "col_mapping" not in st.session_state:
                st.session_state["col_mapping"] = {}

            # Collect user mapping for each missing column
            for missing in missing_cols:
                render_labeled_help(
                    f"Map required field: {missing}",
                    "Choose the uploaded column that should be used for this required field before updating the file.",
                    compact=True,
                )
                st.session_state["col_mapping"][missing] = st.selectbox(
                    f"Please choose a column from your uploaded data for required field '{missing}':",
                    options=[""] + list(rbs_df.columns),
                    key=f"map_{missing}",
                    label_visibility="collapsed",
                )

            # Check if all mappings are filled
            mappings_ready = all(st.session_state["col_mapping"][miss] for miss in missing_cols)

            if not mappings_ready:
                st.warning("You must select a column for each missing required field OR add the column to your data and reupload.")

            render_labeled_help(
                "Update Data Fields/Columns",
                "Apply the selected field mappings and load the cleaned data into the current session.",
                compact=True,
            )
            update_clicked = st.button("Update Data Fields/Columns")

            if update_clicked and mappings_ready:
                # Rename columns according to the mapping
                for missing, found in st.session_state["col_mapping"].items():
                    rbs_df.rename(columns={found: missing}, inplace=True)
                state["pending_rbs_upload"] = rbs_df

                # mark error as resolved
                st.session_state["data_updated"] = True

                st.success(f"Columns updated and data ready to save or use. "
                           f"Loaded {len(rbs_df):,} RBS records. Save below to persist to tmp/consignments.")
            elif update_clicked and not mappings_ready:
                st.error("Please provide a mapping for all missing columns before updating.")

        else:
            state["pending_rbs_upload"] = rbs_df
            st.success(f"Loaded {len(rbs_df):,} RBS records. Save below to persist to tmp/consignments.")

    if rbs_df is not None and not rbs_df.empty:
        st.dataframe(rbs_df.head(25), use_container_width=True, height=300)
        _render_consignment_summary(rbs_df, include_info_message=True)
    else:
        st.info("Upload .csv data file here.")

    render_labeled_help(
        "Consignment source for downstream analysis",
        "Choose whether downstream pages should use synthetic consignments generated from uploaded data or use historical consignment data directly.",
    )
    source_choice = st.radio(
        "Consignment source for downstream analysis",
        [
            "Generate synthetic consignments from data",
            "Use historical consignments",
        ],
        index=0 if state["consignment_source"] == "synthetic" else 1,
        label_visibility="collapsed",
    )
    state["consignment_source"] = "synthetic" if source_choice.startswith("Generate") else "historical"

    # Base name input before actions, with defaults per mode
    default_base = "Generated" if state["consignment_source"] == "synthetic" else "Historical"
    # If the stored value is one of the old defaults, realign it to the current mode before rendering the widget
    if st.session_state.get("consignment_base_name") in ("Generated", "Historical", "Generated_Historical"):
        st.session_state["consignment_base_name"] = default_base
    current_base = st.session_state.get("consignment_base_name", default_base) or default_base
    render_labeled_help(
        "Consignment input file base name",
        "Base name used when saving consignment CSV files into tmp/consignments for downstream pages.",
    )
    st.text_input(
        "Consignment input file base name",
        value=current_base,
        key="consignment_base_name",
        help="Used to name RBS files in tmp/consignments (e.g., <name>.csv).",
        label_visibility="collapsed",
    )
    state["consignment_base_name"] = st.session_state.get("consignment_base_name", current_base) or default_base

    if state["consignment_source"] == "synthetic":
        render_labeled_help(
            "Synthetic consignment generation",
            "Generate new synthetic consignments from the uploaded consignment dataset and save them for downstream analysis.",
        )
        gen_cols = st.columns(2)
        gen_cols[0].markdown("Number of consignments to generate")
        n_samples = gen_cols[0].number_input(
            "Number of consignments to generate",
            min_value=1,
            max_value=10000,
            value=20,
            step=10,
            label_visibility="collapsed",
        )
        method_dict = {
            "multinomial sequential": "sequential",
            "gaussian mixture": "gmm",
        }
        gen_cols[1].markdown("Sampling method")
        method_selection = gen_cols[1].selectbox(
            "Sampling method",
            options=list(method_dict),
            index=0,
            label_visibility="collapsed",
        )
        method = method_dict[method_selection]
        state["use_custom_producer_grouping"] = st.checkbox(
            "Use producer grouping CSV during synthetic generation",
            value=bool(state.get("use_custom_producer_grouping", True)),
            key="use_custom_producer_grouping",
            help="When enabled, synthetic generation will load producer grouping from the selected CSV on the Producer grouping tab.",
        )
        has_tmp_saved_consignments = any(CONSIGNMENT_ROOT.glob("*.csv"))
        has_synthetic_seed = (
            (state.get("pending_rbs_upload") is not None and not state.get("pending_rbs_upload").empty)
            or has_tmp_saved_consignments
        )
        render_labeled_help(
            "Generate synthetic consignments",
            "Create synthetic consignments from the uploaded data and save them to tmp/consignments.",
            compact=True,
        )
        if st.button(
            "Generate synthetic consignments",
            type="primary",
            disabled=not has_synthetic_seed,
        ):
            set_synthetic_options(SyntheticOptions(n_samples=int(n_samples), sampling_method=method))
            set_paths(synthetic_seed=_consignment_paths()["uploaded_rbs"])
            producer_grouping_path = None
            if state.get("use_custom_producer_grouping"):
                producer_grouping_path = state.get("producer_grouping_path")

            # Use st.status to show step-by-step updates
            with st.status("Generating synthetic consignments...", expanded=True) as status:
                try:
                    ok, msg = _save_rbs_to_tmp(
                        current_rbs,
                        pending_manual_rbs,
                        state.get("pending_rbs_upload"),
                        producer_grouping_path=producer_grouping_path,
                        status=status,
                    )
                    if ok:
                        status.update(label="Generation complete", state="complete")
                        if state["paths"].rbs_data:
                            current_rbs = Path(state["paths"].rbs_data)
                        st.success(f"Generated and saved synthetic consignments: {msg}")
                    else:
                        status.update(label="Generation failed", state="error")
                        st.warning(msg)
                except Exception as e:
                    status.update(label="Generation failed", state="error")
                    st.error(f"Error during generation: {e}")
            # ok, msg = _save_rbs_to_tmp(
            #     current_rbs,
            #     pending_manual_rbs,
            #     state.get("pending_rbs_upload"),
            #     producer_grouping_path=producer_grouping_path,
            # )
            # if ok:
            #     if state["paths"].rbs_data:
            #         current_rbs = Path(state["paths"].rbs_data)
            #     st.success(f"Generated and saved synthetic consignments: {msg}")
            # else:
            #     st.warning(msg)
    else:
        if state["consignment_source"] == "historical" and (
            (pis_df is None or pis_df.empty) or (rbs_df is None or rbs_df.empty)
        ):
            st.warning("Upload both PIS action and RBS data on **Page 2 - Contamination Fit** to rely on historical consignments.")
        can_save_uploaded_consignments = (
            (state.get("pending_rbs_upload") is not None and not state.get("pending_rbs_upload").empty)
            or any(CONSIGNMENT_ROOT.glob("*.csv"))
        )
        render_labeled_help(
            "Save uploaded consignments",
            "Persist the uploaded historical consignments into tmp/consignments without generating new data.",
            compact=True,
        )
        if st.button(
            "Save uploaded consignments",
            type="primary",
            key="save_consignment_ingest",
            disabled=not can_save_uploaded_consignments,
        ):
            ok, msg = _save_historical_rbs(current_rbs, state.get("pending_rbs_upload"), base_name=current_base)
            if ok:
                if state["paths"].rbs_data:
                    current_rbs = Path(state["paths"].rbs_data)
                st.success(msg)
            else:
                st.warning(msg)

################################################################################
# Manual Consignment Generation Tab - begin
# UNCOMMENT BELOW FOR MANUAL CONSIGMENT GENERATION
################################################################################

# with manual_tab:
#     st.subheader("Define consignments one by one")
#     st.write("Build inspection units manually, combine them into consignments, and export the resulting RBS file.")
#     render_labeled_help(
#         "Manual Generation",
#         "Create consignments manually by adding inspection units one at a time, then combine them into a saved RBS consignment dataset.",
#     )
#     st.info(
#         "Add inspection units first (one port, one origin, one material per unit), then bundle them into a consignment."
#     )
#     render_labeled_help(
#         "Consignment name/ID",
#         "Unique identifier used to group the inspection units below into a single consignment record.",
#     )
#     consignment_name = st.text_input(
#         "Consignment name/ID (unique per consignment)",
#         value=f"CONS-{len(state['manual_consignments'])+1:03d}",
#         label_visibility="collapsed",
#     )

#     with st.form("inspection_unit_form"):
#         c1, c2 = st.columns(2)
#         with c1:
#             render_labeled_help("Plant Inspection Station (PIS)", "PIS assigned to this inspection unit.")
#             port = st.selectbox(
#                 "Port of entry", # PIS != POE - should we change
#                 options=config_ports or ["Miami PIS"],
#                 index=0,
#                 label_visibility="collapsed",
#             )
#         with c2:
#             render_labeled_help("Country of origin", "Country of origin assigned to this inspection unit.")
#             origin = st.selectbox(
#                 "Country of origin",
#                 options=config_origins or ["Japan"],
#                 index=0,
#                 label_visibility="collapsed",
#             )
#         render_labeled_help("Propagative material type", "Propagative material type assigned to this inspection unit.")
#         material = st.selectbox(
#             "Propagative material type",
#             options=["Budwood/Graftwood (scion)",
#                      "Unrooted Cutting, Bulb, Corm, Rhizome, Tuberous Stem, Tuberous Stem",
#                      "Meristem or Callus Tissue Culture (micropropagated/in vitro culture)",
#                      "Root cutting, crown, or clump, Tuberous Root",
#                      "Rooted Cutting (including air layer)",
#                      "Rooted Plant (including grafted)",
#                      "Unrooted Plant"],
#             index=0,
#             label_visibility="collapsed",
#         )
#         render_labeled_help("Pathway", "Transport pathway used for this inspection unit.")
#         pathway = st.selectbox(
#             "Pathway",
#             ["Airport - Aircraft - Cargo - PIS",
#              "Maritime Port - Vessel - Cargo - PIS",
#              "Airport - Aircraft - Express Carrier - PIS",
#              "Airport - Aircraft - Mail - PIS Mail",
#              "Land Border - Truck - Cargo - PIS"
#              ], # These aren't what we are used to...intentional?
#             index=1,
#             label_visibility="collapsed",
#         )
#         c1, c2 = st.columns(2)
#         with c1:
#             render_labeled_help("Sample units (per inspection unit)", "Number of sampling units contained in this inspection unit.")
#             sample_units = st.number_input(
#                 "Sample units (per inspection unit)",
#                 min_value=1,
#                 max_value=5000,
#                 value=200,
#                 step=10,
#                 label_visibility="collapsed",
#             )
#         with c2:
#             render_labeled_help("Plants per sample unit", "Number of plants represented by each sample unit in this inspection unit.")
#             plants_per_sample = st.number_input(
#                 "Plants per sample unit",
#                 min_value=1,
#                 max_value=1000,
#                 value=5,
#                 step=1,
#                 label_visibility="collapsed",
#             )
#         render_labeled_help("Producer name", "Producer name assigned to this inspection unit.")
#         producer = st.text_input(
#             "Producer name",
#             value="User Defined Producer",
#             label_visibility="collapsed",
#         )
#         render_labeled_help(
#             "Add inspection unit",
#             "Add the inspection unit above to the current consignment draft.",
#             compact=True,
#         )
#         add_unit = st.form_submit_button(
#             "Add inspection unit",
#             type="secondary",
#             use_container_width=True,
#         )

#     if add_unit:
#         state["manual_units"].append(
#             {
#                 "port": port.strip(),
#                 "origin": origin.strip(),
#                 "material": material.strip(),
#                 "pathway": pathway,
#                 "sample_units": int(sample_units),
#                 "plants_per_sample": int(plants_per_sample),
#                 "producer": producer.strip() or "User Defined Producer",
#             }
#         )
#         st.success(f"Added inspection unit: {port} / {origin} / {material}")

#     if state["manual_units"]:
#         st.subheader(f"Inspection units in {consignment_name or 'current consignment'}")
#         st.dataframe(pd.DataFrame(state["manual_units"]), use_container_width=True)

#     st.markdown("---")
#     detection_level = 0.01
#     confidence_level = 0.8
#     render_labeled_help(
#         "Build consignment from inspection units above",
#         "Combine the current inspection units into one consignment. Required inspection units are auto-computed from the fixed detection and confidence settings.",
#     )
#     if st.button(
#         "Build consignment from inspection units above",
#         type="secondary",
#         use_container_width=True,
#         disabled=not state["manual_units"],
#     ):
#         consignment_uid = consignment_name or f"CONS-{len(state['manual_consignments'])+1:03d}"
#         seed_df = _build_manual_consignment_seed(
#             state["manual_units"],
#             consignment_uid,
#             detection_level=detection_level,
#             confidence_level=confidence_level,
#         )
#         rbs_df = _build_rbs_dataset(seed_df)

#         state["manual_consignments"].append(
#             {
#                 "name": consignment_uid,
#                 "seed": seed_df,
#                 "rbs": rbs_df,
#             }
#         )
#         state["manual_units"] = []

#         combined_rbs = pd.concat([c["rbs"] for c in state["manual_consignments"]], ignore_index=True)

#         state["manual_rbs_preview"] = combined_rbs.head(200)
#         state["pending_manual_rbs"] = combined_rbs
#         st.success(
#             f"Saved consignment '{consignment_uid}' with {len(seed_df)} inspection units. "
#             "Use the generation button below to write the RBS file to tmp."
#         )

#     if state.get("manual_consignments"):
#         st.subheader("Current consignments")
#         render_labeled_help(
#             "Current consignments",
#             "Review the consignments you have assembled in this session before previewing or saving the combined RBS dataset.",
#         )
#         summary_rows = [
#             {"Consignment": c["name"], "Inspection units": len(c["seed"])}
#             for c in state["manual_consignments"]
#         ]
#         st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

#     render_labeled_help(
#         "Synthetic RBS preview",
#         "Preview the combined RBS records generated from the current manual consignments and download the CSV before saving it to tmp/consignments.",
#     )
#     rbs_preview = state.get("manual_rbs_preview")
#     with st.expander("Synthetic RBS preview", expanded=False):
#         if rbs_preview is not None:
#             st.dataframe(rbs_preview, use_container_width=True)
#             render_labeled_help(
#                 "Download RBS dataset",
#                 "Download the currently assembled manual RBS dataset as a CSV before saving it to tmp/consignments.",
#                 compact=True,
#             )
#             st.download_button(
#                 "Download RBS dataset",
#                 data=rbs_preview.to_csv(index=False).encode("utf-8"),
#                 file_name="user_defined_rbs_data.csv",
#                 type="primary",
#                 use_container_width=True,
#             )
#         else:
#             st.info("Create a seed dataset to preview and download the generated RBS file.")

#     render_labeled_help(
#         "Consignment input file base name",
#         "Base name used when saving the manual consignment RBS CSV into tmp/consignments for downstream pages.",
#     )
#     manual_base = st.text_input(
#         "Consignment input file base name (manual)",
#         value=st.session_state.get("consignment_base_name_manual", "Manual"),
#         key="consignment_base_name_manual",
#         label_visibility="collapsed",
#     ) or "Manual"
#     render_labeled_help(
#         "Save manual consignments",
#         "Write the current manual consignment RBS dataset to tmp/consignments so it can be used by downstream pages.",
#     )
#     if st.button(
#         "Save manual consignments",
#         type="primary",
#         key="save_consignment_manual",
#     ):
#         ok, msg = _save_manual_rbs(pending_manual_rbs, base_name=manual_base)
#         if ok:
#             st.success(msg)
#         else:
#             st.warning(msg)
################################################################################
# Manual Consignment Generation Tab - end
# UNCOMMENT ABOVE FOR MANUAL CONSIGMENT GENERATION
################################################################################

# Saved consignments tab
with saved_tab:
    st.subheader("Saved consignments")
    st.write("Review saved RBS CSVs in tmp/consignments and preview their contents.")
    saved_files = sorted(CONSIGNMENT_ROOT.glob("*.csv"))
    if not saved_files:
        st.info("No consignment files saved yet in tmp/consignments.")
    else:
        render_labeled_help(
            "Select a saved consignment file",
            "Choose a saved RBS consignment CSV from tmp/consignments to preview its rows, summary metrics, and distributions.",
        )
        sel = st.selectbox(
            "Select a saved consignment file",
            saved_files,
            format_func=lambda p: p.name,
            label_visibility="collapsed",
        )
        try:
            full_df = pd.read_csv(sel)
            _render_saved_consignment_preview(full_df)
            st.caption(f"Location: {sel}")
            if st.button("Delete this consignment file", type="secondary"):
                try:
                    sel.unlink()
                    st.success(f"Deleted {sel.name}")
                    st.rerun()
                except Exception as exc:  # pylint: disable=broad-except
                    st.error(f"Unable to delete consignment file: {exc}")
        except Exception as exc:  # pylint: disable=broad-except
            st.error(f"Unable to preview file: {exc}")

with producer_grouping_tab:
    st.subheader("Producer grouping")
    st.write("Optionally provide producer grouping data to guide synthetic consignment generation.")

    render_labeled_help(
        "Upload custom producer grouping CSV",
        "Optional producer grouping used during synthetic consignment generation on Page 1. Expected columns include PRODUCER_NAME and a grouping column.",
    )
    producer_grouping_upload = st.file_uploader(
        "Upload custom producer grouping CSV",
        type=["csv"],
        key="producer_grouping_upload",
        label_visibility="collapsed",
    )
    if producer_grouping_upload is not None:
        producer_grouping_path = TMP_DIR / "producer_grouping.csv"
        producer_grouping_df = pd.read_csv(producer_grouping_upload)
        producer_grouping_df.to_csv(producer_grouping_path, index=False)
        state["producer_grouping_path"] = producer_grouping_path
        st.success(f"Saved custom producer grouping to {producer_grouping_path}")

    if state.get("producer_grouping_path"):
        current_grouping_path = Path(state["producer_grouping_path"])
        st.caption(f"Current producer grouping: {current_grouping_path}")
        try:
            producer_grouping_df = pd.read_csv(current_grouping_path)
            st.dataframe(producer_grouping_df.head(50), use_container_width=True, height=320)
            st.metric(
                "Rows",
                f"{len(producer_grouping_df):,}",
                help="Number of rows available in the current producer grouping file used during synthetic generation.",
            )
        except Exception as exc:  # pylint: disable=broad-except
            st.warning(f"Unable to preview producer grouping file: {exc}")

pending_manual_rbs = state.get("pending_manual_rbs")

st.divider()
nav_cols = st.columns(3)
with nav_cols[0]:
    if st.button(
        "Reset and Return Home",
        type="secondary",
        key="nav_reset_tmp",
        help="Delete temporary files and restart from the home page",
    ):
        try:
            # Import the helper for safe temporary directory reset
            from .tmp_utils import reset_tmp_directory
            reset_tmp_directory(TMP_DIR)
            # Initialize a fresh copy of config.yml into tmp for downstream use
            src_cfg = Path("gui/data_input/config.yml")
            if src_cfg.exists():
                dst_cfg = TMP_DIR / "config.yml"
                shutil.copy(src_cfg, dst_cfg)
            st.session_state.clear()
            st.success("Temporary files cleared. Returning to Home...")
            st.switch_page("frontend.py")
        except Exception as exc:  # pylint: disable=broad-except
            st.error(f"Unable to reset temporary files: {exc}")
with nav_cols[1]:
    if st.button("Previous Page", type="primary", key="nav_home_page2"):
        st.switch_page("frontend.py")
with nav_cols[2]:
    if st.button(
        "Next Page",
        type="primary",
        key="nav_forward_page2",
        disabled=False,
    ):
        if current_rbs:
            set_paths(
                rbs_data=current_rbs,
            )
        st.switch_page("pages/2_Contamination_Fit.py")
