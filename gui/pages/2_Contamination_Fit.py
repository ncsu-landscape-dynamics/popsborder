# © 2026 The Johns Hopkins University Applied Physics Laboratory LLC

from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

import altair as alt
import numpy as np
from gui.runtime_warnings import suppress_optional_dependency_warnings

suppress_optional_dependency_warnings()

import pandas as pd
import streamlit as st
from typing import Any, Dict, Tuple, Iterable, Optional
from scipy.stats import betabinom

from gui.models import init_state
from gui.navigation import render_sidebar_navigation
from gui.page_styles import (
    apply_shared_page_styles,
    render_labeled_help,
    render_metric_card,
    render_page_intro,
)
from gui.slippage_pipeline import ClarkeFit, create_default_paths, fit_contamination_distribution
from gui.slippage_ui import get_slippage_state, set_paths
from popsborder.inputs import load_configuration

TMP_DIR = Path("tmp")
CONTAM_DIR = TMP_DIR / "contamination"
PARAM_STORE = CONTAM_DIR / "contamination_parameter_sets.json"
FALLBACK_ALPHA = 0.194628
FALLBACK_BETA = 4.7609372
FALLBACK_THETA = float("inf")
FALLBACK_P = 0.0

TMP_DIR.mkdir(parents=True, exist_ok=True)
CONTAM_DIR.mkdir(parents=True, exist_ok=True)


def _load_preview(path: Optional[Path], rows: int = 50) -> Optional[pd.DataFrame]:
    """Load a CSV preview (head) from ``path``, or None on failure.

    Args:
        path: Path to the CSV file or None.
        rows: Number of rows to read for preview.

    Returns:
        DataFrame with up to ``rows`` rows, or None if the path is None
        or the file cannot be read.
    """
    if path is None:
        return None
    try:
        return pd.read_csv(path).head(rows)
    except Exception:  # pylint: disable=broad-except
        return None


def _beta_pdf(alpha: float, beta: float, num_points: int = 200) -> pd.DataFrame:
    """Compute a normalized Beta PDF for visualization.

    Args:
        alpha: Alpha parameter of the Beta distribution.
        beta: Beta parameter of the Beta distribution.
        num_points: Number of points at which to evaluate the PDF.

    Returns:
        DataFrame with columns ``"prevalence"`` (x-axis) and ``"density"``.
    """
    eps = 1e-6
    xs = np.linspace(eps, 1 - eps, num_points)
    log_norm = math.lgamma(alpha + beta) - math.lgamma(alpha) - math.lgamma(beta)
    ys = np.exp(log_norm + (alpha - 1) * np.log(xs) + (beta - 1) * np.log(1 - xs))
    area = np.trapezoid(ys, xs)
    if area > 0:
        ys = ys / area
    return pd.DataFrame({"prevalence": xs, "density": ys})


def _beta_chart(alpha: float, beta: float, title: str) -> alt.Chart:
    """Build an Altair chart for a Beta PDF.

    Args:
        alpha: Alpha parameter for the Beta distribution.
        beta: Beta parameter for the Beta distribution.
        title: Chart title.

    Returns:
        Altair Chart object visualizing the Beta PDF.
    """
    pdf = _beta_pdf(alpha, beta)
    y_max = float(pdf["density"].max() * 1.05) if not pdf.empty else 1.0
    base = alt.Chart(pdf).encode(
        x=alt.X("prevalence:Q", title="Contamination prevalence", axis=alt.Axis(format="%")),
        y=alt.Y("density:Q", title="Density", scale=alt.Scale(domain=[0, y_max])),
    )
    area = base.mark_area(opacity=0.3, color="#1f77b4")
    line = base.mark_line(color="#1f77b4", strokeWidth=2)
    return (area + line).properties(height=220, title=title)


def _read_param_store() -> dict:
    """Read the contamination parameter store JSON file.

    Returns:
        Dictionary of saved parameter sets, or an empty dict if the
        store does not exist or cannot be read.
    """
    if not PARAM_STORE.exists():
        return {}
    try:
        return json.loads(PARAM_STORE.read_text())
    except Exception:  # pylint: disable=broad-except
        return {}


def _write_param_store(store: dict):
    """Write a parameter store dictionary to disk as JSON.

    Args:
        store: Dictionary containing parameter sets keyed by name.
    """
    PARAM_STORE.parent.mkdir(parents=True, exist_ok=True)
    PARAM_STORE.write_text(json.dumps(store, indent=2))


def _next_param_name(store: dict, base: str = "contamination_param_set") -> str:
    """Generate the next available parameter-set name.

    Args:
        store: Current parameter-store dictionary.
        base: Base name prefix to use for new entries.

    Returns:
        A unique name of the form ``f"{base}_<index>"``.
    """
    idx = 1
    while f"{base}_{idx}" in store:
        idx += 1
    return f"{base}_{idx}"


def _average_contamination_rate_percent(rate: Optional[float]) -> Optional[float]:
    """Convert a mean contamination rate to a percentage.

    Args:
        rate: Mean contamination rate in [0, 1].

    Returns:
        Rate multiplied by 100, or None if conversion fails.
    """
    if rate is None:
        return None
    try:
        return float(rate) * 100.0
    except Exception:  # pylint: disable=broad-except
        return None


def _load_default_cluster_p(config_path: Optional[Path]) -> float:
    """Read the default beta-binomial clustering parameter ``p`` from config.

    Args:
        config_path: Path to the active config file.

    Returns:
        Float ``p`` value from the default beta-binomial config, or
        ``FALLBACK_P`` when unavailable.
    """
    if config_path is None or not Path(config_path).exists():
        return FALLBACK_P
    try:
        config = load_configuration(Path(config_path))
        value = (
            config.get("contamination", {})
            .get("contamination_rate", {})
            .get("beta_binomial_parameters", {})
            .get("default", {})
            .get("p", FALLBACK_P)
        )
        return float(value)
    except Exception:  # pylint: disable=broad-except
        return FALLBACK_P


def _save_param_set_fall_back(
    name: str,
    alpha: float,
    beta: float,
    theta: float,
    sample_unit_rate: Optional[float] = None,
    p: Optional[float] = None,
) -> str:
    """Save fallback contamination parameters as a named parameter set.

    Args:
        name: Proposed name for the parameter set (ignored, hard-coded name is used).
        alpha: Alpha parameter.
        beta: Beta parameter.
        theta: Theta parameter.
        sample_unit_rate: Optional sample-unit contamination rate.

    Returns:
        The name under which the fallback parameter set was saved.
    """
    store = _read_param_store()
    name = 'FALL_BACK_CONTAMINATION_PARAMETERS'
    if not name:
        name = _next_param_name(store)
    entry = {"alpha": alpha, "beta": beta, "theta": theta}
    if p is not None:
        entry["p"] = float(p)
    if sample_unit_rate is not None:
        entry["sample_unit_contamination_rate"] = sample_unit_rate
        entry["average_contamination_rate"] = _average_contamination_rate_percent(sample_unit_rate)
    store[name] = entry
    _write_param_store(store)
    st.session_state["last_saved_param_set"] = name
    return name


def _save_param_set_fit(
        name: str, 
        res: Dict[Tuple, Any], 
        inputs_by_quantity: Dict[Any,Any],
        p_override: Optional[float] = None
    ) -> str:
    """Save a fitted contamination parameter set to the store.

    Args:
        name: Name for the parameter set; if empty, an auto-generated name is used.
        res: Mapping from quantity ranges to fitted parameter dictionaries.
        inputs_by_quantity: Mapping from quantity ranges to Clarke model input objects.

    Returns:
        The name under which the parameter set was saved.
    """
    store = _read_param_store()
    if not name:
        name = _next_param_name(store)
    entry = {}
    for key in res.keys():
        key_str = str(key)
        entry[key_str] = {
            "alpha": res[key]['alpha'],
            "beta": res[key]['beta'],
            "theta": inputs_by_quantity[key].theta,
            "mu": res[key]['mu'],
            "average_contamination_rate": _average_contamination_rate_percent(res[key].get('mu')),
            "D": res[key]['D'],
            "rho": res[key]['rho'],
            "J": inputs_by_quantity[key].B,
            "p": p_override
        }
    store[name] = entry
    _write_param_store(store)
    st.session_state["last_saved_param_set"] = name
    return name


def _save_param_set_assign(
    name: str,
    alpha: float,
    beta: float,
    theta: float,
    sample_unit_rate: Optional[float] = None,
    p: Optional[float] = None,
) -> str:
    """Save manually assigned contamination parameters to the store.

    Args:
        name: Name for the new parameter set; if empty, an auto-generated name is used.
        alpha: Alpha parameter.
        beta: Beta parameter.
        theta: Theta parameter.
        sample_unit_rate: Optional sample-unit contamination prevalence.

    Returns:
        The name under which the parameter set was saved.
    """
    store = _read_param_store()
    if not name:
        name = _next_param_name(store)
    entry = {"alpha": alpha, "beta": beta, "theta": theta}
    if p is not None:
        entry["p"] = float(p)
    if sample_unit_rate is not None:
        entry["sample_unit_contamination_rate"] = sample_unit_rate
        entry["average_contamination_rate"] = _average_contamination_rate_percent(sample_unit_rate)
    store[name] = entry
    _write_param_store(store)
    st.session_state["last_saved_param_set"] = name
    return name


def calculate_beta_binomial_params(
        sample_unit_rate: float,
        concentration_input: float,
        n_trials: int = 100,
        confidence_level: float = 0.95
) -> dict:
    """Calculate beta-binomial parameters and summary statistics.

    Args:
        sample_unit_rate: Average contamination rate at the lowest unit
            level (0–1).
        concentration_input: User-specified concentration slider value
            (0–100%) controlling overdispersion.
        n_trials: Number of trials for the beta-binomial (e.g., plants per sample).
        confidence_level: Two-sided confidence level for interval estimates.

    Returns:
        Dictionary containing keys:

        * ``alpha``, ``beta``, ``concentration``, ``variance``, ``rho``,
          ``mean_clamped``, ``mean``, ``lower_bound``, ``upper_bound``,
          and ``confidence_level``.
    """
    # Transform input to concentration
    concentration = transform_input_to_concentration(concentration_input)

    # Clamp mean to avoid exact 0 or 1
    mean_clamped = np.clip(sample_unit_rate, 0.001, 0.999)

    # Calculate alpha and beta
    alpha = mean_clamped * concentration
    beta = (1 - mean_clamped) * concentration

    # Calculate rho and variance
    rho = 1.0 / (concentration + 1.0)
    variance = n_trials * mean_clamped * (1 - mean_clamped) * (1 + (n_trials - 1) * rho)

    # Create Beta-Binomial distribution for CI calculation
    bb_dist = betabinom(n=n_trials, a=alpha, b=beta)

    # Calculate mean and confidence interval
    mean_value = n_trials * mean_clamped
    alpha_level = (1 - confidence_level) / 2
    lower_bound = bb_dist.ppf(alpha_level)
    upper_bound = bb_dist.ppf(1 - alpha_level)

    return {
        'alpha': alpha,
        'beta': beta,
        'concentration': concentration,
        'variance': variance,
        'rho': rho,
        'mean_clamped': mean_clamped,
        'mean': mean_value,
        'lower_bound': lower_bound,
        'upper_bound': upper_bound,
        'confidence_level': confidence_level
    }


def transform_input_to_concentration(
        concentration_input: float,
        conc_min: float = 0.5,
        conc_max: float = 100.0
) -> float:
    """Transform 0–100% slider input into a concentration parameter (log-scale).

    The transformation maps a UI-friendly confidence slider (0–100%) onto
    an internal concentration (shape) parameter for the Beta distribution.

    Args:
        concentration_input: User input in range [0, 100].
        conc_min: Minimum concentration value (default: 0.5).
        conc_max: Maximum concentration value (default: 100.0).

    Returns:
        Concentration parameter in range [conc_min, conc_max].
    """
    # Clamp input to valid range
    concentration_input = np.clip(concentration_input, 0.0, 100.0)

    # Logarithmic interpolation
    log_min = np.log(conc_min)
    log_max = np.log(conc_max)
    log_concentration = log_min + (concentration_input / 100.0) * (log_max - log_min)

    concentration = np.exp(log_concentration)

    return concentration


def transform_concentration_to_input(
        concentration: float,
        conc_min: float = 0.5,
        conc_max: float = 100.0
) -> float:
    """Invert the concentration transform back to the 0–100 control scale.

    Args:
        concentration: Concentration parameter to map back to [0, 100].
        conc_min: Minimum concentration value used in the forward transform.
        conc_max: Maximum concentration value used in the forward transform.

    Returns:
        Slider-scale value in [0, 100].
    """
    concentration = float(np.clip(concentration, conc_min, conc_max))
    log_min = np.log(conc_min)
    log_max = np.log(conc_max)
    return float(((np.log(concentration) - log_min) / (log_max - log_min)) * 100.0)


def clean_range_key(key):
    """Convert a tuple-like range key to a display-friendly string.

    Examples:
        ``"(0, 10)"`` → ``"0-10"``

    Args:
        key: Range key (tuple or string).

    Returns:
        String representation with parentheses removed and numbers
        normalized.
    """
    k = str(key).replace("(", "").replace(")", "").replace(" ", "")
    parts = k.split(",")
    cleaned_parts = []
    for p in parts:
        try:
            num = float(p)
            if num.is_integer():
                cleaned_parts.append(str(int(num)))
            else:
                cleaned_parts.append(str(num))
        except ValueError:
            cleaned_parts.append(p)
    return "-".join(cleaned_parts)


def _find_column(df: pd.DataFrame, substrings: list[str]) -> Optional[str]:
    """Find the first column whose lowercase name contains any substring.

    Args:
        df: DataFrame to search.
        substrings: List of lowercase substrings to look for.

    Returns:
        Original column name if found, otherwise None.
    """
    lower_map = {c.lower(): c for c in df.columns}
    for s in substrings:
        for lc, orig in lower_map.items():
            if s in lc:
                return orig
    return None


def _render_pis_summary(pis_df: pd.DataFrame) -> None:
    """Render summary metrics for PIS/consignment data used for fitting.

    Args:
        pis_df: DataFrame containing inspection IDs, sampling, plant counts,
            and an ``action`` indicator.
    """
    ins_col = _find_column(pis_df, ["inspection"])
    samp_col = _find_column(pis_df, ["total_sampling"])
    plant_col = _find_column(pis_df, ["total_plant"])
    action_col = _find_column(pis_df, ["action"])

    n_rows = len(pis_df)
    unique_inspections = pis_df[ins_col].nunique() if ins_col else 0
    total_sampling = pis_df[samp_col].sum() if samp_col else 0
    total_plants = pis_df[plant_col].sum() if plant_col else 0
    action_ones = int((pis_df[action_col] == 1).sum()) if action_col else 0

    stats = st.columns(4)
    with stats[0]:
        render_metric_card("Rows", f"{n_rows}", "Total number of consignment rows available in the selected input file.")
    with stats[1]:
        render_metric_card("Unique inspections", f"{unique_inspections}", "Number of distinct inspections represented in the selected input file.")
    with stats[2]:
        render_metric_card("Rows with action = 1", f"{action_ones}", "Number of rows where the action indicator equals 1 in the selected input file.")
    with stats[3]:
        render_metric_card("Total sampling units", f"{total_sampling:,}", "Total number of sampling units across the selected input file.")

    if total_plants:
        st.caption(f"Total plant units: {int(total_plants):,}")


def _fit_summary_lines(
        fit: Dict[tuple, Any],
        warnings: Iterable[tuple[Tuple, str]] = (),
        n: int = 1000
) -> list[str]:
    """Generate human-readable summary lines for a fitted Clarke model.

    Args:
        fit: Mapping from quantity ranges to fitted parameter dicts.
        warnings: Iterable of ``((lower, upper), message)`` warnings.
        n: Number of trials used for mean/SD summary calculations.

    Returns:
        List of markdown strings describing the fit per quantity range.
    """
    # Map key -> warning text for quick lookup
    warning_map: Dict[Tuple, list[str]] = {}
    for key, msg in warnings:
        warning_map.setdefault(key, []).append(msg)
    message_lines = ["**FIT SUCCESSFUL:**\n\nFINAL CLARK MODEL BETA-BINOMIAL PARAMETERS:\n"]
    for (lower, upper), results in fit.items():
        alpha = results["alpha"]
        beta = results["beta"]

        if alpha + beta == 0:
            mean = -1
            std_dev = -1
        else:
            mean = n * alpha / (alpha + beta)
            variance = (n * alpha * beta * (alpha + beta + n)) / (
                (alpha + beta) ** 2 * (alpha + beta + 1)
            )
            std_dev = variance ** 0.5
            warning = ""

        # Base summary line
        block = [
            f"For quantities ranging in `({lower}, {upper})`:\n"
            f"    α = {alpha:.4f}, β = {beta:.4f}\n"
            f"    Mean = {mean:.2f}, SD = {std_dev:.2f} (N = {n})"
        ]

        # Attach any warnings for this key
        if (lower, upper) in warning_map:
            for w in warning_map[(lower, upper)]:
                block.append(f"    \nWARNING: {w}")

        # Blank line between blocks
        message_lines.append("\n".join(block) + "\n")

    return message_lines


def _render_saved_parameters(sel: str, params: Dict[str, Any]) -> None:
    """Render a saved parameter set as metrics and Beta charts.

    Args:
        sel: Name of the selected parameter set.
        params: Dictionary of parameter values or nested dict of ranges.
    """
    if isinstance(params, dict) and params and all(isinstance(v, dict) for v in params.values()):
        st.markdown("### Parameter Ranges Summary")
        for key, pdict in params.items():
            cleaned_key = clean_range_key(key)
            alpha = float(pdict.get("alpha", FALLBACK_ALPHA))
            beta = float(pdict.get("beta", FALLBACK_BETA))
            theta = pdict.get("theta", FALLBACK_THETA)
            p_value = pdict.get("p")
            render_labeled_help(
                f"Quantity Range: {cleaned_key}",
                "Beta binomial parameters for a risk unit if the quantity of plants is within this range.",
            )
            summary_cols = st.columns(4 if p_value is not None else 3)
            with summary_cols[0]:
                render_metric_card("Alpha", f"{alpha:.6f}", "Alpha parameter of the beta-binomial distribution.")
            with summary_cols[1]:
                render_metric_card("Beta", f"{beta:.6f}", "Beta parameter of the beta-binomial distribution.")
            with summary_cols[2]:
                render_metric_card("Theta", f"{theta}", "Theta clustering parameter of the beta-binomial distribution.")
            if p_value is not None:
                with summary_cols[3]:
                    render_metric_card("p", f"{float(p_value):.2f}", "Clustering parameter for the beta-binomial contamination distribution.")
            if alpha + beta != 0:
                st.markdown("<div style='height: 1.25rem;'></div>", unsafe_allow_html=True)
                st.altair_chart(
                    _beta_chart(alpha, beta, f"Beta-binomial PDF for range {cleaned_key}"),
                    use_container_width=True,
                )
            st.markdown("---")
        st.info("Sets are stored in tmp/contamination/contamination_parameter_sets.json.")
        return

    if params:
        alpha = float(params.get("alpha", FALLBACK_ALPHA))
        beta = float(params.get("beta", FALLBACK_BETA))
        theta = params.get("theta", FALLBACK_THETA)
        p_value = params.get("p")
        summary_cols = st.columns(4 if p_value is not None else 3)
        with summary_cols[0]:
            render_metric_card("Alpha", f"{alpha:.6f}", "Alpha parameter of the beta-binomial distribution.")
        with summary_cols[1]:
            render_metric_card("Beta", f"{beta:.6f}", "Beta parameter of the beta-binomial distribution.")
        with summary_cols[2]:
            render_metric_card("Theta", f"{theta}", "Theta clustering parameter of the beta-binomial distribution.")
        if p_value is not None:
            with summary_cols[3]:
                render_metric_card("p", f"{float(p_value):.2f}", "Clustering parameter for the beta-binomial contamination distribution.")
        if alpha + beta != 0:
            st.markdown("<div style='height: 1.25rem;'></div>", unsafe_allow_html=True)
            st.altair_chart(_beta_chart(alpha, beta, f"Beta-binomial PDF for {sel}"), use_container_width=True)
        st.info("Sets are stored in tmp/contamination/contamination_parameter_sets.json.")


def _save_current_fit(
    *,
    fit_to_show: Optional[Dict[Tuple, Any]],
    fall_back_fit_to_show: Optional[ClarkeFit],
    inputs_by_quantity: Optional[Dict[Any, Any]],
    name_input: str,
    p_override: Optional[float] = None,
) -> None:
    """Save the current fitted or fallback contamination parameters.

    Args:
        fit_to_show: Dictionary of fitted parameters by quantity range, or None.
        fall_back_fit_to_show: Fallback ClarkeFit instance if the fit failed.
        inputs_by_quantity: Clarke-model input structures per quantity range.
        name_input: Name to use when saving the parameter set.
    """
    if fit_to_show is not None and inputs_by_quantity is not None:
        saved_name = _save_param_set_fit(
            name=name_input or _next_param_name(_read_param_store()),
            res=fit_to_show,
            inputs_by_quantity=inputs_by_quantity,
            p_override=p_override,                     
        )
        st.success(f"Saved '{saved_name}' with parameters as above.")
        return

    if fall_back_fit_to_show is not None:
        saved_name = _save_param_set_fall_back(
            name_input or _next_param_name(_read_param_store()),
            fall_back_fit_to_show.alpha,
            fall_back_fit_to_show.beta,
            float("inf"),
        )
        st.success(
            f"Saved '{saved_name}' with alpha={fall_back_fit_to_show.alpha:.6f}, "
            f"beta={fall_back_fit_to_show.beta:.6f}, theta={fall_back_fit_to_show.theta}"
        )
        return

    st.error("No parameters to save. Fit parameters first.")


# ---- Page setup ----
init_state()
slippage_state = get_slippage_state()
paths = slippage_state["paths"]
default_cluster_p = _load_default_cluster_p(getattr(paths, "config", None))
render_sidebar_navigation()
apply_shared_page_styles()


st.warning(
    "**Test Deployment Notice: This is a test deployment with limited functionality and is under active development. "
    "Features may be incomplete and subject to change. Results have not been validated.**"
)
st.title("Page 2 - Contamination Fit")
render_page_intro(
    "Fit, assign, and manage contamination parameters. "
    "PIS upload and RBS selection live in the <i>Fit Contamination</i> tab. "
    "All outputs are written to <i>tmp/contamination</i>."
)

saved_tab, fit_tab, assign_tab = st.tabs(
    ["Saved Parameter Sets", "Fit Contamination Using Data", "Assign Contamination Manually"]
)

# Fit contamination tab
with fit_tab:
    st.subheader("Fit beta-binomial contamination parameters")
    st.write("Select a consignment source, fit contamination parameters, and save the result for later reuse. Fits are based on the PIS action upload and RBS calculator selection in this tab.")

    rbs_candidates = sorted((Path("tmp") / "consignments" / "source").glob("*.csv"))
    render_labeled_help(
        "Consignment data source",
        "Choose whether to fit contamination parameters from the existing Page 1 consignment file or upload a new CSV for this page only.",
    )
    rbs_source = st.radio(
        "Consignment data source",
        ["Use consignment data from Page 1", "Upload a new consignment data file"],
        index=0,
        key="page2_rbs_source",
        label_visibility="collapsed",
    )
    if rbs_source == "Use consignment data from Page 1":
        if not rbs_candidates:
            st.warning("No consignment files found in tmp/consignments. Add one on Page 1 or upload a file below.")
        else:
            render_labeled_help(
                "Consignment file",
                "Select the saved consignment CSV to use as the source data for fitting contamination parameters.",
            )
            current_rbs = slippage_state["paths"].rbs_data
            default_idx = 0
            if current_rbs in rbs_candidates:
                default_idx = rbs_candidates.index(current_rbs)
            chosen_rbs = st.selectbox(
                "Consignment file",
                rbs_candidates,
                index=default_idx,
                format_func=lambda p: p.name,
                label_visibility="collapsed",
            )
            set_paths(pis_data=chosen_rbs, rbs_data=chosen_rbs, synthetic_seed=chosen_rbs)
            paths = slippage_state["paths"]
    else:
        rbs_upload = st.file_uploader(
            "Upload consignment data CSV",
            type=["csv"],
            key="page2_rbs_upload",
            help="Upload a new consignment data file to use for contamination fitting on this page.",
        )
        if rbs_upload is not None:
            dest = CONTAM_DIR / "fit_rbs_data.csv"
            rbs_df = pd.read_csv(rbs_upload)
            dest.parent.mkdir(parents=True, exist_ok=True)
            rbs_df.to_csv(dest, index=False)
            set_paths(pis_data=dest, rbs_data=dest, synthetic_seed=dest)
            paths = slippage_state["paths"]
            st.success(f"Saved consignment data to {dest}")

    pis_df = None
    pis_preview = _load_preview(slippage_state["paths"].rbs_data)
    if pis_preview is not None:
        st.dataframe(pis_preview, use_container_width=True)
        try:
            pis_df = pd.read_csv(slippage_state["paths"].rbs_data)
        except Exception:  # pylint: disable=broad-except
            pis_df = None
    else:
        st.info("No consignment data loaded yet.")

    # Summary stats beneath the table (one-column flow)
    if pis_df is not None and not pis_df.empty:
        _render_pis_summary(pis_df)

    fit_cols = st.columns(2)
    with fit_cols[0]:
        render_labeled_help(
            "Fit contamination parameters",
            "Estimate the beta-binomial contamination parameters from the selected consignment dataset. Theta is fixed to inf (no clustering) for manual contamination assignment.",
        )
        if st.button("Fit contamination parameters", type="primary"):
            if paths.pis_data is None or paths.rbs_data is None:
                st.error("Upload PIS data and select an RBS file before fitting.")
            else:
                try:
                    fit, pis_df, inputs_by_quantity, warnings = fit_contamination_distribution(paths.pis_data)
                    slippage_state["fit"] = fit
                    slippage_state["inputs_by_quantity"] = inputs_by_quantity
                    st.success("\n".join(_fit_summary_lines(fit, warnings)))

                except Exception as exc:  
                    st.error(f"FITTING FAILED: {exc}")
                    fall_back_fit = ClarkeFit(
                        alpha=FALLBACK_ALPHA,
                        beta=FALLBACK_BETA,
                        theta=FALLBACK_THETA,
                        raw_result={"fallback": True, "error": str(exc)},
                    )
                    slippage_state["fall_back_fit"] = fall_back_fit
                    st.info("Applied fallback parameters.  "
                            "If wanting different parameters, set manual contamination parameters in 'Assign Contamination Manually' tab.")

    fit_to_show: Dict[Tuple,Any] = slippage_state.get("fit")
    fall_back_fit_to_show: Optional[ClarkeFit] = slippage_state.get("fall_back_fit")
    inputs_by_quantity: Optional[Dict[Any, Any]] = slippage_state.get("inputs_by_quantity")
    if fit_to_show is None and fall_back_fit_to_show is not None:
        metrics = st.columns(3)
        with metrics[0]:
            render_metric_card("Alpha", f"{fall_back_fit_to_show.alpha:.6f}", "Alpha parameter of the fallback beta-binomial contamination distribution.")
        with metrics[1]:
            render_metric_card("Beta", f"{fall_back_fit_to_show.beta:.6f}", "Beta parameter of the fallback beta-binomial contamination distribution.")
        with metrics[2]:
            render_metric_card("Theta", f"{fall_back_fit_to_show.theta}", "Theta clustering parameter of the fallback beta-binomial contamination distribution.")
        st.markdown("<div style='height: 1.25rem;'></div>", unsafe_allow_html=True)
        st.altair_chart(
            _beta_chart(fall_back_fit_to_show.alpha, fall_back_fit_to_show.beta, "Beta-Binomial Probability Density Function"),
            use_container_width=True,
        )

    assign_manual_p = st.radio(
        "Assign Manual P",
        ["Use default p parameter", "Manual assignmnet of p parameter"],
        index=0,
        key="assign_manual_p",
        label_visibility="collapsed",
    )
    if assign_manual_p == "Use default p parameter":
        cluster_p = FALLBACK_P
    else:
        render_labeled_help(
            "Clustering p",
            "Controls how concentrated contamination is across sample units. 0 means more spread out; 1 means more clustered.",
        )
        cluster_p = st.slider(
            "fit_cluster_p_slider",
            min_value=0.0,
            max_value=1.0,
            value=FALLBACK_P,
            step=0.01,
            key="fit_cluster_p_slider",
            label_visibility="collapsed",
        )

    render_labeled_help(
        "Parameter set name",
        "Name used when saving the fitted contamination parameter set for later reuse on Page 5.",
    )
    name_input = st.text_input(
        "Parameter set name",
        value=st.session_state.get("last_saved_param_set", ""),
        key="fit_save_name",
        label_visibility="collapsed",
    )
    can_save_fitted_parameters = fit_to_show is not None and bool(name_input.strip())
    render_labeled_help(
        "Save fitted parameters",
        "Write the current fitted contamination parameters to the temporary parameter store.",
    )
    if st.button("Save fitted parameters", type="primary", key="save_fit_params", disabled=not can_save_fitted_parameters):
        _save_current_fit(
            fit_to_show=fit_to_show,
            fall_back_fit_to_show=fall_back_fit_to_show,
            inputs_by_quantity=inputs_by_quantity,
            name_input=name_input,
            p_override = cluster_p,
        )

# Manual assignment tab
with assign_tab:
    st.subheader("Assign contamination manually")
    st.write(
        "Set contamination parameters directly when you already know the target values, either by entering beta-binomial parameters or by specifying an average contamination rate at the lowest unit level."
    )

    render_labeled_help(
        "Assignment mode",
        "Choose whether to specify beta-binomial parameters directly or derive them from an average contamination rate at the lowest unit level.",
    )
    mode = st.selectbox(
        "mode_select",
        ["Specify Beta-Binomial Parameters (alpha and beta)", "Specify Contamination Rate (at lowest unit level)"],
        index=1,
        label_visibility="collapsed",
    )

    assigned_state = st.session_state.get(
        "page2_assigned_fit",
        {
            "alpha": FALLBACK_ALPHA,
            "beta": FALLBACK_BETA,
            "theta": FALLBACK_THETA,
            "p": FALLBACK_P,
            "sample_unit_rate": 0.01,
        },
    )

    if mode == "Specify Contamination Rate (at lowest unit level)":
        stored_mean = st.session_state.get("manual_mean_rate", float(assigned_state.get("sample_unit_rate", 0.01)))
        stored_mean_input = st.session_state.get("manual_mean_input_pct", float(stored_mean) * 100.0)
        pct_default = float(stored_mean_input)
        stored_manual_p = float(st.session_state.get("manual_cluster_p", assigned_state.get("p", default_cluster_p)))

        st.write("")
        render_labeled_help(
            "Average Contamination Rate (0%-100%)",
            "Enter the percentage of plants that are typically contaminated in your samples.",
        )

        pct_input = st.number_input(
            "pct",
            min_value=0.1,
            max_value=99.9,
            value=pct_default,
            step=0.05,
            format="%.1f",
            key="manual_mean_input",
            label_visibility="collapsed",
        )

        sample_unit_rate = pct_input / 100.0
        stored_conc = st.session_state.get(
            "manual_concentration",
            float(max(2.0, assigned_state.get("alpha", FALLBACK_ALPHA) + assigned_state.get("beta", FALLBACK_BETA))),
        )
        stored_concentration_input = st.session_state.get(
            "manual_concentration_input",
            transform_concentration_to_input(stored_conc),
        )

        st.write("")
        render_labeled_help(
            "% Confidence in Specified Contamination Rate", # Is this the correct term to use? If I specify 100% confidence, the distribution does not collapse to have zero confidence
            "(0% = No Confidence, 100% = Full Confidence)",
        )

        concentration_input = st.slider(
            "concentration",
            min_value=0.0,
            max_value=100.0,
            value=float(stored_concentration_input),
            step=0.5,
            key="manual_concentration_slider",
            label_visibility="collapsed",
        )

        st.write("")
        render_labeled_help(
            "Clustering p",
            "Controls how concentrated contamination is across sample units. 0 means more spread out; 1 means more clustered.",
        )
        manual_cluster_p = st.slider(
            "manual_cluster_p_slider",
            min_value=0.0,
            max_value=1.0,
            value=stored_manual_p,
            step=0.01,
            key="manual_cluster_p_slider",
            label_visibility="collapsed",
        )

        n_trials = 100
        params = calculate_beta_binomial_params(sample_unit_rate, concentration_input, n_trials=n_trials)

        adj_alpha = params["alpha"]
        adj_beta = params["beta"]
        concentration = params["concentration"]
        lb = params["lower_bound"]
        ub = params["upper_bound"]
        mean = params["mean"]
        theta_val = float("inf")

        st.session_state["page2_assigned_fit"] = {
            "alpha": adj_alpha,
            "beta": adj_beta,
            "theta": theta_val,
            "p": manual_cluster_p,
            "sample_unit_rate": sample_unit_rate,
        }
        st.session_state["manual_concentration"] = concentration
        st.session_state["manual_concentration_input"] = concentration_input
        st.session_state["manual_cluster_p"] = manual_cluster_p
        st.session_state["manual_mean_rate"] = sample_unit_rate
        st.session_state["manual_mean_input_pct"] = pct_input

        st.write("Contamination Summary")
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            render_metric_card(
                "Expected Average",
                f"{mean:.1f} out of {n_trials} plants",
                "Average number of contaminated plants expected within a sample of 100 plants.",
            )
        with col2:
            render_metric_card(
                "95% Range",
                f"{lb:.1f} - {ub:.1f}",
                "The typical range where 95% of observed contaminated plant counts will fall. This accounts for natural variability in the sampling process.",
            )
        with col3:
            render_metric_card("Alpha", f"{adj_alpha:.6f}", "Alpha parameter of the beta-binomial distribution.")
        with col4:
            render_metric_card("Beta", f"{adj_beta:.6f}", "Beta parameter of the beta-binomial distribution.")
        with col5:
            render_metric_card("Theta", f"{theta_val}", "Theta clustering parameter of the beta-binomial distribution.")
        st.write("")
        st.write("")
        st.altair_chart(
            _beta_chart(adj_alpha, adj_beta, "Beta-Binomial Probability Density Function"),
            use_container_width=True,
        )

        st.write("")
        st.write("")
        render_labeled_help(
            "Parameter Set Name",
            'File name to appear in the "Save Parameter Sets" associated with these set parameters',
        )

        manual_name = st.text_input(
            "Parameter set name for manual values",
            value=st.session_state.get("last_saved_param_set", ""),
            key="manual_save_name_sample_rate",
            label_visibility="collapsed",
        )
        if st.button(
            "Save current parameters",
            type="primary",
            key="save_manual_params_sample_rate",
            disabled=not bool(manual_name.strip()),
        ):
            saved_name = _save_param_set_assign(
                manual_name or _next_param_name(_read_param_store()),
                adj_alpha,
                adj_beta,
                theta_val,
                sample_unit_rate,
                p=manual_cluster_p,
            )
            st.success(
                f"Saved '{saved_name}' with alpha={adj_alpha:.6f}, beta={adj_beta:.6f}, p={manual_cluster_p:.2f}, and sample unit rate={sample_unit_rate}"
            )
    else:
        st.caption("Adjust alpha/beta directly. Theta is fixed to infinity by default.")
        col_a, col_b, col_t = st.columns(3)
        with col_a:
            render_labeled_help(
                "Alpha",
                "Alpha parameter for the beta-binomial contamination distribution.",
            )
        alpha_val = col_a.number_input(
            "Alpha",
            min_value=0.000001,
            value=float(assigned_state["alpha"]),
            step=0.0005,
            format="%.4f",
            label_visibility="collapsed",
        )
        with col_b:
            render_labeled_help(
                "Beta",
                "Beta parameter for the beta-binomial contamination distribution.",
            )
        beta_val = col_b.number_input(
            "Beta",
            min_value=0.000001,
            value=float(assigned_state["beta"]),
            step=0.0005,
            format="%.4f",
            label_visibility="collapsed",
        )
        with col_t:
            render_labeled_help(
                "Clustering p",
                "Controls how concentrated contamination is across sample units. 0 means more spread out; 1 means more clustered.",
            )
        p_val = col_t.number_input(
            "p",
            min_value=0.0,
            max_value=1.0,
            value=float(assigned_state["p"]),
            step=0.0005,
            format="%.4f",
            label_visibility="collapsed",
        )

        st.session_state["page2_assigned_fit"] = {
            "alpha": alpha_val,
            "beta": beta_val,
            "theta": float(assigned_state["theta"]),
            "p": p_val,
            "sample_unit_rate": assigned_state.get("sample_unit_rate", 0.01),
        }

        st.altair_chart(
            _beta_chart(alpha_val, beta_val, "Beta-Binomial Probability Density Function"),
            use_container_width=True,
        )
        render_labeled_help(
            "Parameter Set Name",
            "File name to appear in the saved manual parameter set list.",
        )
        manual_name = st.text_input(
            "Parameter set name for manual values",
            value=st.session_state.get("last_saved_param_set", ""),
            key="manual_save_name_alpha_beta",
            label_visibility="collapsed",
        )
        render_labeled_help(
            "Save current parameters",
            "Save the manually specified beta-binomial parameters to the temporary parameter store.",
        )
        if st.button(
            "Save current parameters",
            type="primary",
            key="save_manual_params_alpha_beta",
            disabled=not bool(manual_name.strip()),
        ):
            saved_name = _save_param_set_assign(
                manual_name or _next_param_name(_read_param_store()),
                alpha_val,
                beta_val,
                p_val,
                assigned_state.get("sample_unit_rate", None),
                p=float(assigned_state.get("p", default_cluster_p)),
            )
            st.success(
                f"Saved '{saved_name}' with alpha={alpha_val:.6f}, beta={beta_val:.6f}, theta={theta_val}, p={float(assigned_state.get('p', default_cluster_p)):.2f}"
            )

# Render saved parameters
with saved_tab:
    st.subheader("Saved contamination parameter sets")
    st.write("Review saved contamination parameter sets and load one for reuse.")
    saved = _read_param_store()
    if not saved:
        st.info("No saved parameter sets yet.")
    else:
        saved_keys = list(saved.keys())
        default_idx = 0
        last_saved = st.session_state.get("last_saved_param_set")
        if last_saved and last_saved in saved_keys:
            default_idx = saved_keys.index(last_saved)
        render_labeled_help(
            "Select a saved set",
            "Choose a saved contamination parameter set to inspect the stored values.",
        )
        sel = st.selectbox("Select a saved set", saved_keys, index=default_idx, label_visibility="collapsed")
        params = saved.get(sel, {})
        _render_saved_parameters(sel, params)
        if st.button("Delete this saved set", type="secondary"):
            try:
                updated = dict(saved)
                updated.pop(sel, None)
                _write_param_store(updated)
                if st.session_state.get("last_saved_param_set") == sel:
                    st.session_state.pop("last_saved_param_set", None)
                st.success(f"Deleted '{sel}'")
                st.rerun()
            except Exception as exc:  # pylint: disable=broad-except
                st.error(f"Unable to delete saved parameter set: {exc}")
st.caption(
    "These parameters are injected into PoPS Border configuration so downstream pages use the updated contamination distribution."
)

st.divider()
nav_cols = st.columns(3)
with nav_cols[0]:
    if st.button(
        "Reset and Return Home",
        type="secondary",
        key="nav_reset_page2",
        help="Delete temporary files and restart from the home page",
    ):
        try:
            # Remove saved parameter sets and all tmp artifacts
            if PARAM_STORE.exists():
                PARAM_STORE.unlink()
            # Use safe reset utility to clear temporary directory
            from .tmp_utils import reset_tmp_directory
            reset_tmp_directory(TMP_DIR)
            # Clear in-memory state
            st.session_state.clear()
            slippage_state["paths"] = create_default_paths()
            slippage_state["fit"] = None
            st.switch_page("frontend.py")
        except Exception as exc:  # pylint: disable=broad-except
            st.error(f"Unable to reset temporary files: {exc}")

with nav_cols[1]:
    if st.button("Previous Page", type="primary", key="nav_back_page2"):
        st.switch_page("pages/1_Consignment_Generation.py")

with nav_cols[2]:
    if st.button("Next Page", type="primary", key="nav_forward_page4"):
        st.switch_page("pages/3_Inspection_Process.py")
