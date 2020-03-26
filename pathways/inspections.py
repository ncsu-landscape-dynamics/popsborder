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


def inspect_percentage_boxes(config, shipment):
    """Inspect shipments based on the percentage of boxes strategy

    :param config: Configuration to be used
    :param shipment: Shipment to be inspected
    """
    ratio = config["proportion"]
    min_boxes = config.get("min_boxes", 1)
    # closest higher integer
    boxes_to_inspect = int(math.ceil(ratio * len(shipment["boxes"])))
    boxes_to_inspect = max(min_boxes, boxes_to_inspect)
    boxes_to_inspect = min(len(shipment["boxes"]), boxes_to_inspect)

    num_boxes = shipment["num_boxes"]
    selection_strategy = config["selection_strategy"]
    if selection_strategy == "tailgate":
        box_index_to_inspect = range(boxes_to_inspect)
    elif selection_strategy == "random":
        box_index_to_inspect = random.choice(num_boxes, size=boxes_to_inspect, replace=False)
    else:
        raise RuntimeError(
            "Unknown inspection selection strategy: {selection_strategy}".format(**locals())
        )

    end_strategy = config["end_strategy"]
    if end_strategy == "to_completion":
        pest = 0
        for i in box_index_to_inspect:
            if shipment["boxes"][i]:
                pest += 1
        return pest == 0, boxes_to_inspect
    elif end_strategy == "to_detection":
        for i in box_index_to_inspect:
            if shipment["boxes"][i]:
                return False, i + 1
        return True, boxes_to_inspect
    else:
        raise RuntimeError(
            "Unknown inspection end strategy: {end_strategy}".format(**locals())
        )


# TODO: revise pct stems function
def inspect_percentage_stems(config, shipment):
    """Inspect shipments based on the percentage of stems strategy

    :param config: Configuration to be used
    :param shipment: Shipment to be inspected
    """
    ratio = config["proportion"]
    within_box_pct = config["within_box_pct"]
    stems_per_box = shipment["stems_per_box"]
    min_boxes = config.get("min_boxes", 1)
    stems_to_inspect = int(math.ceil(ratio * num_stems))
    # Default inspect all stems per box, but allow partial box inspections
    inspect_per_box = int(math.ceil(within_box_pct * stems_per_box))
    boxes_to_inspect = math.ceil(stems_to_inspect / inspect_per_box)
    boxes_to_inspect = max(min_boxes, boxes_to_inspect)
    boxes_to_inspect = min(len(shipment["boxes"]), boxes_to_inspect)

    num_boxes = shipment["num_boxes"]
    selection_strategy = config["selection_strategy"]
    if selection_strategy == "tailgate":
        box_index_to_inspect = range(boxes_to_inspect)
    elif selection_strategy == "random":
        box_index_to_inspect = random.choice(num_boxes, size=boxes_to_inspect, replace=False)
    else:
        raise RuntimeError(
            "Unknown inspection selection strategy: {selection_strategy}".format(**locals())
        )

    end_strategy = config["end_strategy"]
    if end_strategy == "to_completion":
        pest = 0
        for i in box_index_to_inspect:
            if shipment["boxes"][i]:
                pest += 1
        return pest == 0, boxes_to_inspect
    elif end_strategy == "to_detection":
        for i in box_index_to_inspect:
            if shipment["boxes"][i]:
                return False, i + 1
        return True, boxes_to_inspect
    else:
        raise RuntimeError(
            "Unknown inspection end strategy: {end_strategy}".format(**locals())
        )

# TODO: does this function need shipment parameter?
def get_inspection_function(config):
    """Based on config, return function to inspect a shipment."""
    inspection_strategy = config["inspection"]["strategy"]
    if inspection_strategy == "percentage":
        unit = config["inspection"]["strategy"]["percentage"]["unit"]
        if unit == "boxes":
            def inspect(shipment):
                return inspect_percentage_boxes(
                    config=config["inspection"]["strategy"]["percentage"], shipment=shipment # TODO: Added "strategy" bc nested structure of config, right?
                )
        elif unit == "stems":
            def inspect(shipment):
                return inspect_percentage_stems(
                    config=config["inspection"]["strategy"]["percentage"], shipment=shipment # TODO: Added "strategy" bc nested structure of config, right?
                )
        else:
            raise RuntimeError(
                "Unknown inspection percentage unit: {unit}".format(**locals())
            )
    elif inspection_strategy == "first_n":

        def inspect(shipment):
            return inspect_first_n(
                num_boxes=config["inspection"]["first_n_boxes"], shipment=shipment
            )

    # TODO: does this need a function with shipment like "first_n" above?
    elif inspection_strategy == "first":
        inspect = inspect_first
    elif inspection_strategy == "one_random":
        inspect = inspect_one_random
    elif inspection_strategy == "all":
        inspect = inspect_all
    else:
        raise RuntimeError(
            "Unknown inspection strategy: {inspection_strategy}".format(**locals())
        )
    return inspect


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


def count_diseased(shipment):
    """Return number of boxes with pest"""
    count = 0
    for box in shipment["boxes"]:
        if box:
            count += 1
    return count
