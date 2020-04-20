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
Inspections of shipments in pathways simulation

.. codeauthor:: Vaclav Petras <wenzeslaus gmail com>
"""

from __future__ import print_function, division

import math
import random
import weakref
import numpy as np

from .shipments import get_stems_per_box

if not hasattr(weakref, "finalize"):
    from backports import weakref  # pylint: disable=import-error


def inspect_first(shipment):
    """Inspect only the first box in the shipment"""
    if shipment["boxes"][0]:
        return False, 1
    return True, 1


def inspect_one_random(shipment):
    """Inspect only one randomly picked box in the shipment"""
    if random.choice(shipment["boxes"]):
        return False, 1
    return True, 1


def inspect_all(shipment):
    """Inspect all boxes in the shipment"""
    return not is_shipment_diseased(shipment), shipment["num_boxes"]


def inspect_first_n(num_boxes, shipment):
    """Inspect only the first n boxes in the shipment

    :param num_boxes: Number of boxes to inspect
    :param shipment: Shipment to inspect
    """
    num_boxes = min(len(shipment["boxes"]), num_boxes)
    for i in range(num_boxes):
        if shipment["boxes"][i]:
            return False, i + 1
    return True, num_boxes


def sample_percentage(config, shipment):
    """Set sample size to sample units from shipment using percentage strategy.
    Convert to units to boxes if needed.
    Return number of boxes to inspect.

    :param config: Configuration to be used595
    :param shipment: Shipment to be inspected
    """
    unit = config["inspection"]["unit"]
    ratio = config["inspection"]["percentage"]["proportion"]
    num_stems = shipment["num_stems"]
    num_boxes = shipment["num_boxes"]
    min_boxes = config.get("min_boxes", 1)

    if unit == "stems":
        n_stems_to_inspect = int(math.ceil(ratio * num_stems))
        n_boxes_to_inspect = convert_stems_to_boxes(
            config, shipment, n_stems_to_inspect
        )
    elif unit == "boxes":
        n_boxes_to_inspect = int(math.ceil(ratio * num_boxes))
        n_boxes_to_inspect = max(min_boxes, n_boxes_to_inspect)
        n_boxes_to_inspect = min(num_boxes, n_boxes_to_inspect)
    else:
        raise RuntimeError("Unknown sampling unit: {unit}".format(**locals()))
    return n_boxes_to_inspect


def compute_hypergeometric(population_size, detection_level, confidence_level):
    """Get sample size using hypergeometric distribution

    Compute sample size using hypergeometric distribution based on population
    size (total number of stems or boxes in shipment), detection level,
    and confidence level.
    """
    sample_size = math.ceil(
        (1 - ((1 - confidence_level) ** (1 / (detection_level * population_size))))
        * (population_size - (((detection_level * population_size) - 1) / 2))
    )
    return sample_size


def sample_hypergeometric(config, shipment):
    """Set sample size to sample units from shipment using hypergeometric/detection
    level strategy. Convert to units to boxes if needed.
    Return number of boxes to inspect.

    :param config: Configuration to be used
    :param shipment: Shipment to be inspected
    """
    unit = config["inspection"]["unit"]
    detection_level = config["inspection"]["hypergeometric"]["detection_level"]
    confidence_level = config["inspection"]["hypergeometric"]["confidence_level"]
    num_stems = shipment["num_stems"]
    num_boxes = shipment["num_boxes"]
    min_boxes = config.get("min_boxes", 1)

    if unit == "stems":
        n_stems_to_inspect = compute_hypergeometric(
            num_stems, detection_level, confidence_level
        )
        n_boxes_to_inspect = convert_stems_to_boxes(
            config, shipment, n_stems_to_inspect
        )
    elif unit == "boxes":
        n_boxes_to_inspect = compute_hypergeometric(
            num_boxes, detection_level, confidence_level
        )
        n_boxes_to_inspect = max(min_boxes, n_boxes_to_inspect)
        n_boxes_to_inspect = min(num_boxes, n_boxes_to_inspect)
    else:
        raise RuntimeError("Unknown sampling unit: {unit}".format(**locals()))
    return n_boxes_to_inspect


def sample_all(shipment):
    """Set sample size to sample all boxes from shipment.
    Return number of boxes to inspect.

    :param config: Configuration to be used
    :param shipment: Shipment to be inspected
    """
    n_boxes_to_inspect = shipment["num_boxes"]
    return n_boxes_to_inspect


def sample_n(config, shipment):
    """Set sample size to sample fixed number of units from shipment.
    Check if fixed number is <= max units for inspection. Convert to units to
    boxes if needed.
    Return number of boxes to inspect.

    :param config: Configuration to be used
    :param shipment: Shipment to be inspected
    """
    fixed_n = config["inspection"]["fixed_n"]
    unit = config["inspection"]["unit"]
    within_box_pct = config["inspection"]["within_box_pct"]
    pathway = shipment["pathway"]
    stems_per_box = config["stems_per_box"]
    stems_per_box = get_stems_per_box(stems_per_box, pathway)
    num_stems = shipment["num_stems"]
    num_boxes = shipment["num_boxes"]
    min_boxes = config.get("min_boxes", 1)

    if unit == "stems":
        inspect_per_box = int(math.ceil(within_box_pct * stems_per_box))
        # Compute maximum num of stems that can be inspected in a ship based on
        # within box percent.
        full_box_inspect_stems = math.floor(num_stems / stems_per_box) * inspect_per_box
        partial_box = num_stems % stems_per_box
        partial_box_inspect_stems = min(partial_box, inspect_per_box)
        max_stems = full_box_inspect_stems + partial_box_inspect_stems
        n_stems_to_inspect = min(max_stems, fixed_n)
        # Check if max number of stems that can be inspected is less than fixed number.
        n_boxes_to_inspect = convert_stems_to_boxes(
            config, shipment, n_stems_to_inspect
        )
    elif unit == "boxes":
        n_boxes_to_inspect = fixed_n
        n_boxes_to_inspect = max(min_boxes, n_boxes_to_inspect)
        n_boxes_to_inspect = min(num_boxes, n_boxes_to_inspect)
    return n_boxes_to_inspect


def convert_stems_to_boxes(config, shipment, n_stems_to_inspect):
    """Convert number of stems to inspect to number of boxes to inspect based on
    the percentage of stems to inspect per box and number of stems per box.
    Return number of boxes to inspect.

    :param config: Configuration to be used
    :param shipment: Shipment to be inspected
    :param n_stems_to_inspect: Number of stems to inspect defined in sample functions.
    """
    pathway = shipment["pathway"]
    stems_per_box = config["stems_per_box"]
    stems_per_box = get_stems_per_box(stems_per_box, pathway)
    within_box_pct = config["inspection"]["within_box_pct"]
    min_boxes = config.get("min_boxes", 1)
    num_boxes = shipment["num_boxes"]
    inspect_per_box = int(math.ceil(within_box_pct * stems_per_box))

    # Default inspect all stems per box, but allow partial box inspections
    n_boxes_to_inspect = math.ceil(n_stems_to_inspect / inspect_per_box)
    n_boxes_to_inspect = max(min_boxes, n_boxes_to_inspect)
    n_boxes_to_inspect = min(num_boxes, n_boxes_to_inspect)
    return n_boxes_to_inspect


def inspect(config, shipment, n_boxes_to_inspect):
    """Select boxes from shipment based on specified selection strategy.
    Inspect selected boxes using both end strategies (to detection, to completion)
    Return number of boxes opened, stems inspected, and infested stems found for
    each end strategy.

    :param config: Configuration to be used
    :param shipment: Shipment to be inspected
    :param n_boxes_to_inspect: Number of boxes to inspect defined by sample functions.
    """
    pathway = shipment["pathway"]
    stems_per_box = config["stems_per_box"]
    stems_per_box = get_stems_per_box(stems_per_box, pathway)
    num_boxes = shipment["num_boxes"]
    within_box_pct = config["inspection"]["within_box_pct"]
    inspect_per_box = int(math.ceil(within_box_pct * stems_per_box))

    # Select boxes to inspect
    selection_strategy = config["inspection"]["selection_strategy"]
    if selection_strategy == "tailgate":
        box_index_to_inspect = range(n_boxes_to_inspect)
    elif selection_strategy == "random":
        box_index_to_inspect = random.sample(range(num_boxes), n_boxes_to_inspect)
    else:
        raise RuntimeError(
            "Unknown selection strategy: {selection_strategy}".format(**locals())
        )

    # Inspect selected boxes, count opened boxes, inspected stems, and infested stems
    # to detection and completion
    boxes_opened_completion = n_boxes_to_inspect
    boxes_opened_detection = 0
    stems_inspected_completion = n_boxes_to_inspect * inspect_per_box
    stems_inspected_detection = 0
    infested_stems_completion = 0
    infested_stems_detection = 0
    detected = False
    for i in box_index_to_inspect:
        if not detected:
            boxes_opened_detection += 1
        for stem in (shipment["boxes"][i]).stems[0:inspect_per_box]:
            if not detected:
                stems_inspected_detection += 1
            if stem:  # Count every infested stem in box, to completion within a box
                infested_stems_completion += 1
                if not detected:
                    infested_stems_detection += 1
        if infested_stems_detection > 0:
            detected = True

    return (
        infested_stems_completion == 0,
        boxes_opened_completion,
        boxes_opened_detection,
        stems_inspected_completion,
        stems_inspected_detection,
        infested_stems_completion,
        infested_stems_detection,
    )


def get_sample_function(config):
    """Based on config, return function to sample a shipment.
    """
    sample_strategy = config["inspection"]["sample_strategy"]
    if sample_strategy == "percentage":

        def sample(shipment):
            return sample_percentage(config=config, shipment=shipment)

    elif sample_strategy == "hypergeometric":

        def sample(shipment):
            return sample_hypergeometric(config=config, shipment=shipment)

    elif sample_strategy == "fixed_n":

        def sample(shipment):
            return sample_n(config=config, shipment=shipment)

    elif sample_strategy == "all":

        def sample(shipment):
            return sample_all(shipment=shipment)

    else:
        raise RuntimeError(
            "Unknown sample strategy: {sample_strategy}".format(**locals())
        )
    return sample


def is_flower_of_the_day(cfrp, flower, date):
    """Return True if the flower is FoTD based on naive criteria"""
    i = date.day % len(cfrp)
    if flower == cfrp[i]:
        return True
    return False


def naive_cfrp(config, shipment, date):
    """Decided if the shipment should be expected based on CFRP and size"""
    # returns 2 bools: should_inspect, CFRP applied
    flower = shipment["flower"]
    cfrp = config["flowers"]
    max_boxes = config["max_boxes"]
    # we have flowers in the CFRP, flower is in CFRP, and not too big shipment
    if cfrp and flower in cfrp and shipment["num_boxes"] <= max_boxes:
        if is_flower_of_the_day(cfrp, flower, date):
            return True, "naive_cfrp"  # is FotD, inspect
        return False, "naive_cfrp"  # not FotD, release
    return True, None  # not in CFRP or large, inspect


def inspect_always(shipment, date):  # pylint: disable=unused-argument
    """Inspect always"""
    return True, None


def get_inspection_needed_function(config):
    """Based on config, return function to determine is inspection is needed."""
    if "release_programs" in config:
        if "naive_cfrp" in config["release_programs"]:

            def is_inspection_needed(shipment, date):
                return naive_cfrp(
                    config["release_programs"]["naive_cfrp"], shipment, date
                )

        else:
            raise RuntimeError("Unknown release program: {program}".format(**locals()))
    else:
        is_inspection_needed = inspect_always
    return is_inspection_needed


def is_shipment_diseased(shipment):
    """Return True if at least one box has pest"""
    for box in shipment["boxes"]:
        if box:
            return True
    return False


def shipment_infestation_rate(shipment):
    """Get (true) infestation rate of a shipment

    Infestation rate is here defined as number of
    infested stems divided by the number stems.
    """
    count = np.count_nonzero(shipment["stems"])
    return count / shipment["num_stems"]


def count_diseased_boxes(shipment):
    """Return number of boxes with pest"""
    count = 0
    for box in shipment["boxes"]:
        if box:
            count += 1
    return count


def count_diseased_stems(shipment):
    """Return number of stems with pest"""
    count = np.count_nonzero(shipment["stems"])
    return count
