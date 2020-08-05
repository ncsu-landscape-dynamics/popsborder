#!/usr/bin/env python
# -*- coding: utf-8 -*-

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
Simulation for evaluataion of pathways

.. codeauthor:: Vaclav Petras <wenzeslaus gmail com>
"""

from __future__ import print_function, division

import sys
import types
import random
import numpy as np


from .shipments import (
    get_shipment_generator,
    get_pest_function,
)
from .inspections import (
    get_inspection_needed_function,
    get_sample_function,
    inspect,
    is_shipment_diseased,
    shipment_infestation_rate,
)
from .outputs import (
    Form280,
    PrintReporter,
    MuteReporter,
    SuccessRates,
    pretty_shipment,
)


def random_seed(seed):
    """Set seed for all generators used"""
    random.seed(seed)  # random package
    np.random.seed(seed)  # NumPy and SciPy


def simulation(
    config, num_shipments, seed, output_f280_file=None, verbose=False, pretty=None
):
    """Simulate shipments, their infestation, and their inspection

    :param config: Simulation configuration as a dictionary
    :param num_shipments: Number of shipments to generate
    :param f280_file: Filename for output F280 records
    :param verbose: If True, prints messages about each shipment
    """
    # pylint: disable=too-many-locals,too-many-branches,too-many-statements

    if seed is not None:
        random_seed(seed)

    # allow for an empty disposition code specification
    disposition_codes = config.get("disposition_codes", {})
    form280 = Form280(output_f280_file, disposition_codes=disposition_codes)
    if verbose:
        reporter = PrintReporter()
    else:
        reporter = MuteReporter()
    success_rates = SuccessRates(reporter)
    num_inspections = 0
    total_num_boxes = 0
    total_num_stems = 0
    total_boxes_opened_completion = 0
    total_boxes_opened_detection = 0
    total_stems_inspected_completion = 0
    total_stems_inspected_detection = 0
    total_infested_stems_completion = 0
    total_infested_stems_detection = 0
    true_infestation_rate = 0
    intercepted_infestation_rate = 0
    missed_infestation_rate = 0

    shipment_generator = get_shipment_generator(config)
    add_pest = get_pest_function(config)
    is_inspection_needed = get_inspection_needed_function(config)
    sample = get_sample_function(config)

    for unused_i in range(num_shipments):
        shipment = shipment_generator.generate_shipment()
        add_pest(shipment)
        if pretty:
            pretty_config = config.get("pretty", {})
            print(pretty_shipment(shipment, style=pretty, config=pretty_config))

        must_inspect, applied_program = is_inspection_needed(
            shipment, shipment["arrival_time"]
        )
        if must_inspect:
            n_units_to_inspect = sample(shipment)
            ret = inspect(config, shipment, n_units_to_inspect)
            shipment_checked_ok = ret.shipment_checked_ok
            num_inspections += 1
            total_num_boxes += shipment["num_boxes"]
            total_num_stems += shipment["num_stems"]
            total_boxes_opened_completion += ret.boxes_opened_completion
            total_boxes_opened_detection += ret.boxes_opened_detection
            total_stems_inspected_completion += ret.stems_inspected_completion
            total_stems_inspected_detection += ret.stems_inspected_detection
            total_infested_stems_completion += ret.infested_stems_completion
            total_infested_stems_detection += ret.infested_stems_detection
        else:
            shipment_checked_ok = True  # assuming or hoping it's ok
            total_num_boxes += shipment["num_boxes"]
            total_num_stems += shipment["num_stems"]
        form280.fill(
            shipment["arrival_time"],
            shipment,
            shipment_checked_ok,
            must_inspect,
            applied_program,
        )
        shipment_actually_ok = not is_shipment_diseased(shipment)
        success_rates.record_success_rate(
            shipment_checked_ok, shipment_actually_ok, shipment
        )
        true_infestation_rate += shipment_infestation_rate(shipment)
        if not shipment_actually_ok:
            if shipment_checked_ok:
                missed_infestation_rate += shipment_infestation_rate(shipment)
            else:
                intercepted_infestation_rate += shipment_infestation_rate(shipment)

    num_diseased = num_shipments - success_rates.ok
    if num_diseased:
        # avoiding float division by zero
        missing = 100 * float(success_rates.false_negative) / (num_diseased)
        if verbose:
            print("Missing {0:.0f}% of shipments with pest.".format(missing))
    else:
        # we didn't miss anything
        missing = 0

    if success_rates.false_negative:
        false_negative_present = True
        missed_infestation_rate = missed_infestation_rate / success_rates.false_negative
    else:
        false_negative_present = False
        missed_infestation_rate = 0

    if success_rates.true_positive:
        true_positive_present = True
        intercepted_infestation_rate = (
            intercepted_infestation_rate / success_rates.true_positive
        )
        pct_pest_unreported_if_detection = (
            1 - (total_infested_stems_detection / total_infested_stems_completion)
        ) * 100
    else:
        true_positive_present = False
        intercepted_infestation_rate = 0
        pct_pest_unreported_if_detection = 0

    return types.SimpleNamespace(
        missing=missing,
        num_inspections=num_inspections,
        total_num_boxes=total_num_boxes,
        total_num_stems=total_num_stems,
        avg_boxes_opened_completion=total_boxes_opened_completion / num_shipments,
        avg_boxes_opened_detection=total_boxes_opened_detection / num_shipments,
        pct_boxes_opened_completion=(
            (total_boxes_opened_completion / total_num_boxes) * 100
        ),
        pct_boxes_opened_detection=(
            (total_boxes_opened_detection / total_num_boxes) * 100
        ),
        avg_stems_inspected_completion=total_stems_inspected_completion / num_shipments,
        avg_stems_inspected_detection=total_stems_inspected_detection / num_shipments,
        pct_stems_inspected_completion=(
            (total_stems_inspected_completion / total_num_stems) * 100
        ),
        pct_stems_inspected_detection=(
            (total_stems_inspected_detection / total_num_stems) * 100
        ),
        pct_sample_if_to_detection=(
            (total_stems_inspected_detection / total_stems_inspected_completion) * 100
        ),
        pct_pest_unreported_if_detection=pct_pest_unreported_if_detection,
        true_infestation_rate=true_infestation_rate / num_shipments,
        missed_infestation_rate=missed_infestation_rate,
        intercepted_infestation_rate=intercepted_infestation_rate,
        false_negative_present=false_negative_present,
        true_positive_present=true_positive_present,
    )


def run_simulation(
    config,
    num_simulations,
    num_shipments,
    seed=None,
    output_f280_file=None,
    verbose=False,
    pretty=None,
):
    """Run the simulation function specified number of times

    See :func:`simulation` function for explanation of parameters.

    Returns averages computed from the individual simulation runs otherwise
    it relies on :func:`simulation` function to do the hard work.
    """
    # pylint: disable=too-many-branches,too-many-statements

    totals = types.SimpleNamespace(
        missing=0,
        num_inspections=0,
        num_boxes=0,
        num_stems=0,
        avg_boxes_opened_completion=0,
        avg_boxes_opened_detection=0,
        pct_boxes_opened_completion=0,
        pct_boxes_opened_detection=0,
        avg_stems_inspected_completion=0,
        avg_stems_inspected_detection=0,
        pct_stems_inspected_completion=0,
        pct_stems_inspected_detection=0,
        pct_sample_if_to_detection=0,
        pct_pest_unreported_if_detection=0,
        true_infestation_rate=0,
        missed_infestation_rate=0,
        intercepted_infestation_rate=0,
        false_negative_present=0,
        true_positive_present=0,
    )

    for i in range(num_simulations):
        result = simulation(
            config=config,
            num_shipments=num_shipments,
            seed=seed + i if seed else None,
            output_f280_file=output_f280_file,
            verbose=verbose,
            pretty=pretty,
        )
        totals.missing += result.missing
        totals.num_inspections += result.num_inspections
        totals.num_boxes += result.total_num_boxes
        totals.num_stems += result.total_num_stems
        totals.avg_boxes_opened_completion += result.avg_boxes_opened_completion
        totals.avg_boxes_opened_detection += result.avg_boxes_opened_detection
        totals.pct_boxes_opened_completion += result.pct_boxes_opened_completion
        totals.pct_boxes_opened_detection += result.pct_boxes_opened_detection
        totals.avg_stems_inspected_completion += result.avg_stems_inspected_completion
        totals.avg_stems_inspected_detection += result.avg_stems_inspected_detection
        totals.pct_stems_inspected_completion += result.pct_stems_inspected_completion
        totals.pct_stems_inspected_detection += result.pct_stems_inspected_detection
        totals.pct_sample_if_to_detection += result.pct_sample_if_to_detection
        totals.pct_pest_unreported_if_detection += (
            result.pct_pest_unreported_if_detection
        )
        totals.true_infestation_rate += result.true_infestation_rate
        totals.missed_infestation_rate += result.missed_infestation_rate
        totals.intercepted_infestation_rate += result.intercepted_infestation_rate
        totals.false_negative_present += result.false_negative_present
        totals.true_positive_present += result.true_positive_present
    # make these relative (reusing the variables)
    totals.missing /= float(num_simulations)
    totals.num_inspections /= float(num_simulations)
    totals.num_boxes /= float(num_simulations)
    totals.num_stems /= float(num_simulations)
    totals.avg_boxes_opened_completion /= float(num_simulations)
    totals.avg_boxes_opened_detection /= float(num_simulations)
    totals.pct_boxes_opened_completion /= float(num_simulations)
    totals.pct_boxes_opened_detection /= float(num_simulations)
    totals.avg_stems_inspected_completion /= float(num_simulations)
    totals.avg_stems_inspected_detection /= float(num_simulations)
    totals.pct_stems_inspected_completion /= float(num_simulations)
    totals.pct_stems_inspected_detection /= float(num_simulations)
    totals.pct_sample_if_to_detection /= float(num_simulations)
    totals.pct_pest_unreported_if_detection /= float(num_simulations)
    totals.true_infestation_rate /= float(num_simulations)
    if totals.false_negative_present:
        totals.missed_infestation_rate /= float(totals.false_negative_present)
    else:
        totals.missed_infestation_rate = None
    if totals.true_positive_present:
        totals.intercepted_infestation_rate /= float(totals.true_positive_present)
    else:
        totals.intercepted_infestation_rate = None

    return totals


def load_configuration_yaml_from_text(text):
    """Return configuration dictionary from YAML in a string"""
    import yaml  # pylint: disable=import-outside-toplevel

    if hasattr(yaml, "full_load"):
        return yaml.full_load(text)
    return yaml.load(text)


def load_configuration(filename):
    """Get the configuration from a JSON or YAML file

    The format is decided based on the file extension.
    It uses full_load() (FullLoader) to read YAML.

    The parameter can be a string or a path object (path-like object).
    """
    if str(filename).endswith(".json"):
        import json  # pylint: disable=import-outside-toplevel

        return json.load(open(filename))
    elif str(filename).endswith(".yaml") or str(filename).endswith(".yml"):
        import yaml  # pylint: disable=import-outside-toplevel

        if hasattr(yaml, "full_load"):
            return yaml.full_load(open(filename))
        return yaml.load(open(filename))
    else:
        sys.exit("Unknown file extension (file: {})".format(filename))
