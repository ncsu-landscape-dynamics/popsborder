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

from .simulation import run_simulation, load_configuration


def update_nested_dict_by_dict(dictionary, update):
    for key, value in update.items():
        if isinstance(value, collections.abc.Mapping):
            dictionary[key] = update_nested_dict_by_dict(dictionary.get(key, {}), value)
        else:
            dictionary[key] = value

def update_nested_dict_by_item(dictionary, keys, value):
    if len(keys) == 1:
        dictionary[keys[0]] = value
    else:
        if keys[0] not in dictionary:
            dictionary[keys[0]] = {}
        update_nested_dict_by_item(dictionary[keys[0]], keys[1:], value)

def record_to_nested_dictionary(record):
    out = {}
    for path, value in record.items():
        keys = path.split("/")
        update_nested_dict_by_item(out, keys, value)
    return out


def updated_config(config, record):
    config = copy.deepcopy(config)
    update = record_to_nested_dictionary(record)
    update_nested_dict_by_dict(config, update)
    return config


def run_scenarios(basic_config, scenario_table, seed, num_simulations, num_shipments):
    results = []
    for record in scenario_table:
        scenario_config = updated_config(basic_config, record)
        totals, sim_params = run_simulation(
            config=scenario_config,
            num_simulations=num_simulations,
            num_shipments=num_shipments,
            seed=seed,
        )
        results.append(totals)
    return results


def load_scenario_table(filename):
    import csv  # pylint: disable=import-outside-toplevel
    
    return csv.DictReader(filename)

# def run_scenarios_from_files(basic_config_file, scenarios_file):
    