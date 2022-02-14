# Simulation of contaminated consignments and their inspections
# Copyright (C) 2018-2022 Vaclav Petras and others (see below)

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


"""Contaminant addition to consignments

.. codeauthor:: Vaclav Petras <wenzeslaus gmail com>
.. codeauthor:: Kellyn P. Montgomery <kellynmontgomery gmail com>
"""

import math
import random

import numpy as np
from scipy import stats


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
        raise RuntimeError(f"Unknown contamination rate distribution: {distribution}")
    contaminated_items = round(num_items * contamination_rate)
    return contaminated_items


def num_boxes_to_contaminate(config, num_boxes):
    """Return number of boxes to be contaminated as float.

    Config is the ``contamination_rate`` dictionary.
    """
    distribution = config["distribution"]
    if distribution == "fixed_value":
        contamination_rate = config["value"]
    elif distribution == "beta":
        param1, param2 = config["parameters"]
        contamination_rate = float(stats.beta.rvs(param1, param2, size=1))
    else:
        raise RuntimeError(f"Unknown contamination rate distribution: {distribution}")
    contaminated_boxes = num_boxes * contamination_rate
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
        if contaminated_boxes == 0.0:
            return
        box_indexes = np.random.choice(
            consignment.num_boxes, math.ceil(contaminated_boxes), replace=False
        )
        # Contaminate full boxes except for last one
        for box_index in box_indexes[:-1]:
            consignment.boxes[box_index].items.fill(1)
        # Use remainder of contaminated_boxes to partially contaminate
        # last box if needed
        partial_box_proportion = math.modf(contaminated_boxes)[0]
        # If contaminated_boxes is whole number, contaminate full box
        if partial_box_proportion == 0.0:
            partial_box_proportion = 1
        partial_box_contaminated_stems = round(
            consignment.boxes[box_indexes[-1]].num_items * partial_box_proportion
        )
        consignment.boxes[box_indexes[-1]].items[0:partial_box_contaminated_stems].fill(
            1
        )
        # Check if correct number of boxes contaminated, should be rounded up
        # contaminated_boxes, or may be rounded down contaminated_boxes
        # if no stems were contaminated in last partial box
        assert np.count_nonzero(consignment.boxes) in (
            math.ceil(contaminated_boxes),
            math.floor(contaminated_boxes),
        )
    elif contamination_unit in ["item", "items"]:
        contaminated_items = num_items_to_contaminate(
            config["contamination_rate"], consignment.num_items
        )
        if contaminated_items == 0:
            return
        item_indexes = np.random.choice(
            consignment.num_items, contaminated_items, replace=False
        )
        np.put(consignment.items, item_indexes, 1)
        assert np.count_nonzero(consignment.items) == contaminated_items
    else:
        raise RuntimeError(f"Unknown contamination unit: {contamination_unit}")


def _contaminated_items_to_cluster_sizes(
    contaminated_items, contaminated_units_per_cluster
):
    """Get list of cluster sizes for a given number of contaminated items

    The size of each cluster is limited by contaminated_units_per_cluster.
    """
    if contaminated_items > contaminated_units_per_cluster:
        # Split into n clusters so that n-1 clusters have the max size and
        # the last one has the remaining items.
        # Alternative would be sth like:
        # round(contaminated_items/contaminated_units_per_cluster)
        sum_items = 0
        cluster_sizes = []
        while sum_items < contaminated_items - contaminated_units_per_cluster:
            sum_items += contaminated_units_per_cluster
            cluster_sizes.append(contaminated_units_per_cluster)
        # add remaining items
        cluster_sizes.append(contaminated_items - sum_items)
        sum_items += contaminated_items - sum_items
        assert sum_items == contaminated_items
    else:
        cluster_sizes = [contaminated_items]
    return cluster_sizes


def _contaminated_boxes_to_cluster_sizes(
    contaminated_boxes, contaminated_units_per_cluster
):
    """Get list of cluster sizes for a given number of contaminated items

    The size of each cluster is limited by contaminated_units_per_cluster.
    """
    contaminated_boxes = math.ceil(contaminated_boxes)
    if contaminated_boxes > contaminated_units_per_cluster:
        # Split into n clusters so that n-1 clusters have the max size and
        # the last one has the remaining items.
        sum_boxes = 0
        cluster_sizes = []
        while sum_boxes < contaminated_boxes - contaminated_units_per_cluster:
            sum_boxes += contaminated_units_per_cluster
            cluster_sizes.append(contaminated_units_per_cluster)
        # add last cluster with remaining contaminated boxes
        cluster_sizes.append(contaminated_boxes - sum_boxes)
        sum_boxes += contaminated_boxes - sum_boxes
        assert sum_boxes == contaminated_boxes
    else:
        cluster_sizes = [math.ceil(contaminated_boxes)]
    return cluster_sizes


def choose_strata_for_clusters(num_units, cluster_width, num_clusters):
    """Divide array of items or boxes into strata wide enough for clusters
    so that they do not overlap. If array is not equally divisible by cluster_width,
    create one smaller strata that can be used for a smaller cluster if needed.
    This is important for very high contamination rates that require nearly all units
    to be contaminated.
    Randomly select strata to place contaminant clusters. If contamination rate is
    low enough that not all strata are needed, omit smaller strata created from
    remainder and only select from strata wide enough to contain full sized cluster.
    Return strata selected to contaminate with clusters.

    num_units: number of boxes or items in consignment
    cluster_width: size of cluster in terms of boxes or units
    num_clusters: number of clusters to contaminate
    """
    # Round up so that one smaller remainder stratum is included
    num_strata = max(1, math.ceil(num_units / cluster_width))
    # Make sure there are enough strata for the number of clusters needed.
    if num_strata < num_clusters:
        raise ValueError(
            """Cannot avoid overlapping clusters. Increase contaminated_units_per_cluster
            or decrease cluster_item_width (if using item contamination_unit)"""
        )
    # If all strata are needed, all strata are selected for clusters
    if num_clusters == num_strata:
        cluster_strata = np.arange(num_strata)
    # If not all strata needed (num of clusters is less than num of strata), do not use
    # last strata if its smaller than cluster_width (remainder from rounding up)
    else:
        # if no remainder (all strata are equal length), select any strata for clusters
        if num_units % cluster_width == 0:
            cluster_strata = np.random.choice(num_strata, num_clusters, replace=False)
        # if last strata is smaller and not all strata are needed,
        # do not include last strata as option for placing clusters
        else:
            cluster_strata = np.random.choice(
                num_strata - 1, num_clusters, replace=False
            )
    return cluster_strata


def add_contaminant_clusters_to_boxes(config, consignment):
    """Add contaminant clusters to boxes in a consignment"""
    contaminated_units_per_cluster = config["clustered"][
        "contaminated_units_per_cluster"
    ]
    num_boxes = consignment.num_boxes
    contaminated_boxes = num_boxes_to_contaminate(
        config["contamination_rate"], num_boxes
    )
    if contaminated_boxes == 0:
        return
    cluster_sizes = _contaminated_boxes_to_cluster_sizes(
        contaminated_boxes, contaminated_units_per_cluster
    )
    cluster_strata = choose_strata_for_clusters(
        num_boxes, contaminated_units_per_cluster, len(cluster_sizes)
    )
    # Contaminate full boxes in all clusters except the last one
    for index, cluster_size in enumerate(cluster_sizes[:-1]):
        # Find starting index of strata (cluster width * strata index)
        cluster_start = contaminated_units_per_cluster * cluster_strata[index]
        cluster_indexes = np.arange(
            start=cluster_start, stop=cluster_start + cluster_size
        )
        for cluster_index in cluster_indexes:
            consignment.boxes[cluster_index].items.fill(1)
    # In last box of last cluster, contaminate partial box if needed
    cluster_start = (
        contaminated_units_per_cluster * cluster_strata[len(cluster_sizes) - 1]
    )
    cluster_indexes = np.arange(
        start=cluster_start, stop=cluster_start + cluster_sizes[-1]
    )
    for cluster_index in cluster_indexes[:-1]:
        consignment.boxes[cluster_index].items.fill(1)
    # Use remainder of contaminated_boxes to partially contaminate last box
    partial_box_proportion = math.modf(contaminated_boxes)[0]
    # If contaminated_boxes is whole number, contaminate full box
    if partial_box_proportion == 0.0:
        partial_box_proportion = 1
    partial_box_contaminated_stems = round(
        consignment.boxes[cluster_indexes[-1]].num_items * partial_box_proportion
    )
    consignment.boxes[cluster_indexes[-1]].items[0:partial_box_contaminated_stems].fill(
        1
    )
    # Check if correct number of boxes contaminated, should be rounded up
    # contaminated_boxes, or may be rounded down contaminated_boxes
    # if no stems were contaminated in last partial box
    assert np.count_nonzero(consignment.boxes) in (
        math.ceil(contaminated_boxes),
        math.ceil(contaminated_boxes) - 1,
    )


def add_contaminant_clusters_to_items(config, consignment):
    """Add contaminant clusters to items in a consignment"""
    contaminated_units_per_cluster = config["clustered"][
        "contaminated_units_per_cluster"
    ]
    num_items = consignment.num_items
    contaminated_items = num_items_to_contaminate(
        config["contamination_rate"], num_items
    )
    if contaminated_items == 0:
        return
    cluster_sizes = _contaminated_items_to_cluster_sizes(
        contaminated_items, contaminated_units_per_cluster
    )
    cluster_indexes = []
    distribution = config["clustered"]["distribution"]
    if distribution == "random":
        cluster_item_width = config["clustered"]["random"]["cluster_item_width"]
        if cluster_item_width < contaminated_units_per_cluster:
            raise ValueError(
                f"Maximum cluster width, currently {cluster_item_width}, needs"
                " to be at least as large as contaminated_units_per_cluster"
                " (currently {contaminated_units_per_cluster})"
            )
        # cluster can't be wider/longer than the current list of items
        cluster_item_width = min(cluster_item_width, num_items)
        cluster_strata = choose_strata_for_clusters(
            num_items, cluster_item_width, len(cluster_sizes)
        )
        for index, cluster_size in enumerate(cluster_sizes):
            cluster_start = cluster_item_width * cluster_strata[index]
            # Use smaller cluster width if placing items in smaller remainder stratum
            cluster_width = min(
                cluster_item_width, (consignment.num_items - cluster_start)
            )
            assert (
                cluster_width >= cluster_size
            ), "Not enough items available to contaminate in selected cluster stratum."
            cluster = np.random.choice(cluster_width, cluster_size, replace=False)
            cluster += cluster_start
            cluster_indexes.extend(list(cluster))
    elif distribution == "continuous":
        cluster_strata = choose_strata_for_clusters(
            num_items, contaminated_units_per_cluster, len(cluster_sizes)
        )
        for index, cluster_size in enumerate(cluster_sizes):
            cluster = np.arange(cluster_size)
            cluster_start = contaminated_units_per_cluster * cluster_strata[index]
            cluster += cluster_start
            cluster_indexes.extend(list(cluster))
    else:
        raise RuntimeError(f"Unknown cluster distribution: {distribution}")
    cluster_indexes = np.array(cluster_indexes, dtype=np.int64)
    assert min(cluster_indexes) >= 0, "Cluster values need to be valid indices"
    assert max(cluster_indexes) < num_items
    np.put(consignment.items, cluster_indexes, 1)
    assert np.count_nonzero(consignment.items) == contaminated_items


def add_contaminant_clusters(config, consignment):
    """Add contaminant clusters to consignment

    Item (separately or in boxes) with contaminat in *consignment* evaluate
    to True after running this function.
    This function does not touch the not items not selected for contamination.
    However, they are expected to be zero.
    """
    contamination_unit = config["contamination_unit"]
    if contamination_unit in ["box", "boxes"]:
        add_contaminant_clusters_to_boxes(config, consignment)
    elif contamination_unit in ["item", "items"]:
        add_contaminant_clusters_to_items(config, consignment)
    else:
        raise RuntimeError(f"Unknown contamination unit: {contamination_unit}")


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
        raise RuntimeError(f"Unknown contaminant arrangement: {arrangement}")
    return add_contaminant_function
