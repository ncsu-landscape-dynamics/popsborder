# Simulation for evaluataion of pathways
# Copyright (C) 2018-2020 Vaclav Petras

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


"""
Functionality for running multiple scenarios

.. codeauthor:: Vaclav Petras <wenzeslaus gmail com>
"""

import copy
import collections.abc

from .simulation import run_simulation


def update_nested_dict_by_dict(dictionary, update):
    """Recursively update nested dictionary by anther nested dictionary"""
    for key, value in update.items():
        if isinstance(value, collections.abc.Mapping):
            update_nested_dict_by_dict(dictionary.get(key, {}), value)
        else:
            dictionary[key] = value


def update_nested_dict_by_item(dictionary, keys, value):
    """Update nested dictionary by a nested keys-value pair

    An item is a list of keys to navigate the nested dictionary and a value to place
    in the given position.

    When a key can be represented as an int, it is used as a list index.
    List must already exists in the given size or the only index used must be 0.

    Floating point keys are not supported.
    """
    if len(keys) == 1:
        key = keys[0]
        try:
            key = int(key)
        except ValueError:
            pass
        dictionary[key] = value
    else:
        if keys[0] not in dictionary:
            try:
                # Test if the next key is an integer and thus index in a list.
                int(keys[1])
                # In case it is a list, we require keys are items are filled in order.
                dictionary[keys[0]] = [None]
            except ValueError:
                dictionary[keys[0]] = {}
        update_nested_dict_by_item(dictionary[keys[0]], keys[1:], value)


def record_to_nested_dictionary(record):
    """Convert dictionary with key/subkey/subsubkey keys into a nested dictionary"""
    out = {}
    for path, value in record.items():
        keys = path.split("/")
        update_nested_dict_by_item(out, keys, value)
    return out


def update_config(config, record):
    """Update config dictionary by a dictionary with key/subkey/subsubkey keys"""
    config = copy.deepcopy(config)
    update = record_to_nested_dictionary(record)
    update_nested_dict_by_dict(config, update)
    return config


def run_scenarios(
    config, scenario_table, seed, num_simulations, num_shipments, detailed=False
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
    num_shipments : int
        Number of shipements in each simulation.

    Returns
    -------
    results : list of tuples
        List of results with one tuple for each scenario. One tuple contains simulation
        result and configuration for that scenario.
    """
    results = []
    if detailed:
        scenario_details = []
    for record in scenario_table:
        print(record["name"])
        scenario_config = update_config(config, record)
        if detailed:
            result, details = run_simulation(
                config=scenario_config,
                num_simulations=num_simulations,
                num_shipments=num_shipments,
                seed=seed,
                detailed=True,
            )
            scenario_details.append(details)
        else:
            result = run_simulation(
                config=scenario_config,
                num_simulations=num_simulations,
                num_shipments=num_shipments,
                seed=seed,
            )
        results.append((result, scenario_config))
    if detailed:
        return results, scenario_details
    else:
        return results


def load_scenario_table(filename):
    """Load a CSV file into a list of dictionaries

    Values which can be converted into int or float are converted. Cells which can be
    parsed as JSON, will be loaded into Python data structures (dicts, lists, etc.).

    A whole file is read and loaded into memory unlike with the ``csv.reader()``
    function.
    """
    # pylint: disable=import-outside-toplevel
    import csv
    import json

    table = []
    with open(filename) as file:
        for row in csv.DictReader(file):
            for key, value in row.items():
                try:
                    value = int(value)
                    row[key] = value
                except ValueError:
                    try:
                        value = float(value)
                        row[key] = value
                    except ValueError:
                        try:
                            value = json.loads(value)
                            row[key] = value
                        except json.JSONDecodeError:
                            pass
            table.append(row)
    return table
