# Simulation of contaminated consignments and their inspections
# Copyright (C) 2018-2025 Vaclav Petras and others (see below)
# © 2026 The Johns Hopkins University Applied Physics Laboratory LLC

"""
==========================================================================================
Johns Hopkins University Applied Physics Laboratory (JHU/APL) Extensions and Modifications
==========================================================================================

Contributors: Gary Lin, Joseph Agor (JHU/APL)

Modifications:
    Following Functions Modified
    ----------------
    - simulation():
        * Added RBS functionalities that utilize compliance levels to adjust hypergeometric sampling parameters
        * Enhanced to support compliance table integration for country/material type specific detection levels
        * Updated variable names throughout for terminology consistency (boxes -> inspection_units, items -> sample_units)

    - run_simulation():
        * Enhanced result tracking and aggregation for refactored terminology
        * Updated contamination and inspection counting for new hierarchical structure
        * Added support for plant-level contamination tracking in hierarchical consignments
    ----------------

    Terminology Refactoring
    ----------------
    - Updated all variable names from box/item terminology to inspection_unit/sample_unit terminology
    - Enhanced result aggregation to handle both legacy and new terminology reporting
    - Maintained backward compatibility in simulation result structures
        - Johns Hopkins University Applied Physics Laboratory (JHU/APL)
        - United States Department of Agriculture Animal and Plant Health Inspection Service (USDA APHIS)
        * Supports hierarchical packaging structure (boxes -> items -> plants)
        * Custom consignment data input from CSV
    - run_simulation():
        * Inputs for plant-level parameters, compliance table file, and consignment data supported
    ----------------
"""

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


"""Single and multiple runs of the simulation.

.. codeauthor:: Vaclav Petras <wenzeslaus gmail com>
.. codeauthor:: Kellyn P. Montgomery <kellynmontgomery gmail com>
.. codeauthor:: Gary Lin <Gary.Lin jhuapl edu>
.. codeauthor:: Joseph Agor <Joseph.Agor jhuapl edu>
"""

import random
import types
from collections import Counter
from typing import Callable, Optional

import numpy as np
import pandas as pd
import math
import os
import sys

from . import consignments
from .consignments import get_consignment_generator
from .contamination import get_contaminant_function, synchronize_contamination_arrays_from_plants
from .inspections import (
    consignment_contamination_rate,
    get_sample_function,
    inspect,
    is_consignment_contaminated,
)
from .outputs import (
    Form280,
    MuteReporter,
    PrintReporter,
    SuccessRates,
    pretty_consignment,
    PISSimData,
)
from .skipping import get_inspection_needed_function


def random_seed(seed):
    """Set seed for all generators used"""
    random.seed(seed)  # random package
    np.random.seed(seed)  # NumPy and SciPy

def simulation(
    config,
    num_consignments,
    seed,
    output_f280_file=None,
    verbose=False,
    pretty=None,
    detailed=False,
):
    """Simulate consignments, their contamination, and their inspection

    :param config: Simulation configuration as a dictionary
    :param num_consignments: Number of consignments to generate
    :param f280_file: Filename for output F280 records
    :param verbose: If True, prints messages about each consignment
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
    missed_within_tolerance = 0
    num_inspections = 0
    total_num_boxes = 0
    total_num_items = 0
    total_boxes_opened_completion = 0
    total_boxes_opened_detection = 0
    total_items_inspected_completion = 0
    total_items_inspected_detection = 0
    total_contaminated_items_completion = 0
    total_contaminated_items_detection = 0
    true_contamination_rate = 0
    intercepted_contamination_rate = []
    missed_contamination_rate = []
    total_intercepted_contaminants = 0
    total_missed_contaminants = 0
    total_contaminants = 0
    if detailed:
        item_details = []
        inspected_item_details = []

    consignment_generator = get_consignment_generator(config)
    add_contaminant = get_contaminant_function(config)
    is_inspection_needed = get_inspection_needed_function(config)
    sample = get_sample_function(config)
    tolerance_level = config["inspection"].get("tolerance_level", 0)

    for unused_i in range(num_consignments):
        consignment = consignment_generator.generate_consignment()
        add_contaminant(consignment)
        if detailed:
            for box in consignment.boxes:
                item_details.append(box.items)
        if pretty:
            pretty_config = config.get("pretty", {})
            print(pretty_consignment(consignment, style=pretty, config=pretty_config))

        must_inspect, applied_program = is_inspection_needed(
            consignment, consignment.date
        )
        if must_inspect:
            n_units_to_inspect = sample(consignment)
            ret = inspect(config, consignment, n_units_to_inspect, detailed)
            consignment_checked_ok = ret.consignment_checked_ok
            num_inspections += 1
            total_num_boxes += consignment.num_boxes
            total_num_items += consignment.num_items
            total_boxes_opened_completion += ret.boxes_opened_completion
            total_boxes_opened_detection += ret.boxes_opened_detection
            total_items_inspected_completion += ret.items_inspected_completion
            total_items_inspected_detection += ret.items_inspected_detection
            total_contaminated_items_completion += ret.contaminated_items_completion
            total_contaminated_items_detection += ret.contaminated_items_detection
            if detailed:
                inspected_item_details.append(ret.inspected_item_indexes)
        else:
            consignment_checked_ok = True  # assuming or hoping it's ok
            total_num_boxes += consignment.num_boxes
            total_num_items += consignment.num_items

        if hasattr(is_inspection_needed, "add_inspection_result"):
            is_inspection_needed.add_inspection_result(
                consignment, inspected=must_inspect, result=consignment_checked_ok
            )

        form280.fill(
            consignment.date,
            consignment,
            consignment_checked_ok,
            must_inspect,
            applied_program,
        )
        consignment_actually_ok = not is_consignment_contaminated(consignment)
        success_rates.record_success_rate(
            consignment_checked_ok, consignment_actually_ok, consignment
        )
        true_contamination_rate += consignment_contamination_rate(consignment)
        if not consignment_actually_ok:
            if consignment_checked_ok:
                if consignment_contamination_rate(consignment) < tolerance_level:
                    # Implemented as a discount to be applied later, so that the
                    # base numbers are unaffected even with tolerance active.
                    missed_within_tolerance += 1
                missed_contamination_rate.append(
                    consignment_contamination_rate(consignment)
                )
                total_missed_contaminants += consignment.count_contaminated()
            else:
                intercepted_contamination_rate.append(
                    consignment_contamination_rate(consignment)
                )
                total_intercepted_contaminants += consignment.count_contaminated()
            total_contaminants += consignment.count_contaminated()

    num_contaminated = num_consignments - success_rates.ok
    if num_contaminated:
        # avoiding float division by zero
        missing = 100 * float(success_rates.false_negative) / (num_contaminated)
        false_neg = success_rates.false_negative
        if verbose:
            print(f"Missing {missing:.0f}% of contaminated consignments.")
    else:
        # we didn't miss anything
        missing = 0
        false_neg = 0

    if success_rates.false_negative:
        false_negative_present = True
        max_missed_contamination_rate = max(missed_contamination_rate)
        avg_missed_contamination_rate = sum(missed_contamination_rate) / len(
            missed_contamination_rate
        )
    else:
        false_negative_present = False
        max_missed_contamination_rate = 0
        avg_missed_contamination_rate = 0

    if success_rates.true_positive:
        true_positive_present = True
        max_intercepted_contamination_rate = max(intercepted_contamination_rate)
        avg_intercepted_contamination_rate = sum(intercepted_contamination_rate) / len(
            intercepted_contamination_rate
        )
        pct_contaminant_unreported_if_detection = (
            1
            - (total_contaminated_items_detection / total_contaminated_items_completion)
        ) * 100
    else:
        true_positive_present = False
        max_intercepted_contamination_rate = 0
        avg_intercepted_contamination_rate = 0
        pct_contaminant_unreported_if_detection = 0

    simulation_results = types.SimpleNamespace(
        seed=seed,
        missing=missing,
        false_neg=false_neg,
        missed_within_tolerance=missed_within_tolerance,
        intercepted=success_rates.true_positive,
        num_inspections=num_inspections,
        total_num_boxes=total_num_boxes,
        total_num_items=total_num_items,
        avg_boxes_opened_completion=total_boxes_opened_completion / num_consignments,
        avg_boxes_opened_detection=total_boxes_opened_detection / num_consignments,
        pct_boxes_opened_completion=(
            (total_boxes_opened_completion / total_num_boxes) * 100
        ),
        pct_boxes_opened_detection=(
            (total_boxes_opened_detection / total_num_boxes) * 100
        ),
        avg_items_inspected_completion=total_items_inspected_completion
        / num_consignments,
        avg_items_inspected_detection=total_items_inspected_detection
        / num_consignments,
        pct_items_inspected_completion=(
            (total_items_inspected_completion / total_num_items) * 100
        ),
        pct_items_inspected_detection=(
            (total_items_inspected_detection / total_num_items) * 100
        ),
        pct_contaminant_unreported_if_detection=pct_contaminant_unreported_if_detection,
        true_contamination_rate=true_contamination_rate / num_consignments,
        max_missed_contamination_rate=max_missed_contamination_rate,
        avg_missed_contamination_rate=avg_missed_contamination_rate,
        max_intercepted_contamination_rate=max_intercepted_contamination_rate,
        avg_intercepted_contamination_rate=avg_intercepted_contamination_rate,
        false_negative_present=false_negative_present,
        true_positive_present=true_positive_present,
        total_intercepted_contaminants=total_intercepted_contaminants,
        total_missed_contaminants=total_missed_contaminants,
        relative_missed_contaminants=(
            total_missed_contaminants / total_contaminants
            if total_contaminants
            else 0  # Using 0 as in "no contaminants, so none missed"
        ),
        relative_intercepted_contaminants=(
            total_intercepted_contaminants / total_contaminants
            if total_contaminants
            else 0  # Using 0 as in "no contaminants, so none intercepted"
        ),
        total_contaminants=total_contaminants,

        # Added fields (were in first simulation_results but not here), defaulting to 0
        total_num_inspection_units=0,
        total_num_sample_units=0,
        total_num_plants=0,
        avg_inspection_units_opened_completion=0,
        avg_inspection_units_opened_detection=0,
        pct_inspection_units_opened_completion=0,
        pct_inspection_units_opened_detection=0,
        avg_sample_units_inspected_completion=0,
        avg_sample_units_inspected_detection=0,
        pct_sample_units_inspected_completion=0,
        pct_sample_units_inspected_detection=0,
        avg_plant_units_inspected_completion=0,
        avg_plant_units_inspected_detection=0,
        pct_plant_units_inspected_completion=0,
        pct_plant_units_inspected_detection=0,
        total_contaminated_units=0,
        total_contaminated_sample_units=0,
        total_contaminated_inspection_units=0,
        total_intercepted_inspection_units=0,
        total_slipped_inspection_units=0,
        total_slipped_units=0,
        total_slipped_sample_units=0,
        avg_slipped_units_per_consignment=0,
        avg_slipped_sample_units_per_consignment=0,
    )

    if detailed:
        simulation_results.details = [item_details, inspected_item_details]

    return simulation_results




def simulation_pis(
    config,
    num_consignments,
    seed,
    rng=None,
    rng_inspection=None,
    output_f280_file=None,
    verbose=False,
    pretty=None,
    detailed=False,
    output_dir_rep=None,
    shipment_progress_callback: Optional[Callable[[int, int], None]] = None,
    sim_rep: int | bool = None
):
    """Simulate consignments, their contamination, and inspection.

    This function runs a single simulation replication. For each consignment,
    it:

    1. Generates a consignment using the configured generator.
    2. Applies contamination using the configured contaminant function.
    3. Synchronizes contamination from plant-level truth up to sample and
       inspection-unit arrays.
    4. Decides whether inspection is needed.
    5. If inspection occurs, selects units to inspect, performs inspection,
       and records detection statistics.
    6. Accumulates totals and RBS-specific metrics.

    At the end, aggregated metrics are returned as a SimpleNamespace, with
    optional detailed per-consignment records.

    Args:
        config: Full simulation configuration dictionary.
        num_consignments: Number of consignments (shipments) to simulate.
        rng: numpy.random.Generator for contamination and generation.
        rng_inspection: numpy.random.Generator for inspection sampling.
        output_f280_file: Optional filename/path for F280 CSV output.
        verbose: If True, print messages about each consignment via reporter.
        pretty: Optional pretty-print style for consignments (see
            :func:`pretty_consignment`).
        detailed: If True, attach detailed per-consignment records to the
            returned namespace.
        output_dir_rep: Optional directory for writing replication-level
            synthetic data (PIS/RBS/consignment CSVs).
        shipment_progress_callback: Optional callback that receives
            ``(processed, total)`` consignments after each iteration.
        sim_rep: Optional replication index; if provided and
            ``use_rep_consignments`` is enabled upstream, may select a
            specific synthetic input file.

    Returns:
        SimpleNamespace with aggregated simulation metrics such as:
        * missing, false_neg, missed_within_tolerance, intercepted,
        * total_num_inspection_units, total_num_sample_units, total_num_plants,
        * averages and percentages of inspected units and contaminants,
        * additional RBS-related metrics (slippage counts and rates).

        If ``detailed`` is True, a ``details`` attribute is added containing
        lists of sample-unit details and detection records.
    """
    # pylint: disable=too-many-locals,too-many-branches,too-many-statements

    pis_sim_data = PISSimData(output_dir_rep=output_dir_rep, config=config)

    # allow for an empty disposition code specification
    disposition_codes = config.get("disposition_codes", {})
    form280 = Form280(output_f280_file, disposition_codes=disposition_codes)
    if verbose:
        reporter = PrintReporter()
    else:
        reporter = MuteReporter()
    success_rates = SuccessRates(reporter)
    missed_within_tolerance = 0
    num_inspections = 0
    total_num_inspection_units = 0
    total_num_sample_units = 0
    total_num_plants = 0
    total_inspection_units_opened_completion = 0
    total_inspection_units_opened_detection = 0
    total_sample_units_inspected_completion = 0
    total_sample_units_inspected_detection = 0
    total_plant_units_inspected_completion = 0
    total_plant_units_inspected_detection = 0
    total_contaminated_sample_units_completion = 0
    total_contaminated_sample_units_detection = 0
    total_contaminated_units_all = 0
    total_contaminated_sample_units_all = 0
    total_contaminated_inspection_units_all = 0
    total_intercepted_inspection_units = 0
    total_slipped_inspection_units = 0
    true_contamination_rate = 0
    intercepted_contamination_rate = []
    missed_contamination_rate = []
    total_intercepted_contaminants = 0
    total_missed_contaminants = 0
    seed = 0
    total_num_boxes = 0
    total_num_items = 0
    avg_boxes_opened_completion = 0
    avg_boxes_opened_detection = 0
    pct_boxes_opened_completion = 0
    pct_boxes_opened_detection = 0
    avg_items_inspected_completion = 0
    avg_items_inspected_detection = 0
    pct_items_inspected_completion = 0
    pct_items_inspected_detection = 0
    relative_missed_contaminants = 0
    relative_intercepted_contaminants = 0
    total_contaminants = 0
    if detailed:
        sample_unit_details = []
        inspected_sample_unit_details = []
        inspection_unit_detection_records = []

    if sim_rep is not None:
        config["consignment"]["input_file"][
            "file_name"] = f"development_files/slippage_data/rep_synthetic_data/Synthetic_Base_Use_rep_{sim_rep}.csv"

    consignment_generator = get_consignment_generator(config)
    add_contaminant = get_contaminant_function(
        config=config,
        rng=rng
    )
    is_inspection_needed = get_inspection_needed_function(config)
    sample = get_sample_function(
        config=config,
        rng=rng
    )
    tolerance_level = config["inspection"]["tolerance_level"]

    # Dictionary to capture additional metrics per consignment
    rbs_additional_metrics = {}

    prop = 0
    increment = 0.1
    if shipment_progress_callback is not None:
        shipment_progress_callback(0, num_consignments)

    for i in range(num_consignments):
        if i == int(prop*num_consignments):
            percent_complete = int(prop*100)
            print(f'   {percent_complete}% complete ({i+1} out of {num_consignments} consignments)')
            prop += increment
        try:
            consignment = consignment_generator.generate_consignment()
            #print(f"   Generated consignment with {consignment.num_inspection_units} inspection units and {consignment.num_sample_units} sample units")
            #print("   Starting contamination...")
            add_contaminant(consignment)
            synchronize_contamination_arrays_from_plants(consignment)
            #print("   Finished contamination.")
            total_contaminated_units = 0
            total_contaminated_inspection_units = 0
            total_contaminated_sample_units = 0

            inspection_unit_counter = 0
            inspection_units_contaminated = {}
            for inspect_unit in consignment.inspection_units:
                indicator = 0
                sample_unit_counter = 0
                sample_units_contaminated = {}
                for samp_unit in inspect_unit.included_unit_objects:
                    if sum(samp_unit.plants)> 0:
                        plants_contaminated = []
                        for plant_unit in range(len(samp_unit.plants)):
                            if samp_unit.plants[plant_unit] == 1:
                                plants_contaminated.append(plant_unit)
                        sample_units_contaminated[sample_unit_counter] = plants_contaminated
                        indicator = 1
                        total_contaminated_sample_units += 1
                    total_contaminated_units += sum(samp_unit.plants)
                    sample_unit_counter += 1
                if indicator == 1:
                    inspection_units_contaminated[inspection_unit_counter] = sample_units_contaminated
                    total_contaminated_inspection_units += 1
                inspection_unit_counter+=1

            pis_sim_data.add_consignment(consignment)
            if detailed:
                for inspection_unit in consignment.inspection_units:
                    sample_unit_details.append(inspection_unit.included_units)
            if pretty:
                pretty_config = config.get("pretty", {})
                print(pretty_consignment(consignment, style=pretty, config=pretty_config))

            must_inspect, applied_program = is_inspection_needed(
                consignment, consignment.date
            )
            if must_inspect:
                n_units_to_inspect = sample(consignment)
                ret = inspect(config, consignment, n_units_to_inspect, detailed, rng=rng_inspection)
                pis_sim_data.add_to_pis_synthetic_data(ret, consignment, n_units_to_inspect)
                consignment_checked_ok = ret.consignment_checked_ok
                num_inspections += 1
                total_num_inspection_units += consignment.num_inspection_units
                total_num_sample_units += consignment.num_sample_units
                if consignment.num_plants is not None:
                    total_num_plants += consignment.num_plants
                total_inspection_units_opened_completion += ret.inspection_units_opened_completion
                total_inspection_units_opened_detection += ret.inspection_units_opened_detection
                total_sample_units_inspected_completion += ret.sample_units_inspected_completion
                total_sample_units_inspected_detection += ret.sample_units_inspected_detection
                total_plant_units_inspected_completion += ret.plant_units_inspected_completion
                total_plant_units_inspected_detection += ret.plant_units_inspected_detection
                total_contaminated_sample_units_completion += ret.contaminated_sample_units_completion
                total_contaminated_sample_units_detection += ret.contaminated_sample_units_detection
                total_contaminated_units_all += total_contaminated_units
                total_contaminated_sample_units_all += total_contaminated_sample_units
                total_contaminated_inspection_units_all += total_contaminated_inspection_units
                if detailed:
                    inspected_sample_unit_details.append(ret.inspected_sample_unit_indexes)
            else:
                consignment_checked_ok = True  # assuming or hoping it's ok
                total_num_inspection_units += consignment.num_inspection_units
                total_num_sample_units += consignment.num_sample_units
                if consignment.num_plants is not None:
                    total_num_plants += consignment.num_plants

            for inspection_unit in consignment.inspection_units:
                is_infected = bool(getattr(inspection_unit, "is_infected", bool(inspection_unit)))
                is_detected = bool(getattr(inspection_unit, "is_detected", False))
                if is_infected:
                    if is_detected:
                        total_intercepted_inspection_units += 1
                    else:
                        total_slipped_inspection_units += 1

            if detailed:
                sample_unit_to_inspection = getattr(consignment, "sample_unit_to_inspection_unit", {}) or {}
                inspected_sample_unit_indexes = (
                    ret.inspected_sample_unit_indexes if must_inspect else []
                )
                inspected_counts_by_inspection_unit = Counter()
                for sample_unit_index in inspected_sample_unit_indexes:
                    inspection_unit_index = sample_unit_to_inspection.get(
                        sample_unit_index,
                        consignment.get_inspection_unit_and_sample_unit_index(sample_unit_index)[0],
                    )
                    inspected_counts_by_inspection_unit[inspection_unit_index] += 1

                for inspection_unit_index, inspection_unit in enumerate(consignment.inspection_units):
                    sample_unit_objects = getattr(inspection_unit, "included_unit_objects", [])
                    num_plants_in_inspection_unit = sum(len(su.plants) for su in sample_unit_objects)
                    infected_plants_in_inspection_unit = sum(
                        int(np.count_nonzero(su.plants)) for su in sample_unit_objects
                    )
                    risk_unit_id = None
                    risk_unit_ids = getattr(inspection_unit, "risk_unit_ids", None)
                    if risk_unit_ids:
                        risk_unit_id = risk_unit_ids[0]

                    is_infected = bool(getattr(inspection_unit, "is_infected", bool(inspection_unit)))
                    is_detected = bool(getattr(inspection_unit, "is_detected", False))
                    inspection_unit_detection_records.append(
                        {
                            "consignment_index": i + 1,
                            "inspection_number": getattr(consignment, "inspection_number", None),
                            "inspection_unit_id": getattr(inspection_unit, "inspection_print_id", None),
                            "risk_unit_id": risk_unit_id,
                            "num_sample_units": getattr(inspection_unit, "num_sample_units", len(sample_unit_objects)),
                            "num_plants": num_plants_in_inspection_unit,
                            "infected_plants": infected_plants_in_inspection_unit,
                            "is_infected": is_infected,
                            "is_detected": is_detected,
                            "missed": bool(is_infected and not is_detected),
                            "was_inspected": bool(
                                must_inspect and inspected_counts_by_inspection_unit[inspection_unit_index] > 0
                            ),
                            "inspected_sample_units": int(inspected_counts_by_inspection_unit[inspection_unit_index]),
                        }
                    )

            form280.fill(
                consignment.date,
                consignment,
                consignment_checked_ok,
                must_inspect,
                applied_program,
            )
            consignment_actually_ok = total_contaminated_units == 0
            success_rates.record_success_rate(
                consignment_checked_ok, consignment_actually_ok, consignment
            )
            true_contamination_rate += consignment_contamination_rate(consignment)
            if not consignment_actually_ok:
                if consignment_checked_ok:
                    if consignment_contamination_rate(consignment) < tolerance_level:
                        missed_within_tolerance += 1
                    missed_contamination_rate.append(
                        consignment_contamination_rate(consignment)
                    )
                    total_missed_contaminants += consignment.count_contaminated()
                else:
                    intercepted_contamination_rate.append(
                        consignment_contamination_rate(consignment)
                    )
                    total_intercepted_contaminants += consignment.count_contaminated()

            # Add tracking of additional RBS metrics
            rbs_additional_metrics[i] = {
                'number_missed_units': ret.number_units_missed,
                'number_missed_sample_units': ret.number_sample_units_missed,
                'total_plants_on_consignment': len(consignment.plants),
            }
        except RuntimeError as e:
            print(f"Stopped simulation early: {e}")
            pass
        finally:
            if shipment_progress_callback is not None:
                shipment_progress_callback(i + 1, num_consignments)

    # Write out simulated data
    pis_sim_data.finalize_dataframes()
    pis_sim_data.write_synthetic_data_to_csv()

    num_contaminated = num_consignments - success_rates.ok
    if num_contaminated:
        # avoiding float division by zero
        missing = 100 * float(success_rates.false_negative) / (num_contaminated)
        false_neg = success_rates.false_negative
        if verbose:
            print(f"Missing {missing:.0f}% of contaminated consignments.")
    else:
        # we didn't miss anything
        missing = 0
        false_neg = 0

    if success_rates.false_negative:
        false_negative_present = True
        max_missed_contamination_rate = max(missed_contamination_rate)
        avg_missed_contamination_rate = sum(missed_contamination_rate) / len(
            missed_contamination_rate
        )
    else:
        false_negative_present = False
        max_missed_contamination_rate = 0
        avg_missed_contamination_rate = 0

    if success_rates.true_positive:
        true_positive_present = True
        max_intercepted_contamination_rate = max(intercepted_contamination_rate)
        avg_intercepted_contamination_rate = sum(intercepted_contamination_rate) / len(
            intercepted_contamination_rate
        )
        pct_contaminant_unreported_if_detection = (
            1
            - (total_contaminated_sample_units_detection / total_contaminated_sample_units_completion)
        ) * 100
    else:
        true_positive_present = False
        max_intercepted_contamination_rate = 0
        avg_intercepted_contamination_rate = 0
        pct_contaminant_unreported_if_detection = 0

    ##############################
    ### Additional rbs metrics ###
    ##############################
    total_slipped_units = 0
    total_slipped_sample_units = 0
    avg_slipped_units_per_consignment = 0
    avg_slipped_sample_units_per_consignment= 0
    for consignment in rbs_additional_metrics.keys():
        # Contributing to "Average Total Slippage"
        total_slipped_units += rbs_additional_metrics[consignment]['number_missed_units']
        total_slipped_sample_units  += rbs_additional_metrics[consignment]['number_missed_sample_units']
        avg_slipped_units_per_consignment += rbs_additional_metrics[consignment]['number_missed_units']/rbs_additional_metrics[consignment]['total_plants_on_consignment']
        avg_slipped_sample_units_per_consignment += rbs_additional_metrics[consignment]['number_missed_sample_units']/rbs_additional_metrics[consignment]['total_plants_on_consignment']

    avg_slipped_units_per_consignment /= num_consignments
    avg_slipped_sample_units_per_consignment /= num_consignments

    simulation_results = types.SimpleNamespace(
        missing=missing,
        false_neg=false_neg,
        missed_within_tolerance=missed_within_tolerance,
        intercepted=success_rates.true_positive,
        num_inspections=num_inspections,
        total_num_inspection_units=total_num_inspection_units,
        total_num_sample_units=total_num_sample_units,
        total_num_plants=total_num_plants,
        avg_inspection_units_opened_completion=total_inspection_units_opened_completion / num_consignments,
        avg_inspection_units_opened_detection=total_inspection_units_opened_detection / num_consignments,
        pct_inspection_units_opened_completion=(
            (total_inspection_units_opened_completion / total_num_inspection_units) * 100
        ),
        pct_inspection_units_opened_detection=(
            (total_inspection_units_opened_detection / total_num_inspection_units) * 100
        ),
        avg_sample_units_inspected_completion=total_sample_units_inspected_completion
        / num_consignments,
        avg_sample_units_inspected_detection=total_sample_units_inspected_detection
        / num_consignments,
        pct_sample_units_inspected_completion=(
            (total_sample_units_inspected_completion / total_num_sample_units) * 100
        ),
        pct_sample_units_inspected_detection=(
            (total_sample_units_inspected_detection / total_num_sample_units) * 100
        ),
        avg_plant_units_inspected_completion=total_plant_units_inspected_completion / num_consignments,
        avg_plant_units_inspected_detection=total_plant_units_inspected_detection / num_consignments,
        pct_plant_units_inspected_completion=(
            (total_plant_units_inspected_completion / total_num_plants) * 100
        ),
        pct_plant_units_inspected_detection=(
            (total_plant_units_inspected_detection / total_num_plants) * 100
        ),
        total_contaminated_units=total_contaminated_units_all,
        total_contaminated_sample_units=total_contaminated_sample_units_all,
        total_contaminated_inspection_units=total_contaminated_inspection_units_all,
        total_intercepted_inspection_units=total_intercepted_inspection_units,
        total_slipped_inspection_units=total_slipped_inspection_units,
        pct_contaminant_unreported_if_detection=pct_contaminant_unreported_if_detection,
        true_contamination_rate=true_contamination_rate / num_consignments,
        max_missed_contamination_rate=max_missed_contamination_rate,
        avg_missed_contamination_rate=avg_missed_contamination_rate,
        max_intercepted_contamination_rate=max_intercepted_contamination_rate,
        avg_intercepted_contamination_rate=avg_intercepted_contamination_rate,
        false_negative_present=false_negative_present,
        true_positive_present=true_positive_present,
        total_intercepted_contaminants=total_intercepted_contaminants,
        total_missed_contaminants=total_missed_contaminants,
        total_slipped_units=total_slipped_units,
        total_slipped_sample_units = total_slipped_sample_units,
        avg_slipped_units_per_consignment = avg_slipped_units_per_consignment,
        avg_slipped_sample_units_per_consignment = avg_slipped_sample_units_per_consignment,
        seed=seed,
        total_num_boxes=total_num_boxes,
        total_num_items=total_num_items,
        avg_boxes_opened_completion=avg_boxes_opened_completion,
        avg_boxes_opened_detection=avg_boxes_opened_detection,
        pct_boxes_opened_completion=pct_boxes_opened_completion,
        pct_boxes_opened_detection=pct_boxes_opened_detection,
        avg_items_inspected_completion=avg_items_inspected_completion,
        avg_items_inspected_detection=avg_items_inspected_detection,
        pct_items_inspected_completion=pct_items_inspected_completion,
        pct_items_inspected_detection=pct_items_inspected_detection,
        relative_missed_contaminants=relative_missed_contaminants,
        relative_intercepted_contaminants=relative_intercepted_contaminants,
        total_contaminants=total_contaminants,
    )
    if detailed:
        simulation_results.details = [
            sample_unit_details,
            inspected_sample_unit_details,
            inspection_unit_detection_records,
        ]

    return simulation_results


def run_simulation(
    config,
    num_simulations,
    num_consignments,
    seed=None,
    output_f280_file=None,
    verbose=False,
    pretty=None,
    detailed=False,
    individual=False,
    rngs=None,
    rngs_inspections=None,
    output_dir=None,
    progress_callback: Optional[Callable[[int, int, int, int], None]] = None,
    use_rep_consignments: bool = False,
):
    """Run the simulation function multiple times and aggregate results.

    This function runs :func:`simulation` ``num_simulations`` times and
    accumulates/averages the metrics returned from each replication. It also
    computes replication-level RBS metrics and confidence intervals.

    Args:
        config: Full configuration dictionary.
        num_simulations: Number of simulation replications.
        num_consignments: Number of consignments per replication.
        rngs: Optional sequence of numpy.random.Generator instances, one per
            replication for generation/contamination. If None, new generators
            are created.
        rngs_inspections: Optional sequence of Generators for inspection. If
            ``rngs`` is None, default inspection generators are created.
        output_f280_file: Optional F280 output filename/path.
        verbose: If True, enable verbose logging inside :func:`simulation`.
        pretty: Optional pretty-print style for consignments.
        detailed: If True, also return per-consignment details from the first
            replication.
        output_dir: Root directory for writing replication-level output
            (each replication gets its own subdirectory).
        progress_callback: Optional callback receiving
            ``(replications_done, num_simulations, consignments_done, num_consignments)``.
        use_rep_consignments: If True, reuse fixed synthetic consignments per
            replication when reading from ``input_file``.

    Returns:
        If ``detailed`` is False, a SimpleNamespace ``totals`` with aggregated
        metrics across replications. If ``detailed`` is True, a tuple
        ``(details, totals)`` where ``details`` comes from the first replication.
    """
    if rngs is None:
        rngs = [np.random.default_rng() for _ in range(num_simulations)]
        rngs_inspections = [np.random.default_rng(50) for _ in range(num_simulations)]
    else:
        assert len(rngs) == num_simulations, "rngs must have one RNG per simulation"

    # pylint: disable=too-many-branches,too-many-statements

    totals = types.SimpleNamespace(
        missing=0,
        false_neg=0,
        missed_within_tolerance=0,
        intercepted=0,
        num_inspections=0,
        num_boxes=0,
        num_items=0,
        avg_boxes_opened_completion=0,
        avg_boxes_opened_detection=0,
        pct_boxes_opened_completion=0,
        pct_boxes_opened_detection=0,
        avg_items_inspected_completion=0,
        avg_items_inspected_detection=0,
        pct_items_inspected_completion=0,
        pct_items_inspected_detection=0,
        relative_missed_contaminants=0,
        relative_intercepted_contaminants=0,
        total_contaminants=0,
        num_inspection_units=0,
        num_sample_units=0,
        num_plants=0,
        avg_inspection_units_opened_completion=0,
        avg_inspection_units_opened_detection=0,
        pct_inspection_units_opened_completion=0,
        pct_inspection_units_opened_detection=0,
        avg_sample_units_inspected_completion=0,
        avg_sample_units_inspected_detection=0,
        pct_sample_units_inspected_completion=0,
        pct_sample_units_inspected_detection=0,
        avg_plant_units_inspected_completion=0,
        avg_plant_units_inspected_detection=0,
        pct_plant_units_inspected_completion=0,
        pct_plant_units_inspected_detection=0,
        pct_contaminant_unreported_if_detection=0,
        true_contamination_rate=0,
        max_missed_contamination_rate=0,
        avg_missed_contamination_rate=0,
        max_intercepted_contamination_rate=0,
        avg_intercepted_contamination_rate=0,
        false_negative_present=0,
        true_positive_present=0,
        total_intercepted_contaminants=0,
        total_missed_contaminants=0,
        total_slipped_units=0,
        total_unit_slippage_rate=0,
        total_slipped_sample_units=0,
        avg_slipped_units_per_consignment=0,
        avg_slipped_sample_units_per_consignment=0,
        min_slipped_units=0,
        max_slipped_units=0,
        percentile_90_slipped_units=0,
        min_max_spread_slipped_units=0,
        median_slipped_units=0,
        std_slipped_units=0,
        lower_95_ci_total_slipped_units=0,
        upper_95_ci_total_slipped_units=0,
        total_contaminated_units=0,
        total_contaminated_sample_units=0,
        total_contaminated_inspection_units=0,
        total_intercepted_inspection_units=0,
        total_slipped_inspection_units=0,
    )
    if individual:
        individual_results = []

    ##############################
    ### Additional rbs metrics ###
    ##############################
    # Define a dictionary to store each replication output
    sim_rep_outputs = {}

    if progress_callback is not None:
        progress_callback(0, num_simulations, 0, num_consignments)

    for i in range(num_simulations):
        print(f'\n\n======================================================================')
        print(f'======= RUNNING REPLICATION {i + 1} OUT OF {num_simulations} =========')
        print(f'======================================================================')


        if output_dir is not None:
            # Define output replication directory for the simulated data
            output_dir_rep = output_dir / f"rep_{i}"
            output_dir_rep.mkdir(parents=True, exist_ok=True)
        else:
            output_dir_rep = None

        rng = rngs[i]
        rng_inspection = rngs_inspections[i]

        if use_rep_consignments:
            sim_rep = i
        else:
            sim_rep = None

        if (config.get("inspection_process", None) is not None) and (config['inspection_process'] == "RBS-PIS"):
            result = simulation_pis(
                config=config,
                num_consignments=num_consignments,
                seed=seed,
                rng=rng,
                rng_inspection=rng_inspection,
                output_f280_file=output_f280_file,
                verbose=verbose,
                pretty=pretty,
                detailed=detailed,
                output_dir_rep=output_dir_rep,
                shipment_progress_callback=(
                    lambda processed, total, replication_index=i: progress_callback(
                        replication_index + 1,
                        num_simulations,
                        processed,
                        total,
                    )
                ) if progress_callback is not None else None,
                sim_rep=sim_rep if sim_rep is not None else None
            )
            if progress_callback is not None:
                progress_callback(i + 1, num_simulations, num_consignments, num_consignments)
        else:
            result = simulation(
                config=config,
                num_consignments=num_consignments,
                seed=seed + i if seed is not None else None,
                output_f280_file=output_f280_file,
                verbose=verbose,
                pretty=pretty,
                detailed=detailed,
            )

        ##############################
        ### Additional rbs metrics ###
        ##############################

        if detailed and i == 0:
            # details are from first run of simulation only
            details = result.details
        else:
            details = None
        if individual:
            individual_results.append(result)

        # totals are an average of all simulation runs
        totals.missing += result.missing
        totals.false_neg += result.false_neg
        totals.missed_within_tolerance += result.missed_within_tolerance
        totals.intercepted += result.intercepted
        totals.num_inspections += result.num_inspections
        totals.num_boxes += result.total_num_boxes
        totals.num_items += result.total_num_items
        totals.avg_boxes_opened_completion += result.avg_boxes_opened_completion
        totals.avg_boxes_opened_detection += result.avg_boxes_opened_detection
        totals.pct_boxes_opened_completion += result.pct_boxes_opened_completion
        totals.pct_boxes_opened_detection += result.pct_boxes_opened_detection
        totals.avg_items_inspected_completion += result.avg_items_inspected_completion
        totals.avg_items_inspected_detection += result.avg_items_inspected_detection
        totals.pct_items_inspected_completion += result.pct_items_inspected_completion
        totals.pct_items_inspected_detection += result.pct_items_inspected_detection
        totals.pct_contaminant_unreported_if_detection += (
            result.pct_contaminant_unreported_if_detection
        )
        totals.true_contamination_rate += result.true_contamination_rate
        totals.max_missed_contamination_rate += result.max_missed_contamination_rate
        totals.avg_missed_contamination_rate += result.avg_missed_contamination_rate
        totals.max_intercepted_contamination_rate += (
            result.max_intercepted_contamination_rate
        )
        totals.avg_intercepted_contamination_rate += (
            result.avg_intercepted_contamination_rate
        )
        totals.false_negative_present += result.false_negative_present
        totals.true_positive_present += result.true_positive_present
        totals.total_intercepted_contaminants += result.total_intercepted_contaminants
        totals.total_missed_contaminants += result.total_missed_contaminants
        totals.relative_missed_contaminants += result.relative_missed_contaminants
        totals.relative_intercepted_contaminants += (
            result.relative_intercepted_contaminants
        )
        totals.total_contaminants += result.total_contaminants
        # make these relative (reusing the variables)


        # totals are an average of all simulation runs
        totals.num_inspection_units += result.total_num_inspection_units
        totals.num_sample_units += result.total_num_sample_units
        totals.num_plants += result.total_num_plants
        totals.avg_inspection_units_opened_completion += result.avg_inspection_units_opened_completion
        totals.avg_inspection_units_opened_detection += result.avg_inspection_units_opened_detection
        totals.pct_inspection_units_opened_completion += result.pct_inspection_units_opened_completion
        totals.pct_inspection_units_opened_detection += result.pct_inspection_units_opened_detection
        totals.avg_sample_units_inspected_completion += result.avg_sample_units_inspected_completion
        totals.avg_sample_units_inspected_detection += result.avg_sample_units_inspected_detection
        totals.pct_sample_units_inspected_completion += result.pct_sample_units_inspected_completion
        totals.pct_sample_units_inspected_detection += result.pct_sample_units_inspected_detection
        totals.pct_plant_units_inspected_completion += result.pct_plant_units_inspected_completion
        totals.pct_plant_units_inspected_detection += result.pct_plant_units_inspected_detection

        ##############################
        ### Additional rbs metrics ###
        ##############################
        totals.total_slipped_units += result.total_slipped_units
        if result.total_num_plants >0:
            totals.total_unit_slippage_rate += (result.total_slipped_units/result.total_num_plants)
        else:
            totals.total_unit_slippage_rate += 0.0
        totals.total_slipped_sample_units += result.total_slipped_sample_units
        totals.avg_slipped_units_per_consignment += result.avg_slipped_units_per_consignment
        totals.avg_slipped_sample_units_per_consignment += result.avg_slipped_sample_units_per_consignment
        totals.total_contaminated_units += result.total_contaminated_units
        totals.total_contaminated_sample_units += result.total_contaminated_sample_units
        totals.total_contaminated_inspection_units += result.total_contaminated_inspection_units
        totals.total_intercepted_inspection_units += result.total_intercepted_inspection_units
        totals.total_slipped_inspection_units += result.total_slipped_inspection_units
        totals.avg_plant_units_inspected_completion += result.avg_plant_units_inspected_completion
        totals.avg_plant_units_inspected_detection += result.avg_plant_units_inspected_detection

        sim_rep_outputs[f'Rep_{i}'] = {}
        sim_rep_outputs[f'Rep_{i}']['replication'] = i
        sim_rep_outputs[f'Rep_{i}']['intercepted'] = result.intercepted
        sim_rep_outputs[f'Rep_{i}']['false_neg'] = result.false_neg
        sim_rep_outputs[f'Rep_{i}']['missing'] = result.missing
        sim_rep_outputs[f'Rep_{i}']['missed_within_tolerance'] = result.missed_within_tolerance
        sim_rep_outputs[f'Rep_{i}']['num_inspections'] = result.num_inspections
        sim_rep_outputs[f'Rep_{i}']['total_slipped_units'] = result.total_slipped_units
        if result.total_num_plants>0:
            sim_rep_outputs[f'Rep_{i}']['total_unit_slippage_rate'] = (result.total_slipped_units/result.total_num_plants)
        else:
            sim_rep_outputs[f'Rep_{i}']['total_unit_slippage_rate'] = 0.0
        sim_rep_outputs[f'Rep_{i}']['total_slipped_sample_units'] = result.total_slipped_sample_units
        sim_rep_outputs[f'Rep_{i}']['avg_slipped_units_per_consignment'] = result.avg_slipped_units_per_consignment
        sim_rep_outputs[f'Rep_{i}']['avg_slipped_sample_units_per_consignment'] = result.avg_slipped_sample_units_per_consignment
        sim_rep_outputs[f'Rep_{i}']['total_contaminated_units'] = result.total_contaminated_units
        sim_rep_outputs[f'Rep_{i}']['total_contaminated_sample_units'] = result.total_contaminated_sample_units
        sim_rep_outputs[f'Rep_{i}']['total_contaminated_inspection_units'] = result.total_contaminated_inspection_units
        sim_rep_outputs[f'Rep_{i}']['total_intercepted_inspection_units'] = result.total_intercepted_inspection_units
        sim_rep_outputs[f'Rep_{i}']['total_slipped_inspection_units'] = result.total_slipped_inspection_units
        sim_rep_outputs[f'Rep_{i}']['num_plants'] = result.total_num_plants
        sim_rep_outputs[f'Rep_{i}']['num_sample_units'] = result.total_num_sample_units
        sim_rep_outputs[f'Rep_{i}']['num_inspection_units'] = result.total_num_inspection_units
        sim_rep_outputs[f'Rep_{i}']['avg_plant_units_inspected_completion'] = result.avg_plant_units_inspected_completion
        sim_rep_outputs[f'Rep_{i}']['avg_sample_units_inspected_completion'] = result.avg_sample_units_inspected_completion
        sim_rep_outputs[f'Rep_{i}']['avg_inspection_units_opened_completion'] = result.avg_inspection_units_opened_completion
        sim_rep_outputs[f'Rep_{i}']['pct_plant_units_inspected_completion'] = result.pct_plant_units_inspected_completion
        sim_rep_outputs[f'Rep_{i}']['pct_sample_units_inspected_completion'] = result.pct_sample_units_inspected_completion
        sim_rep_outputs[f'Rep_{i}']['pct_inspection_units_opened_completion'] = result.pct_inspection_units_opened_completion

    # make these relative (reusing the variables)
    totals.missing /= float(num_simulations)
    totals.false_neg /= float(num_simulations)
    totals.missed_within_tolerance /= float(num_simulations)
    totals.intercepted /= float(num_simulations)
    totals.num_inspections /= float(num_simulations)
    totals.num_boxes /= float(num_simulations)
    totals.num_items /= float(num_simulations)
    totals.avg_boxes_opened_completion /= float(num_simulations)
    totals.avg_boxes_opened_detection /= float(num_simulations)
    totals.pct_boxes_opened_completion /= float(num_simulations)
    totals.pct_boxes_opened_detection /= float(num_simulations)
    totals.avg_items_inspected_completion /= float(num_simulations)
    totals.avg_items_inspected_detection /= float(num_simulations)
    totals.pct_items_inspected_completion /= float(num_simulations)
    totals.pct_items_inspected_detection /= float(num_simulations)
    totals.pct_contaminant_unreported_if_detection /= float(num_simulations)
    totals.true_contamination_rate /= float(num_simulations)
    if totals.false_negative_present:
        totals.max_missed_contamination_rate /= float(totals.false_negative_present)
        totals.avg_missed_contamination_rate /= float(totals.false_negative_present)
    else:
        totals.max_missed_contamination_rate = None
        totals.avg_missed_contamination_rate = None
    if totals.true_positive_present:
        totals.max_intercepted_contamination_rate /= float(totals.true_positive_present)
        totals.avg_intercepted_contamination_rate /= float(totals.true_positive_present)
    else:
        totals.max_intercepted_contamination_rate = None
        totals.avg_intercepted_contamination_rate = None
    totals.total_intercepted_contaminants /= float(num_simulations)
    totals.total_missed_contaminants /= float(num_simulations)
    totals.relative_missed_contaminants /= float(num_simulations)
    totals.relative_intercepted_contaminants /= float(num_simulations)
    totals.total_contaminants /= float(num_simulations)




    # Convert the sim replication metric storage to a dataframe for analysis
    df_rep_outputs = pd.DataFrame.from_dict(sim_rep_outputs, orient='index')
    totals.replication_outputs = df_rep_outputs.reset_index(drop=True)

    ##############################
    ### Additional rbs metrics ###
    ##############################
    totals.num_inspection_units /= float(num_simulations)
    totals.num_sample_units /= float(num_simulations)
    totals.avg_inspection_units_opened_completion /= float(num_simulations)
    totals.avg_inspection_units_opened_detection /= float(num_simulations)
    totals.pct_inspection_units_opened_completion /= float(num_simulations)
    totals.pct_inspection_units_opened_detection /= float(num_simulations)
    totals.avg_sample_units_inspected_completion /= float(num_simulations)
    totals.avg_sample_units_inspected_detection /= float(num_simulations)
    totals.pct_sample_units_inspected_completion /= float(num_simulations)
    totals.pct_sample_units_inspected_detection /= float(num_simulations)
    totals.pct_plant_units_inspected_completion /= float(num_simulations)
    totals.pct_plant_units_inspected_detection /= float(num_simulations)
    if totals.num_plants:
        totals.num_plants /= float(num_simulations)
    else:
        totals.num_plants = None
    totals.total_slipped_units /= float(num_simulations)
    totals.total_unit_slippage_rate /= float(num_simulations)
    totals.total_slipped_sample_units /= float(num_simulations)
    totals.avg_slipped_units_per_consignment /= float(num_simulations)
    totals.avg_slipped_sample_units_per_consignment /= float(num_simulations)
    totals.total_contaminated_units /= float(num_simulations)
    totals.total_contaminated_sample_units /= float(num_simulations)
    totals.total_contaminated_inspection_units /= float(num_simulations)
    totals.total_intercepted_inspection_units /= float(num_simulations)
    totals.total_slipped_inspection_units /= float(num_simulations)
    totals.avg_plant_units_inspected_completion /= float(num_simulations)
    totals.avg_plant_units_inspected_detection /= float(num_simulations)

    totals.min_slipped_units = df_rep_outputs['total_slipped_units'].min()
    totals.max_slipped_units = df_rep_outputs['total_slipped_units'].max()
    totals.percentile_90_slipped_units = df_rep_outputs['total_slipped_units'].quantile(0.9)
    totals.min_max_spread_slipped_units = df_rep_outputs['total_slipped_units'].max() - df_rep_outputs['total_slipped_units'].min()

    totals.median_slipped_units = df_rep_outputs['total_slipped_units'].median()
    totals.std_slipped_units = df_rep_outputs['total_slipped_units'].std()

    se = totals.std_slipped_units / math.sqrt(float(num_simulations))  # standard error
    totals.lower_95_ci_total_slipped_units  = totals.total_slipped_units - 1.96 * se
    totals.upper_95_ci_total_slipped_units = totals.total_slipped_units + 1.96 * se

    if individual:
        if detailed:
            return details, totals, individual_results
        else:
            return totals, individual_results
    if detailed:
        # details are items and inspected item from first simulation run only
        # totals are an average of all simulation runs
        return details, totals
    else:
        return totals
