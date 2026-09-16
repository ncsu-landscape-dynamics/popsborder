# © 2026 The Johns Hopkins University Applied Physics Laboratory LLC

from __future__ import annotations


import sys, os
# Add the project root (parent of gui) to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.append(project_root)

import copy
import pickle
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from runtime_warnings import suppress_optional_dependency_warnings

suppress_optional_dependency_warnings()

import pandas as pd

from popsborder.generator import SyntheticConsignmentDataGenerator, save_to_csv
from popsborder.inputs import (
    load_compliance_lookup_csv,
    load_configuration,
    load_scenario_table,
)
from popsborder.inspections import construct_risk_units
from popsborder.outputs import save_scenario_result_to_pandas
from popsborder.scenarios import run_scenarios
from slippage_model_utils.clarke_model_support_functions import gen_clarke_model_inputs
from slippage_model_utils.r_script_wrapper import run_clarke_bb_group_model, RVariableCreator
from slippage_model_utils.engineered_feature_creator import  create_engineered_features
from slippage_model_utils.paths import DefaultPaths

# Define default paths object
default_paths = DefaultPaths()

# Default config columns to persist into results
CONFIG_COLUMNS = [
    "contamination/contamination_unit",
    "contamination/contamination_rate/distribution",
    "contamination/contamination_rate/value",
    "contamination/arrangement",
    "inspection/sample_strategy",
    "inspection/proportion/value",
    "inspection/tolerance_level",
    "name",
]

# Default result columns to persist into outputs
RESULT_COLUMNS = [
    "num_inspections",
    "intercepted",
    "false_neg",
    "missing",
    "num_inspection_units",
    "num_sample_units",
    "num_plants",
    "avg_inspection_units_opened_completion",
    "avg_inspection_units_opened_detection",
    "pct_inspection_units_opened_completion",
    "pct_inspection_units_opened_detection",
    "avg_sample_units_inspected_completion",
    "avg_sample_units_inspected_detection",
    "pct_sample_units_inspected_completion",
    "pct_sample_units_inspected_detection",
    "avg_plant_units_inspected_completion",
    "avg_plant_units_inspected_detection",
    "pct_plant_units_inspected_completion",
    "pct_sample_units_inspected_completion",
    "pct_plant_units_inspected_detection",
    "total_missed_contaminants",
    "total_intercepted_contaminants",
    "total_slipped_units",
    "avg_slipped_units_per_consignment",
    "avg_slipped_sample_units_per_consignment",
    "total_contaminated_units",
    "total_contaminated_sample_units",
    "total_contaminated_inspection_units",
    "total_intercepted_inspection_units",
    "total_slipped_inspection_units",
]

@dataclass
class SyntheticOptions:
    """Options for synthetic consignment data generation.

    Attributes:
        n_samples: Number of synthetic consignments to generate.
        sampling_method: Sampling method passed to
            :class:`SyntheticConsignmentDataGenerator` (e.g., "sequential",
            "naive", "gmm").
    """

    n_samples: int = 10
    sampling_method: str = "sequential"


DEFAULT_DATA_DIR = default_paths.input_data_dir()
COMPLIANCE_FILENAME = "compliance_table.csv"
CONFIG_FILENAME = "config.yml"



@dataclass
class SlippagePaths:
    """Container for common filesystem paths used by the slippage pipeline.

    Attributes:
        data_dir: Base directory for input data.
        config: Path to the main contamination/inspection config file.
        scenario_table: Path to the slippage scenario table CSV.
        compliance_lookup: Path to the RBS compliance table.
        pis_data: Optional path to PIS input data (if precomputed).
        rbs_data: Optional path to RBS calculator data (if precomputed).
        synthetic_seed: Optional path to a file used as a seed for synthetic
            consignment generation.
        synthetic_output: Path where synthetic consignment data should be
            written.
        output_dir: Root directory for pipeline outputs.
    """

    data_dir: Path = DEFAULT_DATA_DIR
    config: Path = DEFAULT_DATA_DIR / "config.yml"
    scenario_table: Path = DEFAULT_DATA_DIR / "pis_contaminate_scenarios.csv"
    compliance_lookup: Path = DEFAULT_DATA_DIR / "compliance_table.csv"
    pis_data: Optional[Path] = None
    rbs_data: Optional[Path] = None
    synthetic_seed: Optional[Path] = None
    synthetic_output: Path = default_paths.tmp_dir() / "synthetic_consignment_data.csv"
    output_dir: Path = default_paths.output_dir()


@dataclass
class ExperimentPaths:
    """Container for an experiment's input paths.

    Attributes:
        experiment_dir: Root directory of the experiment.
        scenario_table: Path to the scenario table for this experiment.
        consignment: Optional explicit consignment file path (overrides
            scenario entries).
        compliance: Optional explicit compliance table file path (overrides
            scenario entries).
        config: Optional explicit config path (overrides default).
    """

    experiment_dir: Path
    scenario_table: Path
    consignment: Optional[Path] = None
    compliance: Optional[Path] = None
    config: Optional[Path] = None


@dataclass
class ClarkeFit:
    """Fitted parameters for the Clarke beta-binomial contamination model.

    Attributes:
        alpha: Fitted alpha parameter.
        beta: Fitted beta parameter.
        theta: Fitted clustering (theta) parameter.
        raw_result: Raw result dictionary returned by the R model.
    """

    alpha: float
    beta: float
    theta: float
    raw_result: Dict[str, Any]


@dataclass
class PipelineResult:
    """Outputs from a slippage pipeline run.

    Attributes:
        contamination_fit: Fitted contamination parameters (if applicable).
        scenario_results: Scenario-level summary DataFrame.
        config: Final configuration dictionary used for the run.
        compliance_table: Loaded compliance lookup table/policy.
        pis_data: PIS input DataFrame used (may be empty).
        rbs_data: RBS input DataFrame used (may be empty).
        num_consignments: Total number of consignments simulated or inferred.
        output_dir: Directory where outputs were written.
        output_files: List of paths to key output files (CSV, etc.).
    """

    contamination_fit: ClarkeFit
    scenario_results: pd.DataFrame
    config: Dict[str, Any]
    compliance_table: Any
    pis_data: pd.DataFrame
    rbs_data: pd.DataFrame
    num_consignments: int
    output_dir: Path
    output_files: List[Path]


def create_default_paths(base_dir: Path = DEFAULT_DATA_DIR) -> SlippagePaths:
    """Create default SlippagePaths for a given base directory.

    The function infers PIS and RBS data paths, falling back across
    ``synthetic_rbs_calc_data_enriched.csv`` and
    ``synthetic_rbs_calc_data.csv`` where necessary, and uses those to
    set the ``synthetic_seed`` path if available.

    Args:
        base_dir: Base directory containing input files.

    Returns:
        A SlippagePaths instance with inferred defaults.
    """
    pis_path = base_dir / "synthetic_pis_data.csv"
    rbs_enriched = base_dir / "synthetic_rbs_calc_data_enriched.csv"
    rbs_plain = base_dir / "synthetic_rbs_calc_data.csv"
    rbs_path = rbs_enriched if rbs_enriched.exists() else (rbs_plain if rbs_plain.exists() else None)
    synthetic_seed = rbs_path if rbs_path and rbs_path.exists() else None
    return SlippagePaths(
        data_dir=base_dir,
        pis_data=pis_path if pis_path.exists() else None,
        rbs_data=rbs_path,
        synthetic_seed=synthetic_seed,
    )


def load_scenario_dataframe(path: Path, *, dtype: str = "object"):
    """Load the slippage scenario table as a pandas DataFrame.

    This is a thin wrapper around :func:`popsborder.inputs.load_scenario_table`.

    Args:
        path: Path to a scenario-table CSV or spreadsheet.
        dtype: Optional dtype for columns (currently unused; kept for
            forward compatibility).

    Returns:
        Scenario table as a pandas DataFrame or list-of-dicts, depending on
        the underlying loader.
    """
    scenarios = load_scenario_table(path)
    return scenarios


def load_compliance_policy(path: Path) -> Dict[str, Any]:
    """Load a compliance policy from CSV or a pickled dict.

    Args:
        path: Path to a CSV compliance table or a pickled dictionary.

    Returns:
        Compliance lookup structure (dict-like) as required by the
        inspection module.

    Raises:
        FileNotFoundError: If the specified path does not exist.
        pickle.UnpicklingError: If the pickle file cannot be loaded.
    """
    policy_path = Path(path)
    if policy_path.suffix.lower() == ".pkl":
        with open(policy_path, "rb") as handle:
            return pickle.load(handle)
    return load_compliance_lookup_csv(policy_path)


def generate_synthetic_data(
    seed_path: Path,
    output_path: Path,
    options: SyntheticOptions,
    producer_grouping_path: Optional[Path] = None,
    status: Optional["st.delta_generator.DeltaGenerator"] = None,  # type: ignore
) -> pd.DataFrame:
    def log(msg: str):
        if status is not None:
            status.write(msg)
        else:
            print(msg)

    if seed_path is None:
        raise FileNotFoundError("Seed data path was not provided.")
    seed_path = Path(seed_path).resolve()
    output_path = Path(output_path).resolve()
    if not seed_path.exists():
        raise FileNotFoundError(f"Seed data not found at {seed_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    config = None
    config_path = Path(DEFAULT_DATA_DIR / CONFIG_FILENAME).resolve()
    if config_path.exists():
        config = load_configuration(config_path)

    producer_grouping = None
    if producer_grouping_path is not None:
        producer_grouping_path = Path(producer_grouping_path).resolve()
        if not producer_grouping_path.exists():
            raise FileNotFoundError(f"Producer grouping file not found at {producer_grouping_path}")
        producer_grouping = pd.read_csv(producer_grouping_path)
    else:
        raise FileNotFoundError(
            "Producer grouping file not found and is needed. Supply in 'Producer Grouping' tab"
        )
    try:
        if producer_grouping_path is None:
            raise FileNotFoundError(
                "Producer grouping file not found and is needed. Supply in 'Producer Grouping' tab"
            )
        # Now use `log` instead of print
        log("Initialising R variable creator")
        creator = RVariableCreator()

        log("Cleaning (and grouping where applicable) categorical names")
        log("---Cleaning Producer Name")
        synth_data = pd.read_csv(seed_path)  # or however you load it previously
        synth_data["PRODUCER_NAME_RAW"] = synth_data["PRODUCER_NAME"]
        synth_data["PRODUCER_NAME1"] = creator.batch_basic_text_preproc(
            text_fields=synth_data["PRODUCER_NAME_RAW"]
        )

        producer_grouping = producer_grouping.rename(
            columns={"PRODUCER_NAME": "name", "grouping": "group"}
        )

        log("---Creating producer group mappings")
        synth_data = creator.entity_resolution(
            df=synth_data,
            entity_resolution_lookup_table=producer_grouping,
            use_parquet=False,
        )

        log("---Cleaning Importer Name")
        synth_data["IMPORTER_NAME_RAW"] = synth_data["IMPORTER_NAME"]
        synth_data["IMPORTER_NAME1"] = creator.batch_basic_text_preproc(
            synth_data["IMPORTER_NAME_RAW"]
        )

        log("Reconstructing risk units")
        dt_train = synth_data.copy()
        synth_data["PRODUCER_NAME"] = synth_data["PRODUCER_GROUP_NAME1"]
        synth_data["IMPORTER_NAME"] = synth_data["IMPORTER_NAME1"]
        synth_data = construct_risk_units(config=config, data=synth_data)

        log("Creating engineered features")
        synth_data = create_engineered_features(
            synth_data=synth_data,
            dt_train=dt_train,
            producer_group_mapping=producer_grouping,
            status=status
        )

        log("Finalising producer group column and importer top name")
        synth_data["producer_group"] = synth_data["PRODUCER_NAME"]
        synth_data["IMPORTER_NAME"] = synth_data["IMPORTER_NAME_TOP"]
    except:
        log(f"Generation of engineered features failed (most likely issue is the R wrapper, contact admin for fix).  "
            f"Synthetic consignments will not have following features: "
            f"Resolved Producer/Importer Names, Quantity Binaries, Top Producer/Importer Names")
        generator = SyntheticConsignmentDataGenerator(
            config=config,
            producer_group_mapping=producer_grouping,
            input_data_file=seed_path,
        )
        synth_data = generator.generate_from_input_data(
            n_consignments=options.n_samples,
            sampling_method=options.sampling_method,
        )
    log(f"Saving synthetic data to {output_path}")
    save_to_csv(synth_data, filename=output_path)
    return synth_data

def _infer_num_consignments(consignment_path: Optional[Path]) -> int:
    """Infer number of consignments from a consignment file.

    This counts unique inspection identifiers from commonly used ID
    columns; if none are present or usable, it falls back to the total
    number of rows.

    Args:
        consignment_path: Path to a CSV file containing consignment data.

    Returns:
        Estimated number of consignments (minimum 1).
    """
    if consignment_path and Path(consignment_path).exists():
        try:
            df = pd.read_csv(consignment_path)
            id_cols = [
                "INSPECTION_NUMBER",
                "INSPECTION_ID",
                "inspection_number",
                "inspection_id",
            ]
            for col in id_cols:
                if col in df.columns:
                    n_unique = df[col].nunique(dropna=True)
                    if n_unique > 0:
                        return max(1, int(n_unique))
            return max(1, len(df))
        except Exception:
            pass
    return 1



def fit_contamination_distribution(
    pis_data_path: Path,
) -> Tuple[Dict[Tuple,Any], pd.DataFrame, Dict[Any, Any], list[tuple[tuple, str]]]:
    """Fit contamination parameters using the Clarke beta-binomial model.

    This helper:

    * Loads a PIS dataset with an ``action`` column.
    * Constructs Clarke-model inputs by quantity decile using
      :func:`gen_clarke_model_inputs`.
    * Invokes the R-side Clarke BB group model via
      :func:`run_clarke_bb_group_model` for each decile.
    * Enforces a default alpha/beta pair if the fitted values are both
      zero, recording warnings for such cases.

    Args:
        pis_data_path: Path to the PIS data CSV with an ``"action"`` column.

    Returns:
        A tuple of:
            * ``res``: Mapping from (lower, upper) quantity range to fitted
              parameter dict.
            * ``pis_df``: Original PIS DataFrame.
            * ``inputs_by_quantity``: Input structures per quantity range.
            * ``warnings``: List of ``((lower, upper), message)`` tuples for
              ranges where defaults were used.

    Raises:
        FileNotFoundError: If the PIS data path does not exist.
        ValueError: If required columns are missing or inputs cannot be
            constructed.
    """
    if pis_data_path is None or not Path(pis_data_path).exists():
        raise FileNotFoundError("PIS action data not provided. Upload on Page 2 - Contamination Fit.")
    pis_df = pd.read_csv(pis_data_path)
    if "action" not in pis_df.columns:
        raise ValueError("Data files must include binary 'action' column to align for fitting.")
    try:
        inputs_by_quantity = gen_clarke_model_inputs(pis_df)
    except StopIteration as exc:
        raise ValueError(
            "Fitting failed: check the uploaded data. "
            "Verify required columns are there."
        ) from exc

    if not inputs_by_quantity:
        raise ValueError("Fitting failed: generating of Clark inputs has failed.  Check input data.")

    res = {}
    warnings: list[tuple[tuple, str]] = []
    # Defaults for if/when parameters for alpha/beta are both zero
    k = 10_000
    default_alpha = 0.02 * k  # 200
    default_beta = 0.98 * k  # 9800
    print(f'\nNow Executing Clarke Model Based on Quantities')
    for (lower, upper), inputs in inputs_by_quantity.items():
        print(f'   Calculating for Quantity Range:  {(lower, upper)}')
        params = run_clarke_bb_group_model(
            inputs.ty,
            inputs.b,
            inputs.B,
            inputs.Nbar,
            inputs.freq,
            inputs.theta,
            inputs.R,
            inputs.start_val,
            inputs.se,
        )

        alpha = params.get("alpha", 0)
        beta = params.get("beta", 0)

        if alpha == 0 and beta == 0:
            # Create a warning message
            warning_msg = (
                f"Fitted alpha and beta were zero for quantity range {(lower, upper)}; "
                f"values displayed above are defaults "
                f"for a mean rate ≈ 0.02 and 95% CI = [0.0175,0.0229]."
            )
            warnings.append(((lower, upper), warning_msg))

            # override
            params["alpha"] = default_alpha
            params["beta"] = default_beta

        res[(lower, upper)] = params

    return res, pis_df, inputs_by_quantity, warnings



def run_slippage_pipeline(
    exp_paths: ExperimentPaths,
    *,
    seed: int = 42,
    num_simulations: int = 1,
    progress_callback: Optional[Callable[[int, str], None]] = None,
) -> PipelineResult:
    """Execute the end-to-end slippage simulation pipeline for an experiment.

    The pipeline:

    * Loads scenarios and base configuration.
    * Resolves consignment and compliance-table inputs.
    * Normalizes contamination and inspection settings per scenario.
    * Runs :func:`popsborder.scenarios.run_scenarios` for each scenario,
      with optional retries for specific numerical issues.
    * Aggregates scenario-level and replication-level outputs.
    * Writes scenario and all-run results to the experiment output folder.

    Args:
        exp_paths: ExperimentPaths specifying the experiment directory and
            input files to use.
        seed: Base random seed controlling scenario RNGs.
        num_simulations: Number of simulation replications per scenario.
        progress_callback: Optional callback invoked with progress updates;
            should accept ``(percent, message, details_dict)``.

    Returns:
        PipelineResult capturing fitted contamination parameters, scenario
        results, configuration, compliance policy, and output file paths.

    Raises:
        FileNotFoundError: If required inputs (consignment, config, compliance)
            are missing.
        ValueError: If scenario tables are empty or no results can be
            generated.
    """

    def _report_progress(percent: int, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        if progress_callback is None:
            return
        progress_callback(max(0, min(100, int(percent))), message, details or {})

    experiment_dir = exp_paths.experiment_dir
    scenario_table = exp_paths.scenario_table
    config_path = exp_paths.config or (DEFAULT_DATA_DIR / CONFIG_FILENAME)

    # --- Load scenarios ---
    _report_progress(5, "Loading scenario table")
    scenarios = load_scenario_dataframe(scenario_table)
    if isinstance(scenarios, pd.DataFrame):
        scenarios = scenarios.to_dict(orient="records")
    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError("Scenario table is empty or unreadable.")

    # --- Small helpers ---
    def _is_missing(v: Any) -> bool:
        return v in (None, "", "None", "nan")

    def _maybe_path(v: Any) -> Optional[Path]:
        return None if _is_missing(v) else Path(str(v))

    def _in_exp_dir(p: Path) -> Path:
        # If given a relative path or a missing path, prefer experiment_dir/<filename>
        if p.is_absolute():
            return p
        if p.exists():
            return p
        return experiment_dir / p.name

    def _first_existing_path(values: List[Optional[Path]]) -> Optional[Path]:
        for p in values:
            if p and Path(p).exists():
                return Path(p)
        return None

    def _scenario_path(rec: Dict[str, Any], key: str) -> Optional[Path]:
        p = _maybe_path(rec.get(key))
        return _in_exp_dir(p) if p else None

    def _apply_contam_defaults(rec: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
        rec = rec.copy()
        base = cfg.get("contamination", {}).get("contamination_rate", {})
        if _is_missing(rec.get("contamination/contamination_rate/distribution")):
            rec["contamination/contamination_rate/distribution"] = base.get("distribution", "beta_binomial")

        bb_defaults = base.get("beta_binomial_parameters", {}).get("default", {})
        for key in ("alpha", "beta", "theta", "N_bar", "I", "J", "p"):
            col = f"contamination/contamination_rate/beta_binomial_parameters/default/{key}"
            if _is_missing(rec.get(col)):
                rec[col] = bb_defaults.get(key)
        return rec

    def _normalize_inspection(rec: Dict[str, Any]) -> Dict[str, Any]:
        rec = rec.copy()
        try:
            prop = float(rec.get("inspection/proportion/value", 0) or 0)
        except Exception:
            prop = 0.0
        if prop <= 0:
            prop = 0.02
        rec["inspection/proportion/value"] = min(prop, 1.0)
        rec.setdefault("inspection/sample_strategy", "rbs")
        return rec

    def _build_cfg_for_scenario(
        base_cfg: Dict[str, Any],
        cons_path: Optional[Path],
        comp_path: Optional[Path],
    ) -> Dict[str, Any]:
        cfg = copy.deepcopy(base_cfg)

        if cons_path and cons_path.exists():
            cons_str = str(cons_path).replace("\\", "/")
            cfg.setdefault("consignment", {}).setdefault("input_file", {})
            cfg["consignment"]["input_file"]["rbs_file_name"] = cons_str
            cfg["consignment"]["input_file"]["file_name"] = cons_str

        if comp_path and comp_path.exists():
            comp_str = str(comp_path).replace("\\", "/")
            cfg.setdefault("inspection", {}).setdefault("compliance_table", {})
            cfg["inspection"]["compliance_table"]["file_name"] = comp_str

        return cfg

    # --- Resolve base files (consignment / compliance / config) ---
    # Candidate consignment paths: explicit, plus any scenario references that exist
    _report_progress(15, "Resolving experiment inputs")
    cons_candidates: List[Path] = []
    if exp_paths.consignment and exp_paths.consignment.exists():
        cons_candidates.append(exp_paths.consignment)

    for rec in scenarios:
        p = _scenario_path(rec, "consignment/input_file/file_name")
        if p and p.exists():
            cons_candidates.append(p)

    cons_path = _first_existing_path(cons_candidates)
    if not cons_path:
        raise FileNotFoundError(f"Consignment file missing in experiment folder {experiment_dir}.")

    # Compliance: explicit, else first scenario reference, else default dir fallback (must exist)
    comp_path = None
    if exp_paths.compliance and exp_paths.compliance.exists():
        comp_path = exp_paths.compliance
    else:
        for rec in scenarios:
            p = _scenario_path(rec, "inspection/compliance_table/file_name")
            if p and p.exists():
                comp_path = p
                break

    if not config_path or not Path(config_path).exists():
        raise FileNotFoundError(
            f"Config file missing in experiment folder {experiment_dir} (expected {CONFIG_FILENAME})."
        )
    config = load_configuration(config_path)

    comp_lookup_path = comp_path if (comp_path and comp_path.exists()) else (DEFAULT_DATA_DIR / COMPLIANCE_FILENAME)
    if not comp_lookup_path.exists():
        raise FileNotFoundError(
            f"Compliance table not found for experiment {experiment_dir}. Expected {COMPLIANCE_FILENAME}."
        )

    compliance_table = load_compliance_policy(comp_lookup_path)

    # Ensure base config points to base consignment/compliance (scenario overrides still apply later)
    config = copy.deepcopy(config)
    config.setdefault("consignment", {}).setdefault("input_file", {})
    config["consignment"]["input_file"]["rbs_file_name"] = str(cons_path).replace("\\", "/")
    config["consignment"]["input_file"]["file_name"] = str(cons_path).replace("\\", "/")
    config.setdefault("inspection", {}).setdefault("compliance_table", {})
    config["inspection"]["compliance_table"]["file_name"] = str(comp_lookup_path).replace("\\", "/")

    # Estimate consignments conservatively across unique consignment files
    unique_cons_files = list({str(Path(p)): p for p in cons_candidates}.values())
    counts = [_infer_num_consignments(p) for p in unique_cons_files] if unique_cons_files else []
    num_consignments_default = min(counts) if counts else 1
    planned_consignment_counts = []
    for rec in scenarios:
        rec_cons_path = _scenario_path(rec, "consignment/input_file/file_name")
        planned_consignment_counts.append(_infer_num_consignments(rec_cons_path) if rec_cons_path else 1)
    total_planned_shipments = max(sum(planned_consignment_counts) * max(num_simulations, 1), 1)
    total_planned_replications = max(len(scenarios) * max(num_simulations, 1), 1)

    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = experiment_dir / f"output_{run_timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    _report_progress(25, "Prepared output directory")

    def _run(
        cfg: Dict[str, Any],
        rec: Dict[str, Any],
        cons_count: int,
        *,
        num_sims: int,
        comp_table: Dict[str, Any],
        seed_override: Optional[int] = None,
        progress_update=None,
    ):
        return run_scenarios(
            config=cfg,
            scenario_table=[rec],
            seed=seed if seed_override is None else seed_override,
            num_simulations=num_sims,
            num_consignments=cons_count,
            compliance_table=comp_table,
            detailed=True,
            output_root=output_dir,
            progress_callback=progress_update,
        )

    # --- Core executor (supports a single retry config) ---
    skipped_scenarios: List[str] = []

    def _execute_all(base_cfg: Dict[str, Any]) -> Tuple[List[Tuple[Any, Dict, Dict]], List[int]]:
        """Internal helper to run all scenarios with a given base config."""
        scenario_results_raw: List[Tuple[Any, Dict, Dict]] = []
        consignment_counts: List[int] = []
        total_scenarios = len(scenarios)

        for scenario_idx, rec0 in enumerate(scenarios, start=1):
            scenario_name = str(rec0.get("name", f"Scenario {scenario_idx}"))
            progress_start = 25 + int(((scenario_idx - 1) / max(total_scenarios, 1)) * 60)
            _report_progress(progress_start, f"Running {scenario_name} ({scenario_idx}/{total_scenarios})")
            rec = _normalize_inspection(_apply_contam_defaults(rec0, base_cfg))

            rec_cons_path = _scenario_path(rec, "consignment/input_file/file_name")
            rec_comp_path = _scenario_path(rec, "inspection/compliance_table/file_name")
            rec_num_consignments = _infer_num_consignments(rec_cons_path) if rec_cons_path else 1
            consignment_counts.append(rec_num_consignments)
            shipments_before_scenario = sum(planned_consignment_counts[: scenario_idx - 1]) * max(num_simulations, 1)

            cfg_local = _build_cfg_for_scenario(base_cfg, rec_cons_path, rec_comp_path)
            comp_table = load_compliance_policy(rec_comp_path) if rec_comp_path else compliance_table

            def _scenario_progress(replication_current: int, replications_total: int, shipments_processed: int, shipments_total: int) -> None:
                global_replication_current = (
                    (scenario_idx - 1) * max(num_simulations, 1) + replication_current
                )
                global_shipments_processed = shipments_before_scenario + (
                    max(replication_current - 1, 0) * rec_num_consignments
                ) + shipments_processed
                percent = 25 + int((global_shipments_processed / total_planned_shipments) * 60)
                _report_progress(
                    percent,
                    f"Running {scenario_name} ({scenario_idx}/{total_scenarios})",
                    {
                        "replications_completed": global_replication_current,
                        "replications_total": total_planned_replications,
                        "shipments_processed": min(global_shipments_processed, total_planned_shipments),
                        "shipments_total": total_planned_shipments,
                        "scenario_name": scenario_name,
                    },
                )

            # Aggregated run
            last_exc: Optional[Exception] = None
            for retry_idx in range(10):
                try:
                    scenario_results_raw.extend(
                        _run(
                            cfg_local,
                            rec,
                            rec_num_consignments,
                            num_sims=num_simulations,
                            comp_table=comp_table,
                            seed_override=seed + retry_idx if seed is not None else None,
                            progress_update=_scenario_progress,
                        )
                    )
                    last_exc = None
                    progress_end = 25 + int((scenario_idx / max(total_scenarios, 1)) * 60)
                    _report_progress(
                        progress_end,
                        f"Completed {scenario_name} ({scenario_idx}/{total_scenarios})",
                        {
                            "replications_completed": scenario_idx * max(num_simulations, 1),
                            "replications_total": total_planned_replications,
                            "shipments_processed": min(
                                shipments_before_scenario + (rec_num_consignments * max(num_simulations, 1)),
                                total_planned_shipments,
                            ),
                            "shipments_total": total_planned_shipments,
                            "scenario_name": scenario_name,
                        },
                    )
                    break
                except ValueError as exc:
                    if "a <= 0" not in str(exc):
                        raise
                    last_exc = exc
                    continue
            if last_exc is not None:
                skipped_scenarios.append(str(rec.get("name", f"scenario_{len(skipped_scenarios) + 1}")))
                continue
        return scenario_results_raw, consignment_counts

    # --- Run with one retry path for "Sample larger than population" ---
    try:
        scenario_results_raw, consignment_counts = _execute_all(config)
    except ValueError as exc:
        if "Sample larger than population" not in str(exc):
            raise

        cfg_retry = copy.deepcopy(config)
        cfg_retry.setdefault("inspection", {}).setdefault("proportion", {})
        current_prop = cfg_retry["inspection"]["proportion"].get("value", 0.02) or 0.02
        cfg_retry["inspection"]["proportion"]["value"] = min(float(current_prop), 0.001)
        cfg_retry["inspection"]["min_inspection_units"] = 0

        scenario_results_raw, consignment_counts = _execute_all(cfg_retry)
    except ZeroDivisionError as exc:
        raise ValueError(
            "Division by zero during scenario run. Check inspection proportion, sampling units, and config values."
        ) from exc
    except StopIteration as exc:
        raise ValueError(
            "Scenario execution failed: no valid consignments were generated. "
            "Ensure the consignment file has valid inspection identifiers."
        ) from exc

    # --- Convert results and write outputs ---
    if not scenario_results_raw:
        if skipped_scenarios:
            raise ValueError(
                "All scenarios were skipped after repeated 'a <= 0' contamination errors: "
                + ", ".join(skipped_scenarios)
            )
        raise ValueError("No scenario results were generated.")

    _report_progress(
        90,
        "Building results tables",
        {
            "replications_completed": total_planned_replications,
            "replications_total": total_planned_replications,
            "shipments_processed": total_planned_shipments,
            "shipments_total": total_planned_shipments,
        },
    )
    scenario_results = [(result, cfg) for _details, result, cfg in scenario_results_raw]

    results_df = save_scenario_result_to_pandas(
        scenario_results,
        config_columns=CONFIG_COLUMNS,
        result_columns=RESULT_COLUMNS,
    )

    results_output_path = output_dir / "pis_contamination_scenario_results.csv"
    results_df.to_csv(results_output_path, index=False)
    if skipped_scenarios:
        skipped_path = output_dir / "skipped_scenarios.txt"
        skipped_path.write_text(
            "Skipped after repeated 'a <= 0' errors:\n" + "\n".join(skipped_scenarios),
            encoding="utf-8",
        )

    # Per-replication output
    output_files: List[Path] = [results_output_path]
    if skipped_scenarios:
        output_files.append(skipped_path)
    runs_records: List[Dict[str, Any]] = []
    for _details, result, cfg in scenario_results_raw:
        rep_df = getattr(result, "replication_outputs", None)
        if rep_df is None or getattr(rep_df, "empty", True):
            continue
        rep_records = rep_df.copy()
        if isinstance(cfg, dict) and "name" in cfg:
            rep_records["name"] = cfg.get("name")
        runs_records.extend(rep_records.to_dict(orient="records"))
    if runs_records:
        all_runs_output_path = output_dir / "all_runs.csv"
        pd.DataFrame(runs_records).to_csv(all_runs_output_path, index=False)
        output_files.append(all_runs_output_path)

    _report_progress(
        100,
        "Simulation complete",
        {
            "replications_completed": total_planned_replications,
            "replications_total": total_planned_replications,
            "shipments_processed": total_planned_shipments,
            "shipments_total": total_planned_shipments,
        },
    )
    fit = ClarkeFit(alpha=0.0, beta=0.0, theta=float("inf"), raw_result={"source": "scenario_table"})
    total_cons = sum(consignment_counts) if consignment_counts else num_consignments_default

    return PipelineResult(
        contamination_fit=fit,
        scenario_results=results_df,
        config=config,
        compliance_table=compliance_table,
        pis_data=pd.DataFrame(),
        rbs_data=pd.DataFrame(),
        num_consignments=total_cons,
        output_dir=output_dir,
        output_files=output_files,
    )


__all__ = [
    "SlippagePaths",
    "ExperimentPaths",
    "ClarkeFit",
    "PipelineResult",
    "create_default_paths",
    "load_scenario_dataframe",
    "generate_synthetic_data",
    "fit_contamination_distribution",
    "run_slippage_pipeline",
    "SyntheticOptions",
]
