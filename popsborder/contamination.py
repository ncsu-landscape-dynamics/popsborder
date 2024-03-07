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
from collections.abc import Mapping
from datetime import datetime

import numpy as np
from scipy import stats

from .inputs import update_nested_dict_by_dict


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


def get_contamination_rate(config):
    """Get contamination rate.

    Config is the ``contamination_rate`` dictionary.
    """
    distribution = config["distribution"]
    if distribution == "fixed_value":
        return config["value"]
    if distribution == "beta":
        parameters = config["parameters"]
        if isinstance(parameters, Mapping):
            param1 = parameters["a"]
            param2 = parameters["b"]
        else:
            param1, param2 = parameters
        return float(stats.beta.rvs(param1, param2, size=1))
    raise RuntimeError(f"Unknown contamination rate distribution: {distribution}")


def num_items_to_contaminate(config, num_items):
    """Return number of items to be contaminated
    Rounds up or down to nearest integer.

    Config is the ``contamination_rate`` dictionary.
    """
    contamination_rate = get_contamination_rate(config)
    contaminated_items = round(num_items * contamination_rate)
    return contaminated_items


def num_boxes_to_contaminate(config, num_boxes):
    """Return number of boxes to be contaminated as float.

    Config is the ``contamination_rate`` dictionary.
    """
    contamination_rate = get_contamination_rate(config)
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
            """Cannot avoid overlapping clusters. Increase 
            contaminated_units_per_cluster
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


def consignment_matches_selection_rule(rule, consignment):
    """Return True if the *consignment* matches the selection *rule*."""
    # Commodity properties used for selection default to None.
    commodity = rule.get("commodity")
    origin = rule.get("origin")
    port = rule.get("port")
    # All the properties needs to match, but if the property value is not
    # provided in configuration, we count it as match so that consignment
    # can be selected using only one property.
    selected = (
            (not commodity or commodity == consignment.commodity)
            and (not origin or origin == consignment.origin)
            and (not port or port == consignment.port)
    )
    if not selected:
        return False
    start_date = rule.get("start_date")
    end_date = rule.get("end_date")
    # YAML converts to date, but JSON and other load config methods do not.
    if start_date and isinstance(start_date, str):
        start_date = datetime.strptime(start_date, "%Y-%m-%d")
    if end_date and isinstance(end_date, str):
        end_date = datetime.strptime(end_date, "%Y-%m-%d")
    if not start_date and not end_date:
        return True
    elif start_date and consignment.date < start_date:
        return False
    elif end_date and consignment.date > end_date:
        return False
    return True


def get_contamination_config_for_consignment(config, consignment):
    """Get contamination configuration for specific consignment

    If the *config* contains consignment-specific settings under
    the consignments key, contamination configuration is selected
    based on the specified rules. If the consignment properties match
    the selection rules or if it passes the probability challenge,
    consignment-specific configuration is returned.

    If there is contamination key associated with the consignment settings,
    the associated value is returned as the consignment-specific configuration.
    If there is also a use_contamination_defaults key with value set to true,
    the top-level contamination configuration is used as the basis for the
    consignment-specific configuration and the values under the contamination key
    are used to modify or enhance the top-level config.

    If there is no contamination key, the consignment-specific configuration is the
    top-level contamination configuration.

    If the consignment properties do not match
    the selection rules or if it does not pass the probability challenge,
    None is returned.

    If the *config* does not contain consignment-specific settings under
    the consignments key, the function always returns a the provided
    *config*.

    In all cases, a copy the config dictionary is returned.
    """
    contaminated_consignments = config.get("consignments")
    if not contaminated_consignments:
        # No consignment-specific info, all consignments use the same config.
        return config.copy()
    # Consignment-specific input provided, create the right config for the consignment
    # if the consignment is configured to be contaminated.
    for item in contaminated_consignments:
        if consignment_matches_selection_rule(rule=item, consignment=consignment):
            # The consignment matches the selection rule. Now test if we should
            # contaminate this specific consignment.
            probability = item.get("probability")
            if probability is None or random.random() < probability:
                # This specific consignment should contaminated.
                consignment_specific_config = item.get("contamination")
                if not consignment_specific_config:
                    # If missing or empty, use the global/default one.
                    consignment_specific_config = config.copy()
                    del consignment_specific_config["consignments"]
                elif item.get("use_contamination_defaults"):
                    # There is specifc config, but the global/main contamination
                    # config should be used as the bases for the consignment-specific
                    # config.
                    default_values = config.copy()
                    del default_values["consignments"]
                    update_nested_dict_by_dict(
                        default_values, consignment_specific_config
                    )
                    consignment_specific_config = default_values
                else:
                    # In all other cases, we return a copy, so let's do for the
                    # straightforward case too.
                    consignment_specific_config = consignment_specific_config.copy()
                return consignment_specific_config
            else:
                # Only the first consignment rule is matched.
                break
    # Consignment not selected for contamination based on selection rules.
    return None


def create_contaminant_function(config):
    """Create a function based on the contamination config

    An arrangement key must be provided to specify which function should be used.
    """
    arrangement = config.get("arrangement")
    if arrangement == "random_box":

        def add_contaminant_function(consignment):
            return add_contaminant_to_random_box(
                config=config["random_box"],
                consignment=consignment,
                contamination_rate=config["contamination_rate"],
            )

    elif arrangement == "random":

        def add_contaminant_function(consignment):
            return add_contaminant_uniform_random(
                config=config, consignment=consignment
            )

    elif arrangement == "clustered":

        def add_contaminant_function(consignment):
            return add_contaminant_clusters(config=config, consignment=consignment)

    elif arrangement is None:
        raise RuntimeError("Contaminant arrangement must be set")
    else:
        raise RuntimeError(f"Unknown contaminant arrangement: {arrangement}")
    return add_contaminant_function


def get_contaminant_function(config):
    """Get function for adding contaminant to a consignment based on configuration"""
    if "consignments" in config["contamination"]:
        # If there is config for individual consignments, we define a new function
        # which first picks the right config based on its consignment parameter, then
        # creates an add contaminant function based on this config, and then it calls
        # the function with the consignment.

        def add_contaminant_function(consignment):
            """Picks config for the consignment and then call the specific function"""
            consignment_specific_config = get_contamination_config_for_consignment(
                config["contamination"], consignment
            )
            if not consignment_specific_config:
                # Do not contaminate this consignment.
                # No modification to the existing consignment provided as a parameter
                # and returning None (as all the add contaiminant functions do).
                return None
            contaminant_function = create_contaminant_function(
                consignment_specific_config
            )
            return contaminant_function(consignment)

        return add_contaminant_function

    # If there is config for individual consignments, we just create the function with
    # the default settings.
    return create_contaminant_function(config["contamination"])
