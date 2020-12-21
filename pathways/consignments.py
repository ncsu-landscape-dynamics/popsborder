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
Consignment and contaminant generation for pathways simulation

.. codeauthor:: Vaclav Petras <wenzeslaus gmail com>
"""

from __future__ import print_function, division

import random
import csv
from datetime import datetime, timedelta
import math
import collections
import numpy as np
import scipy.stats as stats


class Box:
    """Box or inspection unit

    Evaluates to bool when it contains contaminant.

    Box is a view into array of items, i.e. a slice of that array. The
    assumption is that the original, and possibly modifed, items can not
    only be accessed but also modifed through the box.
    """

    def __init__(self, items):
        """Store reference to associated items

        :param items: Array-like object of items
        """
        self.items = items

    @property
    def num_items(self):
        """Number of items in the box"""
        return self.items.shape[0]

    def __bool__(self):
        return bool(np.any(self.items > 0))


class Consignment(collections.UserDict):
    """A consignment with all its properties and what it contains.

    Access is through attributes (new style) or using a dictionary-like item access
    (old style).
    """

    # Inheriting from this library class is its intended use, so disable ancestors msg.
    # pylint: disable=too-many-ancestors

    def __init__(
        self,
        flower,
        num_items,
        items,
        items_per_box,
        num_boxes,
        date,
        boxes,
        origin,
        port,
        pathway,
    ):
        """Store reference to associated attributes

        :param flower: string
        :param num_items: integer
        :param items_per_box: integer
        :param num_boxes: integer
        :param date: Array-like object of items
        :param boxes: Array-like object of boxes
        :param origin: string
        :param port: string
        :param pathway: string
        """
        self.flower = flower
        self.num_items = num_items
        self.items = items
        self.items_per_box = items_per_box
        self.num_boxes = num_boxes
        self.date = date
        self.boxes = boxes
        self.origin = origin
        self.port = port
        self.pathway = pathway

    def __getattr__(self, name):
        return self.name

    def count_contaminated(self):
        """Count contaminated items in box."""
        return np.count_nonzero(self.items)

    def item_in_box_to_item_index(self, box_index, item_in_box_index):
        """Convert item index in a box to item index in the consignment"""
        if box_index == 0:
            return item_in_box_index
        items = 0
        for box in self.boxes[:box_index]:
            items += box.num_items
        return items + item_in_box_index


class ParameterConsignmentGenerator:
    """Generate a consignments based on configuration parameters"""

    def __init__(self, parameters, items_per_box, start_date):
        """Set parameters for shipement generation

        :param parameters: Consignment parameters
        :param ports: List of ports to choose from
        :param items_per_box: Configuration driving number of items per box
        :param start_date: Date to start consignment dates from
        """
        self.params = parameters
        self.items_per_box = items_per_box
        self.num_generated = 0
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d")
        self.date = start_date

    def generate_consignment(self):
        """Generate a new consignment"""
        port = random.choice(self.params["ports"])
        # flowers or commodities
        flower = random.choice(self.params["flowers"])
        origin = random.choice(self.params["origins"])
        num_boxes_min = self.params["boxes"].get("min", 0)
        num_boxes_max = self.params["boxes"]["max"]
        pathway = "None"
        items_per_box = self.items_per_box
        items_per_box = get_items_per_box(items_per_box, pathway)
        num_boxes = random.randint(num_boxes_min, num_boxes_max)
        num_items = items_per_box * num_boxes
        items = np.zeros(num_items, dtype=np.int)
        boxes = []
        for i in range(num_boxes):
            lower = i * items_per_box
            upper = (i + 1) * items_per_box
            boxes.append(Box(items[lower:upper]))
        self.num_generated += 1
        # two consignments every nth day
        if self.num_generated % 3:
            self.date += timedelta(days=1)

        return Consignment(
            flower=flower,
            num_items=num_items,
            items=items,
            items_per_box=items_per_box,
            num_boxes=num_boxes,
            date=self.date,
            boxes=boxes,
            origin=origin,
            port=port,
            pathway=pathway,
        )


class F280ConsignmentGenerator:
    """Generate a consignments based on existing F280 records"""

    def __init__(self, items_per_box, filename, separator=","):
        self.infile = open(filename)
        self.reader = csv.DictReader(self.infile, delimiter=separator)
        self.items_per_box = items_per_box

    def generate_consignment(self):
        """Generate a new consignment"""
        try:
            record = next(self.reader)
        except StopIteration:
            raise RuntimeError(
                "More consignments requested than number of records in provided F280"
            )

        num_items = int(record["QUANTITY"])
        items = np.zeros(num_items, dtype=np.int)

        pathway = record["PATHWAY"]
        items_per_box = self.items_per_box
        items_per_box = get_items_per_box(items_per_box, pathway)

        # rounding up to keep the max per box and have enough boxes
        num_boxes = int(math.ceil(num_items / float(items_per_box)))
        if num_boxes < 1:
            num_boxes = 1
        boxes = []
        for i in range(num_boxes):
            lower = i * items_per_box
            # slicing does not go over the size even if our last box is smaller
            upper = (i + 1) * items_per_box
            boxes.append(Box(items[lower:upper]))
        assert sum([box.num_items for box in boxes]) == num_items

        date = datetime.strptime(record["REPORT_DT"], "%Y-%m-%d")
        return Consignment(
            flower=record["COMMODITY"],
            num_items=num_items,
            items=items,
            items_per_box=items_per_box,
            num_boxes=num_boxes,
            date=date,
            boxes=boxes,
            origin=record["ORIGIN_NM"],
            port=record["LOCATION"],
            pathway=pathway,
        )


class AQIMConsignmentGenerator:
    """Generate a consignments based on existing AQIM records"""

    def __init__(self, items_per_box, filename, separator=","):
        self.infile = open(filename)
        self.reader = csv.DictReader(self.infile, delimiter=separator)
        self.items_per_box = items_per_box

    def generate_consignment(self):
        """Generate a new consignment"""
        try:
            record = next(self.reader)
        except StopIteration:
            raise RuntimeError(
                "More consignments requested than number of records in AQIM data"
            )
        pathway = record["CARGO_FORM"]
        items_per_box = self.items_per_box
        items_per_box = get_items_per_box(items_per_box, pathway)
        unit = record["UNIT"]

        # Generate items based on quantity in AQIM records.
        # If quantity is given in boxes, use item_per_box to convert to items.
        if unit in ["Box/Carton"]:
            num_items = int(record["QUANTITY"]) * items_per_box
        elif unit in ["Stems"]:
            num_items = int(record["QUANTITY"])
        else:
            raise RuntimeError("Unsupported quantity unit: {unit}".format(**locals()))

        items = np.zeros(num_items, dtype=np.int)

        # rounding up to keep the max per box and have enough boxes
        num_boxes = int(math.ceil(num_items / float(items_per_box)))
        if num_boxes < 1:
            num_boxes = 1
        boxes = []
        for i in range(num_boxes):
            lower = i * items_per_box
            # slicing does not go over the size even if our last box is smaller
            upper = (i + 1) * items_per_box
            boxes.append(Box(items[lower:upper]))
        assert sum([box.num_items for box in boxes]) == num_items

        date = record["CALENDAR_YR"]
        return Consignment(
            flower=record["COMMODITY_LIST"],
            num_items=num_items,
            items=items,
            items_per_box=items_per_box,
            num_boxes=num_boxes,
            date=date,
            boxes=boxes,
            origin=record["ORIGIN"],
            port=record["LOCATION"],
            pathway=pathway,
        )


def get_items_per_box(items_per_box, pathway):
    """Based on config and pathway, return number of items per box."""
    if pathway.lower() == "airport" and "air" in items_per_box:
        items_per_box = items_per_box["air"]["default"]
    elif pathway.lower() == "maritime" and "maritime" in items_per_box:
        items_per_box = items_per_box["maritime"]["default"]
    else:
        items_per_box = items_per_box["default"]
    return items_per_box


def get_consignment_generator(config):
    """Based on config, return consignment generator object."""
    if ("f280_file" in config) and config["f280_file"]:
        consignment_generator = F280ConsignmentGenerator(
            items_per_box=config["consignment"]["items_per_box"],
            filename=config["f280_file"],
        )
    elif ("aqim_file" in config) and config["aqim_file"]:
        consignment_generator = AQIMConsignmentGenerator(
            items_per_box=config["consignment"]["items_per_box"],
            filename=config["aqim_file"],
        )
    else:
        start_date = config["consignment"].get("start_date", "2020-01-01")
        consignment_generator = ParameterConsignmentGenerator(
            parameters=config["consignment"],
            items_per_box=config["consignment"]["items_per_box"],
            start_date=start_date,
        )
    return consignment_generator


# This function is not used or working, consider updating or removing.
def add_contaminant_to_random_box(config, consignment, contamination_rate=None):
    """Add contaminant to consignment

    Assuming a list of boxes with the non-contaminated boxes set to False.

    Each item (box) in boxes (list) is set to True if a contaminant is
    there, False otherwise.

    :param config: ``random_box`` config dictionary
    :param consignment: Consignment to contaminate
    :param contamination_rate: ``contamination_rate`` config dictionary
    """
    contaminant_probability = config["probability"]
    contaminant_ratio = config["ratio"]
    if random.random() >= contaminant_probability:
        return
    for box in consignment.boxes:
        if random.random() < contaminant_ratio:
            in_box = config.get("in_box_arrangement", "all")
            if in_box == "first":
                # simply put one contaminant to first item in the box
                box.items[0] = 1
            elif in_box == "all":
                box.items.fill(1)
            elif in_box == "one_random":
                index = np.random.choice(box.num_items - 1)
                box.items[index] = 1
            elif in_box == "random":
                if not contamination_rate:
                    raise ValueError(
                        "contamination_rate must be set if arrangement is random"
                    )
                num_contaminated_items = num_items_to_contaminate(
                    contamination_rate, box.num_items
                )
                if num_contaminated_items == 0:
                    continue
                indexes = np.random.choice(
                    box.num_items, num_contaminated_items, replace=False
                )
                np.put(box.items, indexes, 1)


def num_items_to_contaminate(config, num_items):
    """Return number of items to be contaminated
    Rounds up or down to nearest integer.

    Config is the ``contamination_rate`` dictionary.
    """
    distribution = config["distribution"]
    if distribution == "fixed_value":
        contamination_rate = config["value"]
    elif distribution == "beta":
        param1, param2 = config["parameters"]
        contamination_rate = float(stats.beta.rvs(param1, param2, size=1))
    else:
        raise RuntimeError(
            "Unknown contamination rate distribution: {distribution}".format(**locals())
        )
    contaminated_items = round(num_items * contamination_rate)
    return contaminated_items


def num_boxes_to_contaminate(config, num_boxes):
    """Return number of boxes to be contaminated.
    Rounds up or down to nearest integer.

    Config is the ``contamination_rate`` dictionary.
    """
    distribution = config["distribution"]
    if distribution == "fixed_value":
        contamination_rate = config["value"]
    elif distribution == "beta":
        param1, param2 = config["parameters"]
        contamination_rate = float(stats.beta.rvs(param1, param2, size=1))
    else:
        raise RuntimeError(
            "Unknown contamination rate distribution: {distribution}".format(**locals())
        )
    contaminated_boxes = round(num_boxes * contamination_rate)
    return contaminated_boxes


def add_contaminant_uniform_random(config, consignment):
    """Add contaminants to consignment using uniform random distribution

    Contamination rate is determined using the ``contamination_rate`` config key.
    """
    contamination_unit = config["contamination_unit"]
    if contamination_unit in ["box", "boxes"]:
        contaminated_boxes = num_boxes_to_contaminate(
            config["contamination_rate"], consignment.num_boxes
        )
        if contaminated_boxes == 0:
            return
        indexes = np.random.choice(
            consignment.num_boxes, contaminated_boxes, replace=False
        )
        for index in indexes:
            consignment.boxes[index].items.fill(1)
        assert np.count_nonzero(consignment.boxes) == contaminated_boxes
    elif contamination_unit in ["item", "items"]:
        contaminated_items = num_items_to_contaminate(
            config["contamination_rate"], consignment.num_items
        )
        if contaminated_items == 0:
            return
        indexes = np.random.choice(
            consignment.num_items, contaminated_items, replace=False
        )
        np.put(consignment.items, indexes, 1)
        assert np.count_nonzero(consignment.items) == contaminated_items
    else:
        raise RuntimeError(
            "Unknown contamination unit: {contamination_unit}".format(**locals())
        )


def _contaminated_items_to_cluster_sizes(
    contaminated_items, max_contaminated_units_per_cluster
):
    """Get list of cluster sizes for a given number of contaminated items

    The size of each cluster is limited by max_contaminated_units_per_cluster.
    """
    if contaminated_items > max_contaminated_units_per_cluster:
        # Split into n clusters so that n-1 clusters have the max size and
        # the last one has the remaining items.
        # Alternative would be sth like:
        # round(contaminated_items/max_contaminated_units_per_cluster)
        sum_items = 0
        cluster_sizes = []
        while sum_items < contaminated_items - max_contaminated_units_per_cluster:
            sum_items += max_contaminated_units_per_cluster
            cluster_sizes.append(max_contaminated_units_per_cluster)
        # add remaining items
        cluster_sizes.append(contaminated_items - sum_items)
        sum_items += contaminated_items - sum_items
        assert sum_items == contaminated_items
    else:
        cluster_sizes = [contaminated_items]
    return cluster_sizes


def _contaminated_boxes_to_cluster_sizes(contaminated_boxes, max_boxes_per_cluster):
    """Get list of cluster sizes for a given number of contaminated items

    The size of each cluster is limited by max_contaminated_units_per_cluster.
    """
    if contaminated_boxes > max_boxes_per_cluster:
        # Split into n clusters so that n-1 clusters have the max size and
        # the last one has the remaining items.
        sum_boxes = 0
        cluster_sizes = []
        while sum_boxes < contaminated_boxes - max_boxes_per_cluster:
            sum_boxes += max_boxes_per_cluster
            cluster_sizes.append(max_boxes_per_cluster)
        # add remaining boxes
        cluster_sizes.append(contaminated_boxes - sum_boxes)
        sum_boxes += contaminated_boxes - sum_boxes
        assert sum_boxes == contaminated_boxes
    else:
        cluster_sizes = [contaminated_boxes]
    return cluster_sizes


def create_stratas_for_clusters(num_units, cluster_width, cluster_sizes):
    """Divide array of items or boxes into strata wide enough for clusters."""
    num_strata = max(1, math.floor(num_units / cluster_width))
    assert num_strata >= len(
        cluster_sizes
    ), """Cannot avoid overlapping clusters. Increase max_contaminated_units_per_cluster
    or decrease max_cluster_item_width (if using item contamination_unit)"""
    cluster_strata = np.random.choice(num_strata, len(cluster_sizes), replace=False)
    return num_strata, cluster_strata


def add_contaminant_clusters(config, consignment):
    """Add contaminant clusters to consignment

    Assuming a list of boxes with the non-contaminated boxes set to False.

    Each item (box) in boxes (list) is set to True if a contaminant is
    there, False otherwise.
    """
    contamination_unit = config["contamination_unit"]
    max_contaminated_units_per_cluster = config["clustered"][
        "max_contaminated_units_per_cluster"
    ]

    if contamination_unit in ["box", "boxes"]:
        num_boxes = consignment.num_boxes
        contaminated_boxes = num_boxes_to_contaminate(
            config["contamination_rate"], num_boxes
        )
        if contaminated_boxes == 0:
            return
        cluster_sizes = _contaminated_boxes_to_cluster_sizes(
            contaminated_boxes, max_contaminated_units_per_cluster
        )
        num_strata, cluster_strata = create_stratas_for_clusters(
            num_boxes, max_contaminated_units_per_cluster, cluster_sizes
        )
        for index, cluster_size in enumerate(cluster_sizes):
            cluster_start = math.floor(num_boxes / num_strata) * cluster_strata[index]
            cluster_indexes = np.arange(
                start=cluster_start, stop=cluster_start + cluster_size
            )
            for cluster_index in cluster_indexes:
                consignment.boxes[cluster_index].items.fill(1)
        assert np.count_nonzero(consignment.boxes) <= contaminated_boxes

    elif contamination_unit in ["item", "items"]:
        num_items = consignment.num_items
        contaminated_items = num_items_to_contaminate(
            config["contamination_rate"], num_items
        )
        if contaminated_items == 0:
            return
        cluster_sizes = _contaminated_items_to_cluster_sizes(
            contaminated_items, max_contaminated_units_per_cluster
        )
        cluster_indexes = []
        distribution = config["clustered"]["distribution"]
        if distribution == "random":
            max_cluster_item_width = config["clustered"]["random"][
                "max_cluster_item_width"
            ]
            if max_cluster_item_width < max_contaminated_units_per_cluster:
                raise ValueError(
                    "Maximum cluster width, currently {max_cluster_item_width}, needs"
                    " to be at least as large as max_contaminated_units_per_cluster"
                    " (currently {max_contaminated_units_per_cluster})".format(
                        **locals()
                    )
                )
            # cluster can't be wider/longer than the current list of items
            max_cluster_item_width = min(max_cluster_item_width, num_items)
            num_strata, cluster_strata = create_stratas_for_clusters(
                num_items, max_cluster_item_width, cluster_sizes
            )
            for index, cluster_size in enumerate(cluster_sizes):
                cluster = np.random.choice(
                    max_cluster_item_width, cluster_size, replace=False
                )
                cluster_start = math.floor(
                    (num_items / num_strata) * cluster_strata[index]
                )
                cluster += cluster_start
                cluster_indexes.extend(list(cluster))
        elif distribution == "continuous":
            num_strata, cluster_strata = create_stratas_for_clusters(
                num_items, max_contaminated_units_per_cluster, cluster_sizes
            )
            for index, cluster_size in enumerate(cluster_sizes):
                cluster = np.arange(0, cluster_size)
                cluster_start = math.floor(
                    (num_items / num_strata) * cluster_strata[index]
                )
                cluster += cluster_start
                cluster_indexes.extend(list(cluster))
        else:
            raise RuntimeError(
                "Unknown cluster distribution: {distribution}".format(**locals())
            )
        cluster_indexes = np.array(cluster_indexes, dtype=np.int)
        cluster_max = max(cluster_indexes)
        if cluster_max > num_items - 1:
            # If the max index specified by the cluster is outside of item
            # array index range, fit the cluster values into that range.
            cluster_indexes = np.interp(
                cluster_indexes,
                (cluster_indexes.min(), cluster_indexes.max()),
                (0, num_items - 1),
            )
        assert min(cluster_indexes) >= 0, "Cluster values need to be valid indices"
        assert max(cluster_indexes) < num_items
        np.put(consignment.items, cluster_indexes, 1)
        assert np.count_nonzero(consignment.items) == contaminated_items

    else:
        raise RuntimeError(
            "Unknown contamination unit: {contamination_unit}".format(**locals())
        )


def get_contaminant_function(config):
    """Get function for adding contaminant to a consignment based on configuration"""
    arrangement = config["contamination"]["arrangement"]
    if arrangement == "random_box":

        def add_contaminant_function(consignment):
            return add_contaminant_to_random_box(
                config=config["contamination"]["random_box"],
                consignment=consignment,
                contamination_rate=config["contamination"]["contamination_rate"],
            )

    elif arrangement == "random":

        def add_contaminant_function(consignment):
            return add_contaminant_uniform_random(
                config=config["contamination"], consignment=consignment
            )

    elif arrangement == "clustered":

        def add_contaminant_function(consignment):
            return add_contaminant_clusters(
                config=config["contamination"], consignment=consignment
            )

    else:
        raise RuntimeError(
            "Unknown contaminant arrangement: {arrangement}".format(**locals())
        )
    return add_contaminant_function
