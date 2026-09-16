# © 2026 The Johns Hopkins University Applied Physics Laboratory LLC

import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Dict, Union
from datetime import datetime
import warnings
import re
from slippage_model_utils.paths import DefaultPaths
from scipy import stats


def find_latest_simulation_base_path(output_dir: Path, base_name: str = "pops_border_scenario_data") -> Path:
    """Find the most recent simulation base directory by timestamp in its name.

    Directory names are expected to follow the pattern
    ``f"{base_name}_MM_DD_YYYY_HH_MM_SS"``. The function scans all matching
    directories under ``output_dir``, parses their timestamps, and returns
    the newest one.

    Args:
        output_dir: Main output directory containing simulation run subdirs.
        base_name: Base name prefix for simulation directories.

    Returns:
        Path to the most recent simulation base directory.

    Raises:
        FileNotFoundError: If no matching simulation directories are found.
    """
    # Pattern to match simulation directories with timestamp
    pattern = re.compile(rf"{base_name}_(\d{{2}})_(\d{{2}})_(\d{{4}})_(\d{{2}})_(\d{{2}})_(\d{{2}})")

    simulation_dirs = []

    # Find all matching directories
    for item in output_dir.iterdir():
        if item.is_dir():
            match = pattern.match(item.name)
            if match:
                # Extract timestamp components: month, day, year, hour, minute, second
                month, day, year, hour, minute, second = match.groups()

                # Create datetime object for comparison
                try:
                    timestamp = datetime(
                        int(year), int(month), int(day),
                        int(hour), int(minute), int(second)
                    )
                    simulation_dirs.append((timestamp, item))
                except ValueError as e:
                    warnings.warn(f"Invalid timestamp in directory name {item.name}: {e}")

    if not simulation_dirs:
        raise FileNotFoundError(f"No simulation directories found matching pattern '{base_name}_*' in {output_dir}")

    # Sort by timestamp and return the most recent
    simulation_dirs.sort(key=lambda x: x[0], reverse=True)
    latest_dir = simulation_dirs[0][1]

    print(f"Found {len(simulation_dirs)} simulation run(s)")
    print(f"Selected most recent: {latest_dir.name}")

    return latest_dir


def get_simulation_base_path(
    simulation_output_path: Union[str, Path],
    simulation_base_path: Union[str, Path] = "latest",
) -> Path:
    """Resolve the base path for a simulation run.

    This helper either:

    * Returns the most recent simulation run under ``simulation_output_path``
      if ``simulation_base_path`` is ``"latest"``.
    * Returns the specified subdirectory under ``simulation_output_path``.

    Args:
        simulation_output_path: Main output directory path (usually ``output``).
        simulation_base_path: Either ``"latest"`` or an explicit directory
            name (or Path) under ``simulation_output_path``.

    Returns:
        Full path to the selected simulation base directory.

    Raises:
        FileNotFoundError: If the output directory or specified base path
            does not exist.
    """
    output_dir = Path(simulation_output_path)

    if not output_dir.exists():
        raise FileNotFoundError(f"Output directory does not exist: {output_dir}")

    if isinstance(simulation_base_path, str) and simulation_base_path.lower() == "latest":
        return find_latest_simulation_base_path(output_dir)
    else:
        # Use specified directory
        base_path = output_dir / simulation_base_path
        if not base_path.exists():
            raise FileNotFoundError(f"Simulation base path does not exist: {base_path}")
        return base_path


def calculate_action_rates_by_scenario(
        ground_truth_path: str | Path,
        simulation_output_path: str | Path,
        scenarios: List[str],
        num_replications: int,
        filter_fields: List[str] = None,
        simulation_base_path: str = "latest",
        output_file: str = "synthetic_commodity_line_results_data.csv",
        practical_equivalence_threshold: float = 0.005
) -> Dict[str, pd.DataFrame]:
    """Calculate and compare action rates by scenario between simulation and ground truth.

    For each scenario and replication, this function:

    * Loads the simulation output file.
    * Computes the action rate (mean of the ``action`` column).
    * Compares the distribution of simulated action rates to the ground truth
      action rate using:
      - One-sample t-test,
      - Proportion z-test,
      - Exact binomial test,
      - Practical equivalence (absolute difference threshold).

    If ``filter_fields`` are provided, calculations are performed for each
    unique combination of those fields; otherwise the comparison is done
    at the overall level.

    Args:
        ground_truth_path: Path to the ground truth CSV file.
        simulation_output_path: Root directory where scenario outputs are stored.
        scenarios: List of scenario names (subdirectories under the base path).
        num_replications: Number of replications per scenario.
        filter_fields: List of column names from the ground truth to use for
            stratified filtering; if None or empty, overall rates are used.
        simulation_base_path: Either ``"latest"`` or a specific run directory
            name under ``simulation_output_path``.
        output_file: Name of the simulation result file containing ``action``
            (default: ``'synthetic_commodity_line_results_data.csv'``).
        practical_equivalence_threshold: Maximum absolute difference in action
            rates to consider them practically equivalent.

    Returns:
        Dictionary mapping scenario name to a DataFrame of per-scenario
        (and per-filter-combination) statistics, including:

        * Ground-truth and mean simulation action rates,
        * t-test/proportion/binomial test results,
        * practical equivalence indicators,
        * per-replication action rates.
    """
    # Get the actual simulation base path
    base_path = get_simulation_base_path(simulation_output_path, simulation_base_path)
    print(f"\nUsing simulation base path: {base_path}")

    # Load ground truth data
    print(f"Loading ground truth data from {ground_truth_path}")
    ground_truth = pd.read_csv(ground_truth_path)

    # Convert all column names to lowercase
    ground_truth.columns = ground_truth.columns.str.lower()

    results = {}

    if len(filter_fields) == 0 or filter_fields is None:
        print(f'Generating summary of action rates of overall data')
        for scenario in scenarios:
            scenario_results = []

            gt_action_rate = ground_truth['action'].mean()

            unique_inspections = ground_truth['inspection_number'].unique()

            replication_action_rates = []
            trials_per_replication = []

            prop = 0
            increment = 0.25
            # Process each replication
            for rep in range(num_replications):
                if rep == int(prop * num_replications):
                    print(
                        f'      Analyzing simulation replications {prop * 100}% complete ({rep} out of {num_replications})')
                    prop += increment

                sim_file_path = base_path / scenario / f"rep_{rep}" / output_file
                sim_data = pd.read_csv(sim_file_path)
                replication_action_rates.append(sim_data['action'].mean())
                trials_per_replication.append(sim_data.shape[0])

            # Calculate statistics across replications
            valid_rates = [r for r in replication_action_rates if not np.isnan(r)]

            # Perform two-sided t-test if we have valid rates
            if len(valid_rates) > 1:
                # Calculate mean and std
                mean_rate = np.mean(valid_rates)
                std_rate = np.std(valid_rates, ddof=1)  # Use sample std deviation

                # Initialize all proportion/binomial test results to nan
                # (will be populated if data is suitable for these tests)
                prop_z_statistically_same = np.nan
                prop_z_p_value = np.nan
                binomial_statistically_same = np.nan
                binomial_p_value = np.nan

                # Check if rates are essentially identical (no variance)
                if std_rate < 1e-10:  # Very small threshold for numerical stability
                    # If all replications are the same, check if they match ground truth
                    if abs(mean_rate - gt_action_rate) < 1e-10:
                        statistically_same = 1
                        p_value = 1.0  # Perfect match, maximum p-value
                    else:
                        statistically_same = 0
                        p_value = 0.0  # Clear difference, minimum p-value
                else:
                    # Normal t-test when there is variance
                    t_statistic, p_value = stats.ttest_1samp(valid_rates, gt_action_rate)
                    # If p-value > 0.05, we fail to reject null (they are statistically the same)
                    statistically_same = 1 if p_value > 0.05 else 0

                # Also check practical equivalence (e.g., within a small absolute difference)
                absolute_diff = abs(mean_rate - gt_action_rate)

                # Consider practically equivalent if within threshold
                practically_equivalent = 1 if (absolute_diff < practical_equivalence_threshold) else 0

                # ============================================
                # APPROACH 2: BINOMIAL/PROPORTION TEST (for rate/proportion data)
                # ============================================

                # Determine if we should use binomial approach based on data
                is_proportion_data = all(0 <= rate <= 1 for rate in valid_rates)

                if is_proportion_data:
                    # METHOD 2A: One-sample proportion test (z-test for proportions)
                    pooled_prop = mean_rate
                    expected_prop = gt_action_rate

                    # Standard error for proportion
                    se_prop = np.sqrt(expected_prop * (1 - expected_prop) / ground_truth.shape[0])

                    if se_prop < 1e-10:
                        if abs(pooled_prop - expected_prop) < 1e-10:
                            prop_z_statistically_same = 1
                            prop_z_p_value = 1.0
                        else:
                            prop_z_statistically_same = 0
                            prop_z_p_value = 0.0
                    else:
                        # Z-statistic for proportion test
                        z_statistic = (pooled_prop - expected_prop) / se_prop
                        # Two-sided p-value
                        prop_z_p_value = 2 * (1 - stats.norm.cdf(abs(z_statistic)))
                        prop_z_statistically_same = 1 if prop_z_p_value > 0.05 else 0

                    # METHOD 2B: Exact binomial test
                    total_successes = sum(rate * n_trials for rate, n_trials
                                         in zip(valid_rates, trials_per_replication))
                    total_trials = sum(trials_per_replication)

                    binomial_result = stats.binomtest(
                        k=int(round(total_successes)),
                        n=total_trials,
                        p=gt_action_rate,
                        alternative='two-sided'
                    )

                    binomial_p_value = binomial_result.pvalue
                    binomial_statistically_same = 1 if binomial_p_value > 0.05 else 0

            elif len(valid_rates) == 1:
                # Can't perform statistical tests with only one observation
                single_rate = valid_rates[0]

                # Check absolute difference
                absolute_diff = abs(single_rate - gt_action_rate)

                # For single observation, we can only assess practical equivalence
                practically_equivalent = 1 if (absolute_diff < practical_equivalence_threshold) else 0

                # No statistical tests possible with n=1
                statistically_same = np.nan  # Insufficient data for reliable test
                p_value = np.nan

                # Proportion tests also not possible with n=1
                prop_z_statistically_same = np.nan
                prop_z_p_value = np.nan
                binomial_statistically_same = np.nan
                binomial_p_value = np.nan
            else:
                # No valid rates
                statistically_same = np.nan
                p_value = np.nan
                practically_equivalent = np.nan
                absolute_diff = np.nan
                prop_z_statistically_same = np.nan
                prop_z_p_value = np.nan
                binomial_statistically_same = np.nan
                binomial_p_value = np.nan

            result_row = {
                'ground_truth_action_rate': gt_action_rate,
                'mean_simulation_action_rate': np.mean(valid_rates) if valid_rates else np.nan,
                'std_simulation_action_rate': np.std(valid_rates) if valid_rates else np.nan,
                'num_inspection_numbers': len(unique_inspections),
                'num_valid_replications': len(valid_rates),
                'simulation_action_rate_statistically_same_as_ground_truth': statistically_same,
                'p_value': p_value,
                'practically_equivalent': practically_equivalent,
                'practical_threshold': practical_equivalence_threshold,
                'action_rate_abs_diff': absolute_diff,
                'prop_z_statistically_same': prop_z_statistically_same,
                'prop_z_p_value': prop_z_p_value,
                'binomial_statistically_same': binomial_statistically_same,
                'binomial_p_value': binomial_p_value
            }

            # Add individual replication rates
            for rep_idx, rate in enumerate(replication_action_rates):
                result_row[f'rep_{rep_idx}_action_rate'] = rate

            scenario_results.append(result_row)

            # Convert to DataFrame
            results[scenario] = pd.DataFrame(scenario_results)
            print(f"Completed {scenario}: {len(scenario_results)} filter combinations processed")
    else:
        # Convert filter_fields to lowercase for consistency
        filter_fields_lower = [field.lower() for field in filter_fields]

        # Validate required columns
        required_cols = ['inspection_number', 'action'] + filter_fields_lower
        missing_cols = [col for col in required_cols if col not in ground_truth.columns]
        if missing_cols:
            raise ValueError(f"Missing columns in ground truth: {missing_cols}")

        # Get unique combinations of filter fields and their inspection numbers
        print(f"Creating filter combinations based on: {filter_fields_lower}")
        filter_combinations = ground_truth[filter_fields_lower + ['inspection_number', 'action']].copy()

        # Group by filter fields to get unique combinations
        grouped = filter_combinations.groupby(filter_fields_lower)

        for scenario in scenarios:
            scenario_results = []

            combo_count = 1
            for combination_values, group_data in grouped:
                print(f'   \nCombination {combination_values} being analyzed ({combo_count} of {len(grouped)})...')
                combo_count+=1

                if len(filter_fields_lower) == 1:
                    value = combination_values[0] if isinstance(combination_values,
                                                                (tuple, list)) else combination_values
                    combination_dict = {filter_fields_lower[0]: value}
                else:
                    combination_dict = dict(zip(filter_fields_lower, combination_values))

                combination_items = list(combination_dict.items())

                # Get unique inspection numbers for this combination
                unique_inspections = group_data['inspection_number'].unique()

                # For each inspection_number, calculate its action rate
                inspection_action_rates = group_data.groupby('inspection_number')['action'].mean()

                # Average across all calculated rates
                gt_action_rate = inspection_action_rates.mean()

                # Initialize list to store action rates from each replication
                replication_action_rates = []
                trials_per_replication = []

                unique_inspections_set = set(unique_inspections)
                combination_items = list(combination_dict.items())

                prop = 0
                increment = 0.25
                # Process each replication
                for rep in range(num_replications):
                    if rep == int(prop * num_replications):
                        print(
                            f'      Analyzing simulation replications {prop * 100}% complete ({rep} out of {num_replications})')
                        prop += increment
                    sim_file_path = base_path / scenario / f"rep_{rep}" / output_file
                    pis_file_path = base_path / scenario / f"rep_{rep}" / 'synthetic_pis_data.csv'

                    try:
                        # Load simulation data
                        sim_data = pd.read_csv(sim_file_path)
                        sim_pis_data = pd.read_csv(pis_file_path)
                        sim_pis_data.columns = sim_pis_data.columns.str.lower()

                        # Filter before merging
                        sim_subset = sim_data[sim_data['inspection_number'].isin(unique_inspections_set)]
                        sim_pis_subset = sim_pis_data[sim_pis_data['inspection_number'].isin(unique_inspections_set)]

                        # Early exit if no matching data
                        if len(sim_subset) == 0 or len(sim_pis_subset) == 0:
                            warnings.warn(f"No matching inspections in rep {rep}")
                            replication_action_rates.append(np.nan)
                            trials_per_replication.append(np.nan)
                            continue

                        # Merge filtered data
                        merged = sim_subset.merge(
                            sim_pis_subset,
                            left_on='risk_unit_id',
                            right_on='risk_unit',
                            how='inner',
                            suffixes=('', '_drop')
                        )

                        # Drop columns with _drop suffix
                        drop_cols = [col for col in merged.columns if col.endswith('_drop')]
                        if drop_cols:
                            merged.drop(columns=drop_cols, inplace=True)

                        # Rename _x columns
                        x_cols = [col for col in merged.columns if col.endswith('_x')]
                        if x_cols:
                            merged.rename(columns={col: col[:-2] for col in x_cols}, inplace=True)

                        # Deduplicate
                        merged_unique = merged.drop_duplicates(subset=['risk_unit_id', 'comm_id'])

                        if 'action' not in merged_unique.columns:
                            warnings.warn(f"Missing 'action' column in rep {rep}")
                            replication_action_rates.append(np.nan)
                            trials_per_replication.append(np.nan)
                            continue

                        if len(merged_unique) != len(sim_subset):
                            warnings.warn(f"Row mismatch in rep {rep}: {len(merged_unique)} vs {len(sim_subset)}")

                        # Filter to the combination desired
                        filtered_data = merged_unique
                        for col, val in combination_items:
                            if col in filtered_data.columns:
                                filtered_data = filtered_data[filtered_data[col] == val]
                                if len(filtered_data) == 0:
                                    break

                        # Calculate action data
                        if len(filtered_data) > 0:
                            rep_action_rate = filtered_data['action'].mean()
                            replication_action_rates.append(rep_action_rate)
                            trials_per_replication.append(filtered_data.shape[0])
                        else:
                            warnings.warn(f"No data matching combination in rep {rep}")
                            replication_action_rates.append(np.nan)
                            trials_per_replication.append(np.nan)

                    except FileNotFoundError:
                        warnings.warn(f"File not found: {sim_file_path}")
                        replication_action_rates.append(np.nan)
                    except Exception as e:
                        warnings.warn(f"Error in rep {rep}: {str(e)}")
                        replication_action_rates.append(np.nan)

                # Calculate statistics across replications
                valid_rates = [r for r in replication_action_rates if not np.isnan(r)]

                # Perform two-sided t-test if we have valid rates
                if len(valid_rates) > 1:
                    mean_rate = np.mean(valid_rates)
                    std_rate = np.std(valid_rates, ddof=1)

                    prop_z_statistically_same = np.nan
                    prop_z_p_value = np.nan
                    binomial_statistically_same = np.nan
                    binomial_p_value = np.nan

                    if std_rate < 1e-10:
                        if abs(mean_rate - gt_action_rate) < 1e-10:
                            statistically_same = 1
                            p_value = 1.0
                        else:
                            statistically_same = 0
                            p_value = 0.0
                    else:
                        t_statistic, p_value = stats.ttest_1samp(valid_rates, gt_action_rate)
                        statistically_same = 1 if p_value > 0.05 else 0

                    absolute_diff = abs(mean_rate - gt_action_rate)
                    practically_equivalent = 1 if (absolute_diff < practical_equivalence_threshold) else 0

                    is_proportion_data = all(0 <= rate <= 1 for rate in valid_rates)

                    if is_proportion_data:
                        pooled_prop = mean_rate
                        expected_prop = gt_action_rate

                        se_prop = np.sqrt(expected_prop * (1 - expected_prop) / ground_truth.shape[0])

                        if se_prop < 1e-10:
                            if abs(pooled_prop - expected_prop) < 1e-10:
                                prop_z_statistically_same = 1
                                prop_z_p_value = 1.0
                            else:
                                prop_z_statistically_same = 0
                                prop_z_p_value = 0.0
                        else:
                            z_statistic = (pooled_prop - expected_prop) / se_prop
                            prop_z_p_value = 2 * (1 - stats.norm.cdf(abs(z_statistic)))
                            prop_z_statistically_same = 1 if prop_z_p_value > 0.05 else 0

                        total_successes = sum(rate * n_trials for rate, n_trials
                                              in zip(valid_rates, trials_per_replication))
                        total_trials = sum(trials_per_replication)

                        binomial_result = stats.binomtest(
                            k=int(round(total_successes)),
                            n=total_trials,
                            p=gt_action_rate,
                            alternative='two-sided'
                        )

                        binomial_p_value = binomial_result.pvalue
                        binomial_statistically_same = 1 if binomial_p_value > 0.05 else 0

                elif len(valid_rates) == 1:
                    single_rate = valid_rates[0]
                    absolute_diff = abs(single_rate - gt_action_rate)
                    practically_equivalent = 1 if (absolute_diff < practical_equivalence_threshold) else 0
                    statistically_same = np.nan
                    p_value = np.nan
                    prop_z_statistically_same = np.nan
                    prop_z_p_value = np.nan
                    binomial_statistically_same = np.nan
                    binomial_p_value = np.nan
                else:
                    statistically_same = np.nan
                    p_value = np.nan
                    practically_equivalent = np.nan
                    absolute_diff = np.nan
                    prop_z_statistically_same = np.nan
                    prop_z_p_value = np.nan
                    binomial_statistically_same = np.nan
                    binomial_p_value = np.nan

                result_row = {
                    **combination_dict,
                    'ground_truth_action_rate': gt_action_rate,
                    'mean_simulation_action_rate': np.mean(valid_rates) if valid_rates else np.nan,
                    'std_simulation_action_rate': np.std(valid_rates) if valid_rates else np.nan,
                    'num_inspection_numbers': len(unique_inspections),
                    'num_valid_replications': len(valid_rates),
                    'simulation_action_rate_statistically_same_as_ground_truth': statistically_same,
                    'p_value': p_value,
                    'practically_equivalent': practically_equivalent,
                    'practical_threshold': practical_equivalence_threshold,
                    'action_rate_abs_diff': absolute_diff,
                    'prop_z_statistically_same': prop_z_statistically_same,
                    'prop_z_p_value': prop_z_p_value,
                    'binomial_statistically_same': binomial_statistically_same,
                    'binomial_p_value': binomial_p_value
                }

                # Add individual replication rates
                for rep_idx, rate in enumerate(replication_action_rates):
                    result_row[f'rep_{rep_idx}_action_rate'] = rate

                scenario_results.append(result_row)

            # Convert to DataFrame
            results[scenario] = pd.DataFrame(scenario_results)
            print(f"Completed {scenario}: {len(scenario_results)} filter combinations processed")

    return results


def list_available_simulation_runs(
        simulation_output_path: str | Path,
        base_name: str = "pops_border_scenario_data"
) -> List[Dict[str, Union[str, datetime]]]:
    """List all available simulation runs in the output directory.

    Simulation run directories are identified using the same naming pattern
    as :func:`find_latest_simulation_base_path`.

    Args:
        simulation_output_path: Main output directory.
        base_name: Base directory name prefix for simulation runs.

    Returns:
        List of dictionaries, one per run, each containing:
        * ``'name'``: directory name,
        * ``'timestamp'``: parsed datetime,
        * ``'path'``: Path object.
    """
    output_dir = Path(simulation_output_path)
    pattern = re.compile(rf"{base_name}_(\d{{2}})_(\d{{2}})_(\d{{4}})_(\d{{2}})_(\d{{2}})_(\d{{2}})")

    runs = []

    for item in output_dir.iterdir():
        if item.is_dir():
            match = pattern.match(item.name)
            if match:
                month, day, year, hour, minute, second = match.groups()
                try:
                    timestamp = datetime(
                        int(year), int(month), int(day),
                        int(hour), int(minute), int(second)
                    )
                    runs.append({
                        'name': item.name,
                        'timestamp': timestamp,
                        'path': item
                    })
                except ValueError:
                    pass

    # Sort by timestamp (most recent first)
    runs.sort(key=lambda x: x['timestamp'], reverse=True)

    return runs


def save_results(results: Dict[str, pd.DataFrame], output_dir: Union[str, Path]) -> None:
    """Save scenario-wise analysis results to CSV files.

    Each scenario's results are written to
    ``<output_dir>/<scenario>_action_rates_validation.csv``.

    Args:
        results: Dictionary from scenario name to analysis DataFrame as
            returned by :func:`calculate_action_rates_by_scenario`.
        output_dir: Output directory in which to save CSV files.

    Raises:
        ValueError: If ``output_dir`` is None.
    """
    if output_dir is None:
        raise ValueError("Output needs to be specified for validation process directory cannot be None")

    out_path = Path(output_dir)
    out_path.mkdir(exist_ok=True)

    for scenario, df in results.items():
        output_file = out_path / f"{scenario}_action_rates_validation.csv"
        df.to_csv(output_file, index=False)


def summarize_statistical_comparison(
        results: Dict[str, pd.DataFrame],
        filter_fields: List[str],
        ground_truth_path: str | Path,
        output_dir: Union[str, Path] = None
) -> Dict[str, Dict[str, pd.DataFrame]]:
    """Summarize statistical/practical comparisons across scenarios.

    For each scenario in ``results``, this function:

    * Computes overall counts and percentages of combinations where
      simulated action rates are statistically/practically the same as
      ground truth according to:
      - t-test,
      - proportion z-test,
      - exact binomial test,
      - practical-equivalence threshold.
    * Produces DataFrames listing combinations where the simulation differs
      by each test.
    * Saves all summaries and per-test "different combinations" as CSVs.
    * Optionally produces combined summaries across all scenarios.

    Args:
        results: Dictionary mapping scenario name to the per-combination
            analysis DataFrame from
            :func:`calculate_action_rates_by_scenario`.
        filter_fields: List of filter field names used when generating
            ``results``.
        ground_truth_path: Path to the ground truth CSV file, used to
            count rows per combination.
        output_dir: Directory in which to save summary CSV files.

    Returns:
        Nested dictionary such that for each scenario key, the value is a
        dictionary containing:

        * ``'overall_summary'``: overall counts/percentages of combinations,
        * ``'ttest_different_combinations'``
        * ``'prop_z_different_combinations'``
        * ``'binomial_different_combinations'``
        * ``'practically_different_combinations'``.

    Raises:
        ValueError: If ``output_dir`` is None.
    """
    if output_dir is None:
        raise ValueError("Output needs to be specified for validation process directory cannot be None")

    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    # Load ground truth data for row counting
    print(f"Loading ground truth data from {ground_truth_path}")
    ground_truth = pd.read_csv(ground_truth_path)
    ground_truth.columns = ground_truth.columns.str.lower()

    # Convert filter_fields to lowercase for consistency
    filter_fields_lower = [field.lower() for field in filter_fields]

    all_summaries = {}

    for scenario, df in results.items():
        print(f"\nProcessing summary for {scenario}...")

        # Filter out rows where tests couldn't be performed (NaN values)
        df_valid_ttest = df[df['simulation_action_rate_statistically_same_as_ground_truth'].notna()].copy()
        df_valid_prop_z = df[df['prop_z_statistically_same'].notna()].copy()
        df_valid_binomial = df[df['binomial_statistically_same'].notna()].copy()
        df_valid_pract = df[df['practically_equivalent'].notna()].copy()

        # --- Calculate statistics for all tests ---

        # T-test counts
        ttest_same_count = (df_valid_ttest['simulation_action_rate_statistically_same_as_ground_truth'] == 1).sum()
        ttest_different_count = (df_valid_ttest['simulation_action_rate_statistically_same_as_ground_truth'] == 0).sum()
        ttest_total_valid = ttest_same_count + ttest_different_count

        # Proportion z-test counts
        prop_z_same_count = (df_valid_prop_z['prop_z_statistically_same'] == 1).sum()
        prop_z_different_count = (df_valid_prop_z['prop_z_statistically_same'] == 0).sum()
        prop_z_total_valid = prop_z_same_count + prop_z_different_count

        # Binomial test counts
        binomial_same_count = (df_valid_binomial['binomial_statistically_same'] == 1).sum()
        binomial_different_count = (df_valid_binomial['binomial_statistically_same'] == 0).sum()
        binomial_total_valid = binomial_same_count + binomial_different_count

        # Practical test counts
        pract_same_count = (df_valid_pract['practically_equivalent'] == 1).sum()
        pract_different_count = (df_valid_pract['practically_equivalent'] == 0).sum()
        pract_total_valid = pract_same_count + pract_different_count

        # Helper function to calculate metrics for a given mask and dataframe
        def calculate_metrics(df_subset, mask):
            inspection_nums = df_subset.loc[mask, 'num_inspection_numbers'].sum()

            # Calculate rows in ground truth
            rows = 0
            for _, row in df_subset[mask].iterrows():
                filter_condition = pd.Series([True] * len(ground_truth))
                for field in filter_fields_lower:
                    if field in ground_truth.columns:
                        filter_condition &= (ground_truth[field] == row[field])
                rows += filter_condition.sum()

            return inspection_nums, rows

        # Calculate metrics for t-test
        ttest_same_mask = df_valid_ttest['simulation_action_rate_statistically_same_as_ground_truth'] == 1
        ttest_different_mask = df_valid_ttest['simulation_action_rate_statistically_same_as_ground_truth'] == 0

        ttest_same_inspection_nums, ttest_same_rows = calculate_metrics(df_valid_ttest, ttest_same_mask)
        ttest_different_inspection_nums, ttest_different_rows = calculate_metrics(df_valid_ttest, ttest_different_mask)
        ttest_total_inspection_nums = ttest_same_inspection_nums + ttest_different_inspection_nums
        ttest_total_rows = ttest_same_rows + ttest_different_rows

        # Calculate metrics for proportion z-test
        prop_z_same_mask = df_valid_prop_z['prop_z_statistically_same'] == 1
        prop_z_different_mask = df_valid_prop_z['prop_z_statistically_same'] == 0

        prop_z_same_inspection_nums, prop_z_same_rows = calculate_metrics(df_valid_prop_z, prop_z_same_mask)
        prop_z_different_inspection_nums, prop_z_different_rows = calculate_metrics(df_valid_prop_z,
                                                                                    prop_z_different_mask)
        prop_z_total_inspection_nums = prop_z_same_inspection_nums + prop_z_different_inspection_nums
        prop_z_total_rows = prop_z_same_rows + prop_z_different_rows

        # Calculate metrics for binomial test
        binomial_same_mask = df_valid_binomial['binomial_statistically_same'] == 1
        binomial_different_mask = df_valid_binomial['binomial_statistically_same'] == 0

        binomial_same_inspection_nums, binomial_same_rows = calculate_metrics(df_valid_binomial, binomial_same_mask)
        binomial_different_inspection_nums, binomial_different_rows = calculate_metrics(df_valid_binomial,
                                                                                        binomial_different_mask)
        binomial_total_inspection_nums = binomial_same_inspection_nums + binomial_different_inspection_nums
        binomial_total_rows = binomial_same_rows + binomial_different_rows

        # Calculate metrics for practical test
        pract_same_mask = df_valid_pract['practically_equivalent'] == 1
        pract_different_mask = df_valid_pract['practically_equivalent'] == 0

        pract_same_inspection_nums, pract_same_rows = calculate_metrics(df_valid_pract, pract_same_mask)
        pract_different_inspection_nums, pract_different_rows = calculate_metrics(df_valid_pract, pract_different_mask)
        pract_total_inspection_nums = pract_same_inspection_nums + pract_different_inspection_nums
        pract_total_rows = pract_same_rows + pract_different_rows

        # Create overall summary with all tests
        overall_summary = pd.DataFrame({
            'comparison_result': [
                'T-Test Same',
                'T-Test Different',
                'Total Valid (T-Test)',
                'Prop Z-Test Same',
                'Prop Z-Test Different',
                'Total Valid (Prop Z-Test)',
                'Binomial Test Same',
                'Binomial Test Different',
                'Total Valid (Binomial Test)',
                'Practically Same',
                'Practically Different',
                'Total Valid (Practical)'
            ],
            'num_combinations': [
                ttest_same_count,
                ttest_different_count,
                ttest_total_valid,
                prop_z_same_count,
                prop_z_different_count,
                prop_z_total_valid,
                binomial_same_count,
                binomial_different_count,
                binomial_total_valid,
                pract_same_count,
                pract_different_count,
                pract_total_valid
            ],
            'percentage_of_combinations': [
                (ttest_same_count / ttest_total_valid * 100) if ttest_total_valid > 0 else 0,
                (ttest_different_count / ttest_total_valid * 100) if ttest_total_valid > 0 else 0,
                100.0,
                (prop_z_same_count / prop_z_total_valid * 100) if prop_z_total_valid > 0 else 0,
                (prop_z_different_count / prop_z_total_valid * 100) if prop_z_total_valid > 0 else 0,
                100.0,
                (binomial_same_count / binomial_total_valid * 100) if binomial_total_valid > 0 else 0,
                (binomial_different_count / binomial_total_valid * 100) if binomial_total_valid > 0 else 0,
                100.0,
                (pract_same_count / pract_total_valid * 100) if pract_total_valid > 0 else 0,
                (pract_different_count / pract_total_valid * 100) if pract_total_valid > 0 else 0,
                100.0
            ],
            'num_inspection_numbers': [
                ttest_same_inspection_nums,
                ttest_different_inspection_nums,
                ttest_total_inspection_nums,
                prop_z_same_inspection_nums,
                prop_z_different_inspection_nums,
                prop_z_total_inspection_nums,
                binomial_same_inspection_nums,
                binomial_different_inspection_nums,
                binomial_total_inspection_nums,
                pract_same_inspection_nums,
                pract_different_inspection_nums,
                pract_total_inspection_nums
            ],
            'percentage_of_inspection_numbers': [
                (
                            ttest_same_inspection_nums / ttest_total_inspection_nums * 100) if ttest_total_inspection_nums > 0 else 0,
                (
                            ttest_different_inspection_nums / ttest_total_inspection_nums * 100) if ttest_total_inspection_nums > 0 else 0,
                100.0,
                (
                            prop_z_same_inspection_nums / prop_z_total_inspection_nums * 100) if prop_z_total_inspection_nums > 0 else 0,
                (
                            prop_z_different_inspection_nums / prop_z_total_inspection_nums * 100) if prop_z_total_inspection_nums > 0 else 0,
                100.0,
                (
                            binomial_same_inspection_nums / binomial_total_inspection_nums * 100) if binomial_total_inspection_nums > 0 else 0,
                (
                            binomial_different_inspection_nums / binomial_total_inspection_nums * 100) if binomial_total_inspection_nums > 0 else 0,
                100.0,
                (
                            pract_same_inspection_nums / pract_total_inspection_nums * 100) if pract_total_inspection_nums > 0 else 0,
                (
                            pract_different_inspection_nums / pract_total_inspection_nums * 100) if pract_total_inspection_nums > 0 else 0,
                100.0
            ],
            'num_ground_truth_rows': [
                ttest_same_rows,
                ttest_different_rows,
                ttest_total_rows,
                prop_z_same_rows,
                prop_z_different_rows,
                prop_z_total_rows,
                binomial_same_rows,
                binomial_different_rows,
                binomial_total_rows,
                pract_same_rows,
                pract_different_rows,
                pract_total_rows
            ],
            'percentage_of_ground_truth_rows': [
                (ttest_same_rows / ttest_total_rows * 100) if ttest_total_rows > 0 else 0,
                (ttest_different_rows / ttest_total_rows * 100) if ttest_total_rows > 0 else 0,
                100.0,
                (prop_z_same_rows / prop_z_total_rows * 100) if prop_z_total_rows > 0 else 0,
                (prop_z_different_rows / prop_z_total_rows * 100) if prop_z_total_rows > 0 else 0,
                100.0,
                (binomial_same_rows / binomial_total_rows * 100) if binomial_total_rows > 0 else 0,
                (binomial_different_rows / binomial_total_rows * 100) if binomial_total_rows > 0 else 0,
                100.0,
                (pract_same_rows / pract_total_rows * 100) if pract_total_rows > 0 else 0,
                (pract_different_rows / pract_total_rows * 100) if pract_total_rows > 0 else 0,
                100.0
            ]
        })

        # Add scenario information
        overall_summary.insert(0, 'scenario', scenario)

        # --- Helper function to create different combinations dataframe ---
        def create_different_combinations_df(df_valid, test_column, test_name):
            different_combinations = df_valid[df_valid[test_column] == 0].copy()

            # Add row count for each different combination
            row_counts = []
            for _, row in different_combinations.iterrows():
                filter_condition = pd.Series([True] * len(ground_truth))
                for field in filter_fields_lower:
                    if field in ground_truth.columns:
                        filter_condition &= (ground_truth[field] == row[field])
                row_counts.append(filter_condition.sum())

            # Determine which columns to include based on test type
            if test_name == 'ttest':
                columns_to_include = (
                        filter_fields_lower +
                        [
                            'ground_truth_action_rate',
                            'mean_simulation_action_rate',
                            'std_simulation_action_rate',
                            'num_inspection_numbers',
                            'num_valid_replications',
                            'p_value',
                            'action_rate_abs_diff',
                            'practically_equivalent',
                            'practical_threshold',
                            'prop_z_statistically_same',
                            'prop_z_p_value',
                            'binomial_statistically_same',
                            'binomial_p_value'
                        ]
                )
            elif test_name == 'prop_z':
                columns_to_include = (
                        filter_fields_lower +
                        [
                            'ground_truth_action_rate',
                            'mean_simulation_action_rate',
                            'std_simulation_action_rate',
                            'num_inspection_numbers',
                            'num_valid_replications',
                            'prop_z_p_value',
                            'action_rate_abs_diff',
                            'practically_equivalent',
                            'practical_threshold',
                            'simulation_action_rate_statistically_same_as_ground_truth',
                            'p_value',
                            'binomial_statistically_same',
                            'binomial_p_value'
                        ]
                )
            elif test_name == 'binomial':
                columns_to_include = (
                        filter_fields_lower +
                        [
                            'ground_truth_action_rate',
                            'mean_simulation_action_rate',
                            'std_simulation_action_rate',
                            'num_inspection_numbers',
                            'num_valid_replications',
                            'binomial_p_value',
                            'action_rate_abs_diff',
                            'practically_equivalent',
                            'practical_threshold',
                            'simulation_action_rate_statistically_same_as_ground_truth',
                            'p_value',
                            'prop_z_statistically_same',
                            'prop_z_p_value'
                        ]
                )
            else:  # practical
                columns_to_include = (
                        filter_fields_lower +
                        [
                            'ground_truth_action_rate',
                            'mean_simulation_action_rate',
                            'std_simulation_action_rate',
                            'num_inspection_numbers',
                            'num_valid_replications',
                            'action_rate_abs_diff',
                            'practical_threshold',
                            'simulation_action_rate_statistically_same_as_ground_truth',
                            'p_value',
                            'prop_z_statistically_same',
                            'prop_z_p_value',
                            'binomial_statistically_same',
                            'binomial_p_value'
                        ]
                )

            columns_to_include = [col for col in columns_to_include if col in different_combinations.columns]
            different_combinations = different_combinations[columns_to_include].copy()
            different_combinations['num_ground_truth_rows'] = row_counts

            # Calculate relative difference
            different_combinations['relative_difference_pct'] = (
                    (different_combinations['action_rate_abs_diff'] /
                     different_combinations['ground_truth_action_rate']) * 100
            )

            # Sort by absolute difference
            different_combinations = different_combinations.sort_values(
                'action_rate_abs_diff',
                ascending=False
            ).reset_index(drop=True)

            different_combinations.insert(0, 'scenario', scenario)

            return different_combinations

        # --- Create different combinations dataframes for each test ---
        ttest_different_combinations = create_different_combinations_df(
            df_valid_ttest,
            'simulation_action_rate_statistically_same_as_ground_truth',
            'ttest'
        )

        prop_z_different_combinations = create_different_combinations_df(
            df_valid_prop_z,
            'prop_z_statistically_same',
            'prop_z'
        )

        binomial_different_combinations = create_different_combinations_df(
            df_valid_binomial,
            'binomial_statistically_same',
            'binomial'
        )

        pract_different_combinations = create_different_combinations_df(
            df_valid_pract,
            'practically_equivalent',
            'practical'
        )

        # Store results
        all_summaries[scenario] = {
            'overall_summary': overall_summary,
            'ttest_different_combinations': ttest_different_combinations,
            'prop_z_different_combinations': prop_z_different_combinations,
            'binomial_different_combinations': binomial_different_combinations,
            'practically_different_combinations': pract_different_combinations
        }

        # Save to CSV
        overall_file = output_path / f"{scenario}_overall_summary.csv"
        ttest_different_file = output_path / f"{scenario}_ttest_different_combinations.csv"
        prop_z_different_file = output_path / f"{scenario}_prop_z_different_combinations.csv"
        binomial_different_file = output_path / f"{scenario}_binomial_different_combinations.csv"
        pract_different_file = output_path / f"{scenario}_practically_different_combinations.csv"

        overall_summary.to_csv(overall_file, index=False)
        ttest_different_combinations.to_csv(ttest_different_file, index=False)
        prop_z_different_combinations.to_csv(prop_z_different_file, index=False)
        binomial_different_combinations.to_csv(binomial_different_file, index=False)
        pract_different_combinations.to_csv(pract_different_file, index=False)

        print(f"Saved overall summary to: {overall_file}")
        print(f"Saved t-test different combinations to: {ttest_different_file}")
        print(f"Saved proportion z-test different combinations to: {prop_z_different_file}")
        print(f"Saved binomial test different combinations to: {binomial_different_file}")
        print(f"Saved practically different combinations to: {pract_different_file}")
        print(
            f"  T-Test: {ttest_same_count} same, {ttest_different_count} different ({ttest_different_rows:,} ground truth rows)")
        print(
            f"  Prop Z-Test: {prop_z_same_count} same, {prop_z_different_count} different ({prop_z_different_rows:,} ground truth rows)")
        print(
            f"  Binomial Test: {binomial_same_count} same, {binomial_different_count} different ({binomial_different_rows:,} ground truth rows)")
        print(
            f"  Practical Test: {pract_same_count} same, {pract_different_count} different ({pract_different_rows:,} ground truth rows)")

    # Create combined summaries across all scenarios
    if len(results) > 1:
        # Combine overall summaries
        combined_overall = pd.concat(
            [summary['overall_summary'] for summary in all_summaries.values()],
            ignore_index=True
        )
        combined_overall_file = output_path / "all_scenarios_overall_summary.csv"
        combined_overall.to_csv(combined_overall_file, index=False)
        print(f"\nSaved combined overall summary to: {combined_overall_file}")

        # Combine t-test different combinations
        combined_ttest_different = pd.concat(
            [summary['ttest_different_combinations'] for summary in all_summaries.values()],
            ignore_index=True
        )
        combined_ttest_different_file = output_path / "all_scenarios_ttest_different_combinations.csv"
        combined_ttest_different.to_csv(combined_ttest_different_file, index=False)
        print(f"Saved combined t-test different combinations to: {combined_ttest_different_file}")

        # Combine prop z-test different combinations
        combined_prop_z_different = pd.concat(
            [summary['prop_z_different_combinations'] for summary in all_summaries.values()],
            ignore_index=True
        )
        combined_prop_z_different_file = output_path / "all_scenarios_prop_z_different_combinations.csv"
        combined_prop_z_different.to_csv(combined_prop_z_different_file, index=False)
        print(f"Saved combined prop z-test different combinations to: {combined_prop_z_different_file}")

        # Combine binomial test different combinations
        combined_binomial_different = pd.concat(
            [summary['binomial_different_combinations'] for summary in all_summaries.values()],
            ignore_index=True
        )
        combined_binomial_different_file = output_path / "all_scenarios_binomial_different_combinations.csv"
        combined_binomial_different.to_csv(combined_binomial_different_file, index=False)
        print(f"Saved combined binomial test different combinations to: {combined_binomial_different_file}")

        # Combine practically different combinations
        combined_pract_different = pd.concat(
            [summary['practically_different_combinations'] for summary in all_summaries.values()],
            ignore_index=True
        )
        combined_pract_different_file = output_path / "all_scenarios_practically_different_combinations.csv"
        combined_pract_different.to_csv(combined_pract_different_file, index=False)
        print(f"Saved combined practically different combinations to: {combined_pract_different_file}")

    return all_summaries