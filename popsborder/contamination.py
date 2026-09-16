# Simulation of contaminated consignments and their inspections
# Copyright (C) 2018-2022 Vaclav Petras and others (see below)
# © 2026 The Johns Hopkins University Applied Physics Laboratory LLC

"""
==========================================================================================
Johns Hopkins University Applied Physics Laboratory (JHU/APL) Extensions and Modifications
==========================================================================================

Contributors: Gary Lin, Joseph Agor (JHU/APL)

Modifications:
    - add_contaminant_uniform_random():
        * Added plant-level contamination support with pooled contamination methodology

    - add_contaminant_clusters():
        * Updated contamination_unit parameter handling for backward compatibility
        * Supports legacy "box"/"item" terminology while using new "inspection_unit"/"sample_unit" internally
        * Enhanced clustering algorithms for hierarchical contamination patterns

    - add_contaminant_uniform_random():
        * Added functionality to use the beta-binomial model from Clark et. al 2023 paper for plant units

    - get_contaminant_function():
        * Updated to include ability to contaminate using the beta-binomial approach
        * Embedded logic from previously existing create_contaminant_function() into this function

    - Added the following support function for new data-driven contamination procedure:
        * add_contaminant_beta_binomial(): Vectorized sampling functon for Beta-Binomial distribution
        * get_range_key(): Function that finds the parameters based on what range the quantities fall into
        * set_beta_binomial_params():  Function that sets the beta-binomial parameters needed based on the main config file.
        * heuristic_adjust_nonzeros(): Heuristically adjust the number of nonzero entries in an allocation vector.
        * synchronize_contamination_arrays_from_plants(): Synchronize sample-unit and plant arrays to match plant-level contamination truth.
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


"""Contaminant addition to consignments

.. codeauthor:: Vaclav Petras <wenzeslaus gmail com>
.. codeauthor:: Kellyn P. Montgomery <kellynmontgomery gmail com>
.. codeauthor:: Gary Lin <Gary.Lin jhuapl edu>
.. codeauthor:: Joseph Agor <Joseph.Agor jhuapl edu>
"""

import math
import copy
import random
from collections.abc import Mapping
from collections import defaultdict
from datetime import datetime

import numpy as np
from scipy import stats

from .inputs import update_nested_dict_by_dict
import warnings
import ast
from typing import Any, Dict, Optional, Union
from popsborder.consignments import Consignment
from numpy.random import Generator
from slippage_model_utils.general_utils import get_range_key

#############################################
## START:  APL Added New Support Functions ##
#############################################

def heuristic_adjust_nonzeros(
    x: np.ndarray,
    n_bar: np.ndarray,
    target: int,
    max_iters: int = 1000,
) -> np.ndarray:
    """Heuristically adjust the number of nonzero entries in an allocation vector.

    This function attempts to modify the vector ``x`` so that the number of
    nonzero entries is close to ``target``, while respecting capacity
    constraints given by ``n_bar``. It does this by repeatedly merging
    allocations (reducing the number of non-zeros) when there are too many
    nonzero entries, and splitting allocations (increasing the number of
    non-zeros) when there are too few nonzero entries.

    The algorithm stops when the relative difference between the current
    number of non-zeros and ``target`` is within 5%, when the maximum number
    of iterations is reached, or when no further feasible merges/splits are
    possible.

    Args:
        x: One-dimensional array of nonnegative integer allocations. This
            array is copied internally and not modified in-place.
        n_bar: One-dimensional array of capacity constraints for each position
            in ``x``. Must be the same length as ``x``. The allocation at each
            position will not exceed the corresponding capacity in ``n_bar``.
        target: Desired number of nonzero entries in the adjusted allocation
            vector.
        max_iters: Maximum number of heuristic adjustment iterations.

    Returns:
        A one-dimensional array representing the adjusted allocations after
        the heuristic procedure.
    """
    x_adjusted = x.copy()
    total = x.sum()

    for i in range(max_iters):
        nonzero_indices = np.nonzero(x_adjusted)[0]
        nnz = len(nonzero_indices)

        # Handle degenerate case
        if target == 0:
            x_adjusted[:] = 0
            break

        # Relative difference from target
        rel_diff = abs(nnz - target) / target

        # Termination criterion (within 5% relative difference of the target clustering)
        if rel_diff < 0.05:
            break

        if nnz > target:
            # CASE 1: Too many nonzero indices so merge some
            # Sort nonzeros by x_adjusted value ascending (smallest first)
            nz_vals = x_adjusted[nonzero_indices]
            order = np.argsort(nz_vals)
            sorted_indices = nonzero_indices[order]

            merged_any = False

            for idx in sorted_indices:
                # Recompute nnz cheaply: zero idx if we merge
                if nnz <= target:
                    break

                val = x_adjusted[idx]
                if val == 0:
                    continue

                # Prefer targets with larger remaining capacity
                remaining_capacity = n_bar - x_adjusted
                candidates = np.where((remaining_capacity >= val) & (np.arange(len(x_adjusted)) != idx))[0]

                if len(candidates) == 0:
                    continue

                # Choose among the candidates with largest remaining capacity
                cand_cap = remaining_capacity[candidates]
                best_idx = candidates[np.argmax(cand_cap)]

                # Merge: move all mass from idx to best_idx
                x_adjusted[best_idx] += val
                x_adjusted[idx] = 0
                nnz -= 1
                merged_any = True

            if not merged_any:
                # No more merges possible without violating capacity
                break

        else:
            # CASE 2: Too Few nonzero indices split larger ones into multiple
            # Indices that are currently zero but have capacity > 0
            zero_indices = np.where(x_adjusted == 0)[0]
            zero_with_capacity = zero_indices[n_bar[zero_indices] > 0]

            if len(zero_with_capacity) == 0:
                # No place to create new nonzeros
                break

            # Candidates to split from: nonzero indices sorted by descending x_adjusted
            nonzero_indices = np.nonzero(x_adjusted)[0]
            nz_vals = x_adjusted[nonzero_indices]
            order = np.argsort(-nz_vals)  # largest first
            split_sources = nonzero_indices[order]

            split_any = False

            for src in split_sources:
                if nnz >= target:
                    break

                src_val = x_adjusted[src]
                if src_val <= 1:
                    continue  # not enough to split

                # Choose a zero index with largest remaining capacity
                remaining_capacity_zero = (n_bar - x_adjusted)[zero_with_capacity]
                if len(remaining_capacity_zero) == 0:
                    break

                best_zero_idx = zero_with_capacity[np.argmax(remaining_capacity_zero)]

                capacity_left = n_bar[best_zero_idx] - x_adjusted[best_zero_idx]
                if capacity_left <= 0:
                    zero_with_capacity = zero_with_capacity[zero_with_capacity != best_zero_idx]
                    continue

                # Move at most half of src_val, but not more than capacity_left, and at least 1
                move = min(src_val // 2, capacity_left)
                if move <= 0:
                    continue

                # Perform split
                x_adjusted[src] -= move
                x_adjusted[best_zero_idx] += move

                nnz += 1
                split_any = True
                zero_with_capacity = zero_with_capacity[zero_with_capacity != best_zero_idx]

                if len(zero_with_capacity) == 0:
                    break

            if not split_any:
                # No way to create new nonzeros given capacities
                break

    return x_adjusted


def set_beta_binomial_params(
        contamination_config: Dict[str, Any],
        consignment: Consignment
) -> Dict[str, Any]:
    """Set beta-binomial parameters based on plant quantity in a consignment.

    Args:
        contamination_config: Contamination configuration dictionary from the
            main config file.
        consignment: Consignment object providing plant-level information.

    Returns:
        A dictionary with beta-binomial parameters (e.g., alpha, beta, theta,
        J, N_bar, p) for the given consignment.

    Warns:
        UserWarning: If no plant information is available on the consignment,
            default parameters are returned.
    """
    beta_binomial_params = {}
    # Get the number of plants on the consignment
    if consignment.get('num_plants') is None:
        if consignment.get('plants') is None:
            warnings.warn(
                "Attempting to set the beta binomial parameters in the 'set_beta_binomial_params' function"
                " of the contamination.py module and no plant information was found (i.e., no 'num_plants'"
                " or 'plants' attribute in the consignment object).  Default values are being set"
                " for parameters that will not reflect any data used for training.",
                UserWarning
            )
            return contamination_config["contamination_rate"]["beta_binomial_parameters"]['default']
        else:
            num_plants = len(consignment.get('plants'))
    else:
        num_plants = consignment.get('num_plants')

    # Get the appropriate alpha and beta parameters based on the plant quantity of the consignment, otherwise default to the default parameters
    param_dict = contamination_config["contamination_rate"]["beta_binomial_parameters"]
    key = get_range_key(param_dict, num_plants)
    beta_binomial_params = dict(param_dict[key] if key is not None else param_dict["default"])

    # Get J and actual N values per sample unit
    all_sample_unit_objects = []
    for inspection_unit in consignment.inspection_units:
        all_sample_unit_objects.extend(inspection_unit.included_unit_objects)

    if not all_sample_unit_objects:
        warnings.warn("No sample units found in consignment", UserWarning)
        return contamination_config["contamination_rate"]["beta_binomial_parameters"]['default']

    beta_binomial_params['J'] = len(all_sample_unit_objects)

    # Use actual plant counts per sample unit
    actual_n = np.array([len(su.plants) for su in all_sample_unit_objects])
    beta_binomial_params['N_bar'] = actual_n  # Array of plant unit counts

    # Get theta parameter
    if beta_binomial_params['theta'] is None:
        beta_binomial_params['theta'] = np.inf

    # Set clustering parameter. Prefer the selected parameter block and only
    # fall back to the default block when the selected one has no explicit p.
    selected_p = beta_binomial_params.get('p')
    if selected_p is None:
        selected_p = param_dict.get('default', {}).get('p')
    if selected_p is None:
        beta_binomial_params['p'] = 0
    else:
        beta_binomial_params['p'] = 1 - float(selected_p)

    return beta_binomial_params


def add_contaminant_beta_binomial(
    beta_binomial_config: Dict[str, Any],
    rng: Generator
) -> np.ndarray:
    """Draw contaminant counts per sample unit from a beta-binomial model.

    This function simulates contamination counts per sample unit using a
    beta-binomial model with an optional clustering adjustment (parameter
    ``p``). When clustering is enabled, contamination mass can be collapsed
    into fewer units, subject to capacity constraints.

    Args:
        beta_binomial_config: Dictionary of beta-binomial parameters with keys:
            * ``alpha``: Shape parameter of the Beta prior for the group-level
              contamination probability.
            * ``beta``: Shape parameter of the Beta prior for the group-level
              contamination probability.
            * ``theta``: Precision/dispersion parameter for the Beta distribution
              of cell-level probabilities (may be ``np.inf`` for no dispersion).
            * ``N_bar``: Number of plants per cell (sample unit), scalar or
              array-like.
            * ``J``: Number of cells (sample units) to simulate.
            * ``p``: Clustering parameter in [0, 1], where 0 means no clustering
              and 1 means fully clustered.
        rng: Numpy random Generator to use for sampling.

    Returns:
        One-dimensional array of length ``J`` containing the number of infected
        plants per sample unit.
    """
    alpha = beta_binomial_config["alpha"]
    beta = beta_binomial_config["beta"]
    theta = beta_binomial_config["theta"]
    N_bar = beta_binomial_config["N_bar"]
    I = 1
    J = beta_binomial_config['J']

    # Sample from beta p_i ~ Beta(alpha, beta), shape (I,)
    p_i = rng.beta(alpha, beta)

    if np.isinf(theta):
        # Degenerate case: p_ij = p_i for all J cells
        p_ij = np.full(J, p_i)
    else:
        # Draw J samples from Beta(theta*p_i, theta*(1-p_i))
        p_ij = rng.beta(theta * p_i, theta * (1 - p_i), size=J)

    # Convert N_bar to array if it's a scalar
    N_bar = np.atleast_1d(N_bar)
    if N_bar.size == 1:
        N_bar = np.full(J, N_bar[0])  # Broadcast scalar to all J

    # Draw X_ij from Binomial(N_bar, p_ij) for each of the J cells
    X = rng.binomial(N_bar, p_ij)

    # Apply clustering
    if beta_binomial_config['p'] > 0 and sum(X) > 0:
        n = min(int(round(J * (1 - beta_binomial_config['p']), 0)), len(X))
        m = len(X)

        # Choose indices to become zero
        if n == m:
            zero_idx = rng.choice(m, size=n - 1, replace=False)
        else:
            zero_idx = rng.choice(m, size=n, replace=False)

        # Identify indices that remain nonzero-eligible
        nonzero_idx = np.setdiff1d(np.arange(m), zero_idx)

        # Store values that will be removed
        values_to_redistribute = X[zero_idx].copy()

        # Zero out chosen indices
        X[zero_idx] = 0

        # Redistribute any nonzero removed values
        for val in values_to_redistribute:
            if val != 0:
                target = rng.choice(nonzero_idx)
                X[target] += val

        # Check for overload and, if necessary, apply heuristic adjustment
        if np.any(X > N_bar):
            X = heuristic_adjust_nonzeros(X, N_bar, len(nonzero_idx))
    return X


def synchronize_contamination_arrays_from_plants(consignment: Consignment) -> None:
    """Synchronize sample-unit and plant arrays with plant-level contamination.

    This function updates the consignment's sample-unit and plant-level arrays
    to reflect the contamination status encoded in the nested SampleUnit
    objects under each InspectionUnit.

    Args:
        consignment: Consignment instance whose inspection_units and nested
            SampleUnit objects contain plant-level contamination.
    """
    if not hasattr(consignment, "inspection_units"):
        return

    global_sample_unit_idx = 0
    global_plant_idx = 0
    has_global_sample_units = hasattr(consignment, "sample_units") and consignment.sample_units is not None
    has_global_plants = hasattr(consignment, "plants") and consignment.plants is not None

    for inspection_unit in consignment.inspection_units:
        sample_unit_objects = getattr(inspection_unit, "included_unit_objects", [])
        for local_su_idx, sample_unit_object in enumerate(sample_unit_objects):
            contaminated_plants_in_sample_unit = int(np.count_nonzero(sample_unit_object.plants))

            if hasattr(inspection_unit, "included_units") and local_su_idx < len(inspection_unit.included_units):
                inspection_unit.included_units[local_su_idx] = contaminated_plants_in_sample_unit

            if has_global_sample_units and global_sample_unit_idx < len(consignment.sample_units):
                consignment.sample_units[global_sample_unit_idx] = contaminated_plants_in_sample_unit
            global_sample_unit_idx += 1

            if has_global_plants:
                plant_values = np.asarray(sample_unit_object.plants, dtype=np.int64)
                n_plants = len(plant_values)
                end_idx = min(global_plant_idx + n_plants, len(consignment.plants))
                write_n = end_idx - global_plant_idx
                if write_n > 0:
                    consignment.plants[global_plant_idx:end_idx] = plant_values[:write_n]
                global_plant_idx += n_plants

###########################################
## END:  APL Added New Support Functions ##
###########################################

# This function is not used or working, consider updating or removing.
# This function is not used or working, consider updating or removing.
def add_contaminant_to_random_box(config,
                                  consignment,
                                  contamination_rate=None,
                                  rng: Generator = None
                                  ) -> None:
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

def get_contamination_rate(config, rng: Generator = None):
    """Return contamination rate based on contamination-rate configuration.

    Args:
        config: Contamination-rate configuration dictionary containing a
            ``distribution`` key and associated parameters.
        rng: Random number generator, required for stochastic distributions.

    Returns:
        Contamination rate as a float.

    Raises:
        RuntimeError: If the contamination-rate distribution is unknown.
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
        return float(stats.beta.rvs(param1, param2, size=1)[0])
    elif distribution in ["beta_binomial", "beta-binomial"]:
        params = config.get("beta_binomial_parameters", {})
        alpha = float(params['default'].get("alpha", 0))
        beta = float(params['default'].get("beta", 0))
        denom = alpha + beta
        return 0.0 if denom <= 0 else alpha / denom
    raise RuntimeError(f"Unknown contamination rate distribution: {distribution}")


def num_items_to_contaminate(config, num_items, rng: Generator = None):
    """Return the number of items to be contaminated.

    The number is computed as ``num_items * contamination_rate`` and rounded
    to the nearest integer.

    Args:
        config: Contamination-rate configuration dictionary.
        num_items: Total number of items available for contamination.
        rng: Random number generator to be passed to contamination-rate logic.

    Returns:
        Integer number of items to contaminate.
    """
    contamination_rate = get_contamination_rate(config, rng=rng)
    contaminated_items = round(num_items * contamination_rate)
    return contaminated_items


def num_boxes_to_contaminate(config, num_boxes):
    """Return the number of boxes to be contaminated as a float.

    Args:
        config: Contamination-rate configuration dictionary.
        num_boxes: Total number of boxes in the consignment.

    Returns:
        Expected number of contaminated boxes as a float.
    """
    contamination_rate = get_contamination_rate(config)
    contaminated_boxes = num_boxes * contamination_rate
    return contaminated_boxes


def add_contaminant_uniform_random(
        config,
        consignment,
        rng: Generator
):
    """Add contaminants to a consignment using a uniform random distribution.

    Contamination rate is determined using the ``contamination_rate`` entry in
    the contamination configuration.

    Args:
        config: Contamination configuration dictionary, including
            ``contamination_unit`` and ``contamination_rate``.
        consignment: Consignment object to contaminate (boxes/items/plants).
        rng: Random number generator.
    """
    contamination_unit = config["contamination_unit"]
    if contamination_unit in ["box", "boxes"]:
        contaminated_boxes = num_boxes_to_contaminate(
            config["contamination_rate"], consignment.num_boxes
        )
        if contaminated_boxes == 0.0:
            return
        if rng is None:
            box_indexes = np.random.choice(
                consignment.num_boxes, math.ceil(contaminated_boxes), replace=False
            )
        else:
            box_indexes = rng.choice(
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
            config["contamination_rate"], consignment.num_items, rng=rng
        )
        if contaminated_items == 0:
            return
        if rng is None:
            item_indexes = np.random.choice(
                consignment.num_items, contaminated_items, replace=False
            )
        else:
            item_indexes = rng.choice(
                consignment.num_items, contaminated_items, replace=False
            )
        np.put(consignment.items, item_indexes, 1)
        assert np.count_nonzero(consignment.items) == contaminated_items

    elif contamination_unit in ["plant", "plants"]:
        # Contaminate plants directly per inspection unit
        if config["contamination_rate"]['distribution'] == 'beta-binomial':
            beta_binomial_params = set_beta_binomial_params(config, consignment)
            contaminated_plants = np.asarray(add_contaminant_beta_binomial(
                beta_binomial_config=beta_binomial_params,
                rng=rng
            ), dtype=int).ravel()
            if np.all(contaminated_plants == 0):
                return
        else:
            # Fallback fixed-rate contamination across all plants
            total_plants = sum(len(su.plants) for iu in consignment.inspection_units for su in iu.included_unit_objects)
            contaminated_items = num_items_to_contaminate(
                config["contamination_rate"], total_plants
            )
            contaminated_plants = np.zeros(total_plants, dtype=int)
            if contaminated_items > 0:
                # Distribute proportionally by plant counts per inspection unit
                unit_sizes = [sum(len(su.plants) for su in iu.included_unit_objects) for iu in consignment.inspection_units]
                total_size = sum(unit_sizes)
                for idx, size in enumerate(unit_sizes):
                    share = int(round(contaminated_items * size / total_size)) if total_size else 0
                    contaminated_plants[idx] = min(share, size)
            if contaminated_plants.sum() == 0:
                return

        # Apply contamination per SAMPLE UNIT
        if len(contaminated_plants) != len(consignment.sample_units):
            print(f"WARNING: contaminated_plants length ({len(contaminated_plants)}) "
                  f"!= sample_units length ({len(consignment.sample_units)})")

        for inspection_unit in consignment.inspection_units:
            for sample_unit in inspection_unit.included_unit_objects:
                if contaminated_plants[sample_unit.id] <= 0:
                    continue
                # If more contaminated plants than exist, then contaminate entire sample unit
                if contaminated_plants[sample_unit.id] > sample_unit.num_plants:
                    contaminated_plants[sample_unit.id] = sample_unit.num_plants

                # Randomly select k plants to contaminate in this sample unit
                chosen_indices = rng.choice(sample_unit.num_plants, size=contaminated_plants[sample_unit.id], replace=False)
                sample_unit.plants[chosen_indices] = 1

        # Update consignment.sample_units to sum of contaminated plants
        sample_unit_counter = 0
        for inspection_unit in consignment.inspection_units:
            for sample_unit_object in inspection_unit.included_unit_objects:
                consignment.sample_units[sample_unit_counter] = sample_unit_object.plants.sum()
                sample_unit_counter += 1

        # Verify contamination count
        total_contaminated = sum(
            (sample_unit_object.plants == 1).sum()
            for inspection_unit in consignment.inspection_units
            for sample_unit_object in inspection_unit.included_unit_objects
        )

        expected = int(np.sum(contaminated_plants))
        if total_contaminated != expected:
            print(f"WARNING: Contaminated plant count mismatch. Expected {expected}, got {total_contaminated}.")
    else:
        raise RuntimeError(f"Unknown contamination unit: {contamination_unit}")


def _contaminated_items_to_cluster_sizes(
    contaminated_items, contaminated_units_per_cluster
):
    """Return list of cluster sizes for a given number of contaminated items.

    The size of each cluster is limited by ``contaminated_units_per_cluster``.
    If the number of contaminated items exceeds the per-cluster limit, items
    are split into multiple clusters, with the last cluster taking the
    remainder.

    Args:
        contaminated_items: Total number of items to contaminate.
        contaminated_units_per_cluster: Maximum number of items per cluster.

    Returns:
        List of integer cluster sizes whose sum equals ``contaminated_items``.
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
    """Return list of cluster sizes for a given number of contaminated boxes.

    The size of each cluster is limited by ``contaminated_units_per_cluster``.
    If the number of contaminated boxes exceeds the per-cluster limit, boxes
    are split into multiple clusters.

    Args:
        contaminated_boxes: Total number of boxes to contaminate (float).
        contaminated_units_per_cluster: Maximum number of boxes per cluster.

    Returns:
        List of integer cluster sizes whose sum equals the rounded-up number
        of contaminated boxes.
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


def add_contaminant_clusters_to_items_with_subset_clustering(config, consignment):
    """Add contaminant cluster to items in a consignment using a single parameter

    Clustering equal to 0 means all items in the consignment can be contaminated with
    equal probability, i.e., the cluster spreads over the whole consignment. Clustering
    equal to 1 means that all items in the cluster are contaminated. The size of the
    cluster is then directly determined by the contamination rate.
    If the cluster would spread over the end of the consignment, we put the extra part
    of the cluster at the beginning of the consignment.
    """
    clustering = config["clustered"]["value"]
    num_of_contaminated_items = num_items_to_contaminate(
        config["contamination_rate"], consignment.num_items
    )
    if num_of_contaminated_items == 0:
        return
    subset_size = round(consignment.num_items * (1 - clustering))
    subset_size = max(subset_size, num_of_contaminated_items)
    start_index2 = None
    end_index2 = None
    if subset_size == consignment.num_items:
        start_index = 0
        end_index = consignment.num_items
    else:
        # Place the beginning of the cluster anywhere,
        # but put the overhang at the beginning.
        start_index = np.random.randint(0, consignment.num_items)
        if start_index + subset_size > consignment.num_items:
            start_index2 = 0
            end_index2 = subset_size - (consignment.num_items - start_index)
            end_index = consignment.num_items
            assert (end_index - start_index) + (
                end_index2 - start_index2
            ) == subset_size
        else:
            end_index = start_index + subset_size
            assert end_index - start_index == subset_size

    potential_indexes = np.arange(start_index, end_index)
    if start_index2 is not None and end_index2 is not None:
        potential_indexes = np.concatenate(
            (potential_indexes, np.arange(start_index2, end_index2))
        )
    assert len(potential_indexes) == subset_size
    indexes = np.random.choice(
        potential_indexes,
        num_of_contaminated_items,
        replace=False,
    )
    consignment.items[indexes] = 1
    assert np.count_nonzero(consignment.items) == num_of_contaminated_items


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


def add_contaminant_clusters(config, consignment, rng: Generator = None):
    """Add contaminant clusters to consignment

    Item (separately or in boxes) with contaminant in *consignment* evaluate
    to True after running this function.
    This function does not touch the not items not selected for contamination.
    However, they are expected to be zero.
    """
    contamination_unit = config["contamination_unit"]
    if contamination_unit in ["box", "boxes"]:
        if config["clustered"]["distribution"] == "single":
            raise RuntimeError(
                "clustering distribution 'single' is not supported for boxes"
            )
        add_contaminant_clusters_to_boxes(config, consignment)
    elif contamination_unit in ["item", "items"]:
        if config["clustered"]["distribution"] == "single":
            add_contaminant_clusters_to_items_with_subset_clustering(
                config, consignment
            )
        else:
            add_contaminant_clusters_to_items(config, consignment)
    else:
        raise RuntimeError(f"Unknown contamination unit: {contamination_unit}")


def consignment_matches_selection_rule(rule, consignment):
    """Return True if a consignment matches a given selection rule.

    Args:
        rule: Dictionary describing selection criteria such as commodity,
            origin, port, start_date, and end_date.
        consignment: Consignment whose attributes are compared against the rule.

    Returns:
        True if all applicable criteria match, otherwise False.
    """
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


def get_contamination_config_for_consignment(config, consignment, rng: Generator = None):
    """Return contamination configuration for a specific consignment.

    If ``config`` contains consignment-specific settings under the
    ``consignments`` key, contamination configuration is selected based on
    specified rules (commodity, origin, port, date range, and probability).
    If a rule matches and passes its probability challenge, a consignment-
    specific contamination configuration is returned; otherwise, None is
    returned.

    When a matching rule includes a ``contamination`` key, that value is used
    as the consignment-specific configuration. If the rule also includes
    ``use_contamination_defaults: true``, the top-level contamination
    configuration is used as a base and the nested ``contamination`` block is
    applied on top via a nested dictionary update.

    If there is no consignment-specific configuration, the top-level
    contamination configuration is returned (copied). If the top-level
    configuration does not contain a ``consignments`` key at all, a copy of
    the provided configuration is always returned.

    Args:
        config: Global contamination configuration dictionary. May contain a
            ``consignments`` key with consignment-specific rules.
        consignment: Consignment to match against selection rules.
        rng: Random number generator used for probability checks.

    Returns:
        A copy of the contamination configuration dictionary appropriate for
        the given consignment, or None if the consignment is not selected.
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
            if probability is None or rng.random() < probability:
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


def create_contaminant_function(
        config,
        rng: Generator,
):
    """Create a contaminant-adding function from contamination configuration.

    An ``arrangement`` key must be provided in ``config["contamination"]`` to
    specify which contamination function should be used (e.g., random, clustered).

    Args:
        config: Contamination configuration dictionary.
        rng: Random number generator.

    Returns:
        A function that takes a Consignment and applies contamination according
        to the specified arrangement.

    Raises:
        RuntimeError: If the arrangement is missing or unknown.
    """
    arrangement = config.get("arrangement")
    if arrangement == "random_box":

        def add_contaminant_function(consignment):
            return add_contaminant_to_random_box(
                config=config["random_box"],
                consignment=consignment,
                contamination_rate=config["contamination_rate"],
                rng=rng,
            )

    elif arrangement == "random":

        def add_contaminant_function(consignment):
            return add_contaminant_uniform_random(
                config=config,
                consignment=consignment,
                rng=rng
            )

    elif arrangement == "clustered":

        def add_contaminant_function(consignment):
            return add_contaminant_clusters(
                config=config,
                consignment=consignment,
                rng=rng
            )

    elif arrangement is None:
        raise RuntimeError("Contaminant arrangement must be set")
    else:
        raise RuntimeError(f"Unknown contaminant arrangement: {arrangement}")
    return add_contaminant_function


def get_contaminant_function(
        config,
        rng: Generator = None,
):
    """Return a function that adds contaminant to a consignment.

    If the contamination configuration contains a ``consignments`` key, the
    returned function first selects an appropriate consignment-specific
    configuration (based on rules) and then applies the corresponding
    contamination function. Otherwise, it directly constructs a contamination
    function from the top-level configuration.

    Args:
        config: Full configuration dictionary containing a ``contamination``
            section.
        rng: Random number generator.

    Returns:
        A function that takes a Consignment and applies contamination
        according to the configuration.
    """
    if "consignments" in config["contamination"]:
        # If there is config for individual consignments, we define a new function
        # which first picks the right config based on its consignment parameter, then
        # creates an add contaminant function based on this config, and then it calls
        # the function with the consignment.

        def add_contaminant_function(consignment):
            """Pick config for the consignment and then call the specific function."""
            consignment_specific_config = get_contamination_config_for_consignment(
                config["contamination"], consignment, rng=rng
            )
            if not consignment_specific_config:
                # Do not contaminate this consignment.
                # No modification to the existing consignment provided as a parameter
                # and returning None (as all the add contaiminant functions do).
                return None
            contaminant_function = create_contaminant_function(
                consignment_specific_config,
                rng=rng
            )
            return contaminant_function(consignment)

        return add_contaminant_function

    # If there is no config for individual consignments, we just create the function with
    # the default settings.
    return create_contaminant_function(config["contamination"], rng=rng)
