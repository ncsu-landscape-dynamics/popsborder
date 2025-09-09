# Simulation of contaminated consignments and their inspections
# Copyright (C) 2018-2021 Vaclav Petras and others (see below)

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.

# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.

# You should have received a copy of the GNU General Public License along with
# this program; if not, see https://www.gnu.org/licenses/gpl-2.0.html


"""Functionality for running multiple scenarios

.. codeauthor:: Vaclav Petras <wenzeslaus gmail com>
"""

import itertools
from concurrent.futures import ProcessPoolExecutor, as_completed

from .inputs import update_config
from .simulation import run_simulation


def run_scenarios(
    config, scenario_table, seed, num_simulations, num_consignments, detailed=False
):
    """Run scenarios based on the configuration and list of scenarios

    Parameters
    ----------
    config : nested dict
        Basic configuration for each simulation.
    scenario_table : list of dicts
        Configurations specific for each scenario as a list of dictionaries with
        key/subkey/subsubkey keys.
    seed : int
        Seed for a random generator. All scenarios get the same seed, but each
        simulation within a scenario runs with a different seed based on this one.
    num_simulations : int
        Num of simulations for each scenario.
    num_consignments : int
        Number of shipements in each simulation.

    Returns
    -------
    results : list of tuples
        List of results with one tuple for each scenario. One tuple contains simulation
        result and configuration for that scenario.
    """
    results = []
    for record in scenario_table:
        scenario_name = record["name"]
        print(f"Running scenario: {scenario_name}")
        scenario_config = update_config(config, record)
        result = run_simulation(
            config=scenario_config,
            num_simulations=num_simulations,
            num_consignments=num_consignments,
            seed=seed,
            detailed=detailed,
        )
        if detailed:
            # The result is tuple of details ([0]) and simulation totals ([1]).
            results.append((result[0], result[1], scenario_config))
        else:
            # The result is simulation totals.
            results.append((result, scenario_config))
    return results


def run_scenarios_parallel(
    config,
    scenario_table,
    seed,
    num_runs_per_submission,
    num_submission_per_scenario,
    num_consignments,
    max_workers=None,
):
    """Run scenarios in parallel using concurrent.futures.

    Parameters
    ----------
    config : nested dict
        Basic configuration for each simulation.
    scenario_table : list of dicts
        Configurations specific for each scenario.
    seed : int
        Random seed base. Each scenario will derive its own seeds.
    num_simulations : int
        Number of simulations per scenario.
    num_consignments : int
        Number of consignments in each simulation.
    max_workers : int, optional
        Number of workers for parallel execution. Defaults to cpu_count().
    """
    results = []

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_to_scenario = {}
        for record in scenario_table:
            for computed_seed in range(
                seed,
                seed + (num_submission_per_scenario * num_runs_per_submission),
                num_runs_per_submission,
            ):
                scenario_config = update_config(config, record)
                future_to_scenario[
                    executor.submit(
                        run_simulation,
                        config=scenario_config,
                        num_simulations=num_runs_per_submission,
                        num_consignments=num_consignments,
                        seed=computed_seed,
                        detailed=False,
                        individual=True,
                    )
                ] = scenario_config

        print(f"doing {len(future_to_scenario)} submissions...")
        print(f"running {num_runs_per_submission * len(future_to_scenario)} simulations...")

        # Collect results as they finish
        for future in as_completed(future_to_scenario):
            scenario_config = future_to_scenario[future]
            try:
                unused_totals, individual_results = future.result()
                for result in individual_results:
                    results.append((result, scenario_config))
            except Exception as e:
                print(f"Scenario {record['name']} failed: {e}")
    return results


def generate_scenarios(parameter_values, done=None):
    """
    Generate a list of scenario dictionaries with different parameter combinations.

    Parameters
    ----------
    parameter_values : dict
        Dictionary of parameter names mapping to lists of values.
        Example:
        {
            "inspection/effectiveness": [0.5, 0.7, 0.9],
            "contamination/contamination_rate/value": [0.01, 0.05, 0.1],
            "contamination/clustered/value": [0.1, 0.3, 0.5],
        }
    done : pd.DataFrame or None
        Previously completed scenarios (with matching parameter columns).

    Returns
    -------
    scenarios : list of dict
        Each dict represents a scenario.
    found : int
        Number of scenarios skipped because they were already in `done`.
    """
    scenarios = []
    found = 0

    keys = list(parameter_values.keys())
    values = list(parameter_values.values())

    # Precompute set of done combinations as tuples
    done_combos = set()
    if done is not None and not done.empty:
        done_combos = set(tuple(row[k] for k in keys) for _, row in done.iterrows())

    # Cartesian product over all parameter lists
    for combo in itertools.product(*values):
        scenario = dict(zip(keys, combo))

        # Create a descriptive scenario name
        scenario_name = "_".join(
            f"{parameter}={value}" for parameter, value in scenario.items()
        )
        scenario["name"] = scenario_name

        # Skip if already in 'done' (exact match across all params)
        if tuple(combo) in done_combos:
            found += 1
            continue

        scenarios.append(scenario)

    return scenarios, found
