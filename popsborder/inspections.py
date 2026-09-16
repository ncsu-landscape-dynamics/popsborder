# Simulation of contaminated consignments and their inspections
# Copyright (C) 2018-2021 Vaclav Petras and others (see below)
# © 2026 The Johns Hopkins University Applied Physics Laboratory LLC

"""
==========================================================================================
Johns Hopkins University Applied Physics Laboratory (JHU/APL) Extensions and Modifications
==========================================================================================

Contributors: Gary Lin, Joseph Agor (JHU/APL)

Modifications:
    New Functions Added
    ----------------
    - construct_risk_units():
        * Takes in data and a config file to reassign inspection units to risk units
    - relabel_risk_units():
        * Relabel RISK_UNIT IDs based on unique combinations of grouping variables.
    - load_compliance_lookup():
        * Loads compliance lookup dictionary from pickle file.
    - sample_rbs():
        * Implements risk-based sampling methodology using compliance-based detection levels
        * Retrieves country/propagative material specific compliance parameters from lookup table
        * Calculates sample size using hypergeometric distribution based on risk assessment

    - count_contaminated_inspection_units():
        * Counts contaminated inspection units in consignment
        * Supports refactored terminology (inspection_units vs boxes)

    - count_contaminated_sample_units():
        * Counts contaminated sample units in consignment
        * Supports refactored terminology (sample_units vs items)

    - get_detection_and_confidence():
        * Adds ability to process compliance tables beyond just origin and PM Type

    - _norm():
        * Support function to normalize for matching text: lowercase, strip non-alphanum.

    - normalize_rbs_variables_against_consignment():
        * Maps free-form field names in rbs_variables to actual attributes on a Consignment
          instance, using case-insensitive aliasing

    - fuzzy_match_attribute():
        * Attempts fuzzy matching using substring/word matching.

    - normalize_rbs_variables_using_risk_unit_config():
        * Map free-form field names in rbs_variables to actual RiskUnit attributes defined
          in RiskUnitConfig, using case-insensitive aliasing.
    ----------------

    Following Functions Modified
    ----------------
    - select_units_to_inspect():
        * Unified function for selecting units to inspect based on selection strategy
        * Supports random, cluster, and convenience selection strategies
        * Handles both inspection_unit and sample_unit selection

    - get_sample_function():
        * Added RBS structured consignment inspection
        * Enhanced to support compliance table parameter passing

    - sample_proportion():
        * Added backward compatibility for min_inspection_units (formerly min_boxes)
        * Updated to handle both old and new terminology in configuration

    - sample_n():
        * Added backward compatibility for within_inspection_unit_proportion (formerly within_box_proportion)
        * Added backward compatibility for min_inspection_units (formerly min_boxes)

    - convert_items_to_boxes_fixed_proportion() :
        * Added backward compatibility for within_inspection_unit_proportion
        * Converted to the convert_sample_units_to_inspection_units_fixed_proportion()

    - compute_max_inspectable_items():
        * Added backward compatibility for within_sample_unit_proportion
        * Converted to the function compute_max_inspectable_sample_units()

    - compute_n_clusters_to_inspect():
        * Added backward compatibility for within_inspection_unit_proportion and min_inspection_units

    - inspect():
        * Added backward compatibility for within_inspection_unit_proportion
        * Enhanced detailed tracking with sample_unit_in_inspection_unit_to_sample_unit_index()

    - inspect_item():
        * Converted to the function inspect_sample_unit()

    - get_detection_and_confidence():
        * Added ability to process beyond just origin and PM Type
    ----------------

    Terminology Refactoring
    ----------------
    - Systematically refactored: boxes -> inspection_units, items -> sample_units
    - Updated all class names, method names, and variable names for consistency
    - Added comprehensive backward compatibility for existing configurations
    - Maintained dual access patterns for smooth migration from legacy terminology
    ----------------

    Backward Compatibility
    ----------------
    - Added aliases: count_contaminated_boxes() -> count_contaminated_inspection_units()
    - Added aliases: count_contaminated_items() -> count_contaminated_sample_units()
    - Configuration parameter mapping: boxes -> inspection_units, items -> sample_units
    - Maintained support for legacy configuration keys while enabling new terminology
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


"""Inspections of consignments.

.. codeauthor:: Vaclav Petras <wenzeslaus gmail com>
.. codeauthor:: Kellyn P. Montgomery <kellynmontgomery gmail com>
.. codeauthor:: Gary Lin <Gary.Lin jhuapl edu>
.. codeauthor:: Joseph Agor <Joseph.Agor jhuapl edu>
"""

import math
import pickle
import random
import re
import types
import warnings
from collections import defaultdict
from difflib import get_close_matches
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import numpy as np
import pandas as pd
from numpy.random import Generator

from .inputs import get_validated_effectiveness, load_compliance_lookup_csv
from slippage_model_utils.UnitAttributes import RiskUnitConfig
from slippage_model_utils.paths import DefaultPaths
from slippage_model_utils.references import (
    country_of_origin_names,
    find_column_name,
    get_domain_specific_aliases,
    pm_type_names,
    possible_pis_stations,
)

SAMPLE_UNIT_ALIASES = {"sample_unit", "sample_units", "item", "items"}
INSPECTION_UNIT_ALIASES = {"inspection_unit", "inspection_units", "box", "boxes"}


def _is_sample_unit_unit(unit: str) -> bool:
    """Return True if the given unit string refers to a sample unit."""
    return unit in SAMPLE_UNIT_ALIASES


def _is_inspection_unit_unit(unit: str) -> bool:
    """Return True if the given unit string refers to an inspection unit."""
    return unit in INSPECTION_UNIT_ALIASES


def _get_min_inspection_units(config: dict) -> int:
    """Return minimum number of inspection units to inspect from config."""
    inspection_cfg = config["inspection"]
    return inspection_cfg.get("min_inspection_units", inspection_cfg.get("min_boxes", 0))


def _get_within_inspection_unit_proportion(config: dict) -> float:
    """Return within-inspection-unit sampling proportion with backward compatibility.

    Falls back to ``within_box_proportion`` if
    ``within_inspection_unit_proportion`` is not present.
    """
    inspection_cfg = config["inspection"]
    return inspection_cfg.get(
        "within_inspection_unit_proportion",
        inspection_cfg.get("within_box_proportion", 1.0),
    )


def _get_unit_population(consignment, unit: str) -> int:
    """Return the population size for the given sampling unit type.

    Args:
        consignment: Consignment object.
        unit: String indicating unit type (sample_unit/sample_units/item/items
            or inspection_unit/inspection_units/box/boxes).

    Returns:
        The number of units in the consignment for the specified unit type.

    Raises:
        RuntimeError: If the unit type is unknown.
    """
    if _is_sample_unit_unit(unit):
        return consignment.num_sample_units
    if _is_inspection_unit_unit(unit):
        return consignment.num_inspection_units
    raise RuntimeError(f"Unknown unit: {unit}")


def _select_convenience_indexes(unit: str, consignment, n_units_to_inspect: int) -> List[int]:
    """Return the first n unit indexes (convenience sampling)."""
    return list(range(min(n_units_to_inspect, _get_unit_population(consignment, unit))))


def load_compliance_lookup(
        filename: Union[str, Path]
) -> Dict:
    """Load compliance lookup dictionary from a pickle file.

    The function looks for the file either at the given path or in the
    default compliance directory.

    Args:
        filename: Name or path of the pickle file (e.g.,
            ``'compliance_lookup_final.pkl'``).

    Returns:
        Compliance lookup dictionary loaded from the pickle file.

    Raises:
        FileNotFoundError: If the pickle file cannot be found.
    """
    default_paths = DefaultPaths()

    candidate_path = Path(filename)
    if candidate_path.exists():
        full_path = candidate_path
    else:
        full_path = default_paths.compliance_dir() / candidate_path.name

    if not full_path.exists():
        raise FileNotFoundError(
            f"Compliance lookup file not found: {full_path}\n"
            f"Expected location: {default_paths.compliance_dir()}\n"
            f"Please ensure the pickle file is in the correct directory."
        )

    with full_path.open("rb") as f:
        compliance_table_dict = pickle.load(f)

    return compliance_table_dict


def relabel_risk_units(group, risk_unit_grouping_variables):
    """Relabel RISK_UNIT IDs based on grouping variables.

    For each inspection (group), the function assigns new RISK_UNIT IDs
    based on unique combinations of grouping variables.

    Args:
        group: DataFrame representing one inspection group, must contain
            ``'RISK_UNIT'`` and ``'INSPECTION_NUMBER'``.
        risk_unit_grouping_variables: List of column names by which risk
            units should be distinguished.

    Returns:
        DataFrame with relabeled ``RISK_UNIT`` column.
    """
    # Extract the base number (before underscore)
    first_risk_unit = group['RISK_UNIT'].iloc[0]
    base_number = first_risk_unit.split('_')[0]
    inspection_num = str(group['INSPECTION_NUMBER'].iloc[0])

    # Create unique combinations of grouping variables
    # Use factorize to assign sequential IDs to unique combinations
    group_combinations = group[risk_unit_grouping_variables].apply(
        lambda row: '_'.join(row.astype(str)), axis=1
    )

    # Get unique IDs for each combination (1-indexed)
    _, unique_ids = pd.factorize(group_combinations)
    unique_id_map = {combo: idx + 1 for idx, combo in enumerate(unique_ids)}

    # Map each row to its new ID
    new_ids = group_combinations.map(unique_id_map)

    # Create new RISK_UNIT values
    group['RISK_UNIT'] = inspection_num + '_' + 'risk_unit' + '_' + new_ids.astype(str)

    return group


def construct_risk_units(config: dict = None, data: pd.DataFrame = None):
    """Reassign inspection units to risk units using configuration rules.

    This function processes each inspection (``INSPECTION_NUMBER``) and
    groups rows based on configurable risk-unit grouping variables, which
    may depend on the PIS station.

    Args:
        config: Configuration dictionary containing
            ``inspection.rbs_calculator_grouping_variables``.
        data: DataFrame whose rows represent inspection units/commodity lines
            and contain ``INSPECTION_NUMBER`` and ``INSPECTION_LOCATION_NAME`` columns.

    Returns:
        DataFrame with updated ``RISK_UNIT`` values per inspection.
    """
    # Get the PIS Station for the consignment and the corresponding Risk Unit Group variables
    rbs_calculator_grouping_variables_stations = list(config["inspection"]["rbs_calculator_grouping_variables"].keys())

    def process_inspection_group(group):
        """Process each unique inspection number."""
        # Get the inspection number from the group name
        inspection_number = group.name
        # Add the INSPECTION_NUMBER column back to the result
        group = group.copy()  # Make a copy to avoid SettingWithCopyWarning
        group['INSPECTION_NUMBER'] = inspection_number

        port_name = list(group['INSPECTION_LOCATION_NAME'])[0]

        match = get_close_matches(port_name, rbs_calculator_grouping_variables_stations, n=1, cutoff=0.6)
        pis_station = match[0] if match else None

        if pis_station is None:
            if ('default' in config["inspection"]["rbs_calculator_grouping_variables"].keys()
                    and len(config["inspection"]["rbs_calculator_grouping_variables"]['default']) > 0):
                default_list = config["inspection"]["rbs_calculator_grouping_variables"]['default']
                warnings.warn(
                    f"PIS Station ---{port_name}--- for the consignment not found in config. "
                    f"Using defaults found in config for risk unit grouping variables: {default_list}",
                    UserWarning,
                    stacklevel=2
                )
                risk_unit_grouping_variables = [
                    x.lower().replace(' ', '_').replace('-', '_').replace('.', '_')
                    for x in config["inspection"]["rbs_calculator_grouping_variables"]['default']
                ]
            else:
                default_list = ['origin', 'material_type']
                warnings.warn(
                    f"PIS Station ---{port_name}--- for the consignment not found in config."
                    f"Also, no defaults found in config so risk unit group variables being defaulted to...{default_list}",
                    UserWarning,
                    stacklevel=2
                )
                risk_unit_grouping_variables = ['origin', 'material_type']
        else:
            if len(config["inspection"]["rbs_calculator_grouping_variables"][pis_station]) == 0:
                default_list = ['origin', 'material_type']
                warnings.warn(
                    f"PIS Station ---{port_name}--- for the consignment found in config."
                    f"However, no grouping variables found in the config, so risk unit group variables being defaulted to...{default_list}",
                    UserWarning,
                    stacklevel=2
                )
                risk_unit_grouping_variables = ['origin', 'material_type']
            else:
                risk_unit_grouping_variables = [
                    x.lower().replace(' ', '_').replace('-', '_').replace('.', '_')
                    for x in config["inspection"]["rbs_calculator_grouping_variables"][pis_station]
                ]

        for count, var in enumerate(risk_unit_grouping_variables):
            matching_column_name = find_column_name(var, list(group.columns))
            if matching_column_name is not None:
                risk_unit_grouping_variables[count] = matching_column_name
            else:
                raise ValueError(f'Variable {var} not a valid column for risk unit construction. ')

        # Relabel risk units based on grouping variables
        group = relabel_risk_units(group, risk_unit_grouping_variables)
        return group

    # Apply processing
    data_updated = data.groupby('INSPECTION_NUMBER', group_keys=False).apply(
        process_inspection_group,
        include_groups=False
    )
    return data_updated


def inspect_first(consignment):
    """Inspect only the first box in the consignment"""
    if consignment.boxes[0]:
        return False, 1
    return True, 1


def inspect_one_random(consignment):
    """Inspect only one randomly picked box in the consignment"""
    if random.choice(consignment.boxes):
        return False, 1
    return True, 1


def inspect_all(consignment):
    """Inspect all boxes in the consignment"""
    return not is_consignment_contaminated(consignment), consignment.num_boxes


def inspect_first_n(num_boxes, consignment):
    """Inspect only the first n boxes in the consignment

    :param num_boxes: Number of boxes to inspect
    :param consignment: Consignment to inspect
    """
    num_boxes = min(len(consignment.boxes), num_boxes)
    for i in range(num_boxes):
        if consignment.boxes[i]:
            return False, i + 1
    return True, num_boxes


def sample_proportion(config, consignment):
    """Set sample size to sample units from consignment using proportion strategy.
    Return number of units to inspect.

    :param config: Configuration to be used595
    :param consignment: Consignment to be inspected
    """
    unit = config["inspection"]["unit"]
    ratio = config["inspection"]["proportion"]["value"]
    num_items = consignment.num_items
    num_boxes = consignment.num_boxes
    min_boxes = config["inspection"]["min_boxes"]

    if unit in ["item", "items"]:
        n_units_to_inspect = round(ratio * num_items)
    elif unit in ["box", "boxes"]:
        n_units_to_inspect = round(ratio * num_boxes)
        n_units_to_inspect = max(min_boxes, n_units_to_inspect)
        n_units_to_inspect = min(num_boxes, n_units_to_inspect)
    else:
        raise RuntimeError(f"Unknown sampling unit: {unit}")
    return n_units_to_inspect


def compute_hypergeometric(detection_level, confidence_level, population_size):
    """Compute sample size from a hypergeometric-based detection formula.

    The sample size is computed using the hypergeometric-based formula from
    the RBS spreadsheet (IICA, USDA APHIS PPQ, NAPPO) based on detection level
    and confidence level.

    Args:
        detection_level: Desired detection level (proportion).
        confidence_level: Desired confidence level (proportion).
        population_size: Size of the population (number of units).

    Returns:
        Integer sample size (capped at the population size).
    """
    detection_level = float(detection_level)
    confidence_level = float(confidence_level)

    # Equation comes from RBS spreadsheet for calculating hypergeometric
    # sample sizes created by IICA, USDA APHIS PPQ, and NAPPO.
    sample_size = math.ceil(
        (1 - ((1 - confidence_level) ** (1 / (detection_level * population_size))))
        * (population_size - (((detection_level * population_size) - 1) / 2))
    )

    # The computation gives sample size > num boxes when using 1% detection
    # Make max sample size = population size
    sample_size = min(sample_size, population_size)
    return sample_size


def sample_hypergeometric(config, consignment):
    """Compute sample size using hypergeometric detection/level strategy.

    Args:
        config: Configuration dictionary.
        consignment: Consignment to be inspected.

    Returns:
        Number of units to inspect.
    """
    unit = config["inspection"]["unit"]
    detection_level = config["inspection"]["hypergeometric"]["detection_level"]
    confidence_level = config["inspection"]["hypergeometric"]["confidence_level"]

    if (config.get("inspection_process", None) is not None) and (config['inspection_process'] == "RBS-PIS"):
        return compute_hypergeometric(
            detection_level,
            confidence_level,
            _get_unit_population(consignment, unit),
        )
    else:
        num_items = consignment.num_items
        num_boxes = consignment.num_boxes
        if unit in ["item", "items"]:
            n_units_to_inspect = compute_hypergeometric(
                detection_level, confidence_level, num_items
            )
        elif unit in ["box", "boxes"]:
            n_units_to_inspect = compute_hypergeometric(
                detection_level, confidence_level, num_boxes
            )
        else:
            raise RuntimeError(f"Unknown sampling unit: {unit}")
        return n_units_to_inspect


def sample_all(config, consignment):
    """Sample all units from a consignment.

    Args:
        config: Configuration dictionary.
        consignment: Consignment to be inspected.

    Returns:
        Number of units to inspect (entire population).
    """
    unit = config["inspection"]["unit"]
    if unit in ["item", "items"]:
        return consignment.num_items
    elif unit in ["box", "boxes"]:
        return consignment.num_boxes
    else:
        return _get_unit_population(consignment, unit)


def sample_n(config, consignment):
    """Set sample size to sample fixed number of units from consignment.
    Check if fixed number is <= max units for inspection.
    Return number of units to inspect.

    :param config: Configuration to be used
    :param consignment: Consignment to be inspected
    """
    fixed_n = config["inspection"]["fixed_n"]
    unit = config["inspection"]["unit"]
    within_box_proportion = config["inspection"]["within_box_proportion"]
    items_per_box = consignment.items_per_box
    num_items = consignment.num_items
    num_boxes = consignment.num_boxes
    min_boxes = config["inspection"]["min_boxes"]

    if unit in ["item", "items"]:
        max_items = compute_max_inspectable_items(
            num_items, items_per_box, within_box_proportion
        )
        # Check if max number of items that can be inspected is less than fixed number.
        n_units_to_inspect = min(max_items, fixed_n)
    elif unit in ["box", "boxes"]:
        n_units_to_inspect = fixed_n
        n_units_to_inspect = max(min_boxes, n_units_to_inspect)
        n_units_to_inspect = min(num_boxes, n_units_to_inspect)
    return n_units_to_inspect


def sample_rbs(
        config,
        consignment,
        rng: Generator = None,
):
    """Compute sample sizes per unit using RBS compliance levels.

    This function uses a risk-based sampling methodology driven by compliance
    levels, where detection and confidence levels are obtained from a
    compliance lookup table and used in hypergeometric calculations.

    Args:
        config: Configuration dictionary.
        consignment: Consignment to be inspected.
        rng: Optional random number generator.

    Returns:
        Mapping from risk-unit or inspection-unit ID to units-to-inspect.
    """
    unit = config["inspection"]["unit"]
    debug_print = config.get("debug", {}).get("print_compliance_levels", False)

    # Get filename from config
    compliance_table_lookup_filename = config["inspection"]["compliance_table"]['file_name']

    # Load compliance lookup
    compliance_table_dict = load_compliance_lookup(filename=compliance_table_lookup_filename)

    for key, val in list(compliance_table_dict.items()):
        # Only process entries where the key is a tuple and value is a tuple of two strings
        if isinstance(key, tuple) and isinstance(val, tuple) and len(val) == 2:
            str1, str2 = val
            compliance_table_dict[key] = (float(str1), float(str2))

    detection_confidence_levels = get_detection_and_confidence(
        consignment, compliance_table_dict, print_compliance_levels=False
    )
    n_units_to_inspect = {}
    if unit in ["sample_unit", "sample_units", "item", "items"]:
        risk_units = consignment.risk_units if consignment.risk_units else []
        if risk_units:
            risk_unit_by_id = {risk_unit.id: risk_unit for risk_unit in risk_units}
            for risk_unit_id, levels in detection_confidence_levels.items():
                detection_level, confidence_level = levels[0], levels[1]
                risk_unit = risk_unit_by_id.get(risk_unit_id)
                if risk_unit is None:
                    continue
                population_n = risk_unit.n_for_hypergeom
                if population_n <= 0:
                    continue

                n_for_risk = compute_hypergeometric(
                    detection_level, confidence_level, population_n
                )
                n_for_risk = max(0, min(n_for_risk, population_n))
                n_units_to_inspect[risk_unit_id] = n_for_risk
        else:
            # Fallback for legacy consignments without risk_units.
            for inspect_number in range(consignment.num_inspection_units):
                detection_level, confidence_level = detection_confidence_levels[inspect_number]
                population_n = consignment.inspection_units[inspect_number].num_sample_units
                n_units_to_inspect[inspect_number] = compute_hypergeometric(
                    detection_level, confidence_level, population_n
                )
    elif unit in ["inspection_unit", "inspection_units", "box", "boxes"]:
        num_sample_units = consignment.num_sample_units
        for inspect_number in detection_confidence_levels.keys():
            detection_level, confidence_level = detection_confidence_levels[inspect_number][0], \
                detection_confidence_levels[inspect_number][1]
            n_units_to_inspect[inspect_number] = compute_hypergeometric(
                detection_level, confidence_level, num_sample_units
            )
    else:
        raise RuntimeError(f"Unknown sampling unit: {unit}")
    return n_units_to_inspect



def convert_items_to_boxes_fixed_proportion(config, consignment, n_items_to_inspect):
    """Convert number of items to inspect to number of boxes to inspect based on
    the number of items per box and the proportion of items to inspect per box
    specified in the config. Adjust number of boxes to inspect to be at least
    the minimum number of boxes to inspect specified in the config and at most the
    total number of boxes in the consignment.
    Return number of boxes to inspect.

    :param config: Configuration to be used
    :param consignment: Consignment to be inspected
    :param n_items_to_inspect: Number of items to inspect defined in sample functions.
    """
    items_per_box = consignment.items_per_box
    within_box_proportion = config["inspection"]["within_box_proportion"]
    min_boxes = config["inspection"]["min_boxes"]
    num_boxes = consignment.num_boxes
    inspect_per_box = int(math.ceil(within_box_proportion * items_per_box))

    n_boxes_to_inspect = math.ceil(n_items_to_inspect / inspect_per_box)
    n_boxes_to_inspect = max(min_boxes, n_boxes_to_inspect)
    n_boxes_to_inspect = min(num_boxes, n_boxes_to_inspect)
    return n_boxes_to_inspect


def compute_n_clusters_to_inspect(config, consignment, n_items_to_inspect):
    """Compute number of cluster units (boxes) that need to be opened to achieve item
    sample size when using the cluster selection strategy. Use config within box
    proportion if possible or compute minimum number of items to inspect per box
    required to achieve item sample size.
    Return number of boxes to inspect and number of items to inspect per box.

    :param config: Configuration to be used
    :param consignment: Consignment to be inspected
    :param n_items_to_inspect: Number of items to inspect defined by sample functions.
    """
    cluster_selection = config["inspection"]["cluster"]["cluster_selection"]
    items_per_box = consignment.items_per_box
    within_box_proportion = config["inspection"]["within_box_proportion"]
    min_boxes = config["inspection"]["min_boxes"]
    num_boxes = consignment.num_boxes
    num_items = consignment.num_items

    if cluster_selection == "random":
        # Check if within box proportion is high enough to achieve sample size.
        max_items = compute_max_inspectable_items(
            num_items, items_per_box, within_box_proportion
        )
        if max_items >= n_items_to_inspect:
            inspect_per_box = math.ceil(within_box_proportion * items_per_box)
            n_boxes_to_inspect = math.ceil(n_items_to_inspect / inspect_per_box)
        else:
            # If not, divide sample size across number of boxes to get number
            # of items to inspect per box.
            print(
                "Warning: Within box proportion is too low to achieve sample size. "
                "Automatically increasing within box proportion to achieve sample size."
            )
            inspect_per_box = math.ceil(n_items_to_inspect / num_boxes)
            n_boxes_to_inspect = math.ceil(n_items_to_inspect / inspect_per_box)

    elif cluster_selection == "interval":  # Every nth box, where n = interval
        interval = config["inspection"]["cluster"]["interval"]
        # Maximum num boxes that can be inspected based on interval.
        # Should be at least 1.
        max_boxes = max(1, round(num_boxes / interval))
        # Assumes full boxes, no remainder partial box.
        max_items = max_boxes * (math.ceil(within_box_proportion * items_per_box))
        # Check if within box proportion is high enough and/or interval is
        # low enough to achieve sample size
        if max_items >= n_items_to_inspect:
            inspect_per_box = math.ceil(within_box_proportion * items_per_box)
            n_boxes_to_inspect = math.ceil(n_items_to_inspect / inspect_per_box)
        # If not, divide sample size across max boxes to get number of
        # items to inspect per box.
        else:
            print(
                "Warning: Within box proportion is too low and/or interval is too "
                "high to achieve sample size. Automatically increasing within box "
                "proportion to achieve sample size."
            )
            inspect_per_box = math.ceil(n_items_to_inspect / max_boxes)
            # If not enough boxes to achieve sample size, inspect all items
            # and increase n_boxes_to_inspect as needed.
            inspect_per_box = min(inspect_per_box, items_per_box)
            n_boxes_to_inspect = math.ceil(n_items_to_inspect / inspect_per_box)
    else:
        raise RuntimeError(f"Unknown cluster selection method: {cluster_selection}")

    # Allow user specified box minimum override calculations
    n_boxes_to_inspect = max(min_boxes, n_boxes_to_inspect)
    assert num_boxes >= n_boxes_to_inspect

    return n_boxes_to_inspect, inspect_per_box


def compute_max_inspectable_items(num_items, items_per_box, within_box_proportion):
    """Compute maximum number of items that can be inspected in a consignment based
    on within box proportion. If within box proportion is less than 1 (partial box
    inspections), then maximum number of items that can be inspected will be
    less than the total number of items in the consignment.

    :param num_items: total number of items in consignment
    :param items_per_box: number of items in each box
    :param within_box_proportion: proportion of items to be inspected per box
    """
    inspect_per_box = math.ceil(within_box_proportion * items_per_box)
    num_full_boxes = math.floor(num_items / items_per_box)
    full_box_inspectable_items = num_full_boxes * inspect_per_box
    remainder_box = num_items % items_per_box
    # Assume that num of items to inspect is based on num of items
    # in full box. Same inspect_per_box will be applied to
    # full and partial boxes.
    remainder_box_inspectable_items = min(remainder_box, inspect_per_box)
    max_items = full_box_inspectable_items + remainder_box_inspectable_items
    return max_items


def select_random_indexes(unit, consignment, n_units_to_inspect):
    """Select units (indexes) from consignment based on sample size and
    random selection strategy.

    :param unit: Unit to be used for inspection (box or item)
    :param consignment: Consignment to be inspected
    :param n_units_to_inspect: Number of units to inspect defined in sample functions.
    """
    if unit in ["item", "items"]:
        indexes_to_inspect = random.sample(
            list(range(consignment.num_items)), n_units_to_inspect
        )
    elif unit in ["box", "boxes"]:
        indexes_to_inspect = random.sample(
            list(range(consignment.num_boxes)), n_units_to_inspect
        )
    else:
        raise RuntimeError(f"Unknown unit: {unit}")
    indexes_to_inspect.sort()
    return indexes_to_inspect


def select_random_indexes_rbs(
        unit,
        consignment,
        n_units_to_inspect,
        rng: Generator,
):
    """Select random unit indexes for RBS-based sampling.

    For sample-unit based RBS, the function samples within risk-unit pools
    (if available) or per inspection unit (legacy fallback).

    Args:
        unit: Sampling unit, expected to be a sample-unit alias.
        consignment: Consignment to be inspected.
        n_units_to_inspect: Mapping from risk-unit (or inspection) IDs to
            number of units to inspect.
        rng: Random number generator.

    Returns:
        Tuple ``(indexes_to_inspect, inspection_units_to_inspect)`` where:
        * ``indexes_to_inspect`` is the list of global sample-unit indexes.
        * ``inspection_units_to_inspect`` maps inspection-unit index to a
          list of local sample-unit indexes.

    Raises:
        RuntimeError: If an unsupported unit type is used with RBS strategy.
    """
    indexes_to_inspect = []
    if _is_sample_unit_unit(unit):
        inspection_unit_counter = 0
        inspection_units_to_inspect = {
            idx: [] for idx in range(consignment.num_inspection_units)
        }

        # Build lookup from sample_unit_id to local index inside each inspection unit.
        sample_unit_local_index = {}
        for iu_idx, inspection_unit in enumerate(consignment.inspection_units):
            for local_idx, sample_unit_obj in enumerate(inspection_unit.included_unit_objects):
                sample_unit_id = getattr(sample_unit_obj, "id", None)
                if sample_unit_id is not None:
                    sample_unit_local_index[sample_unit_id] = (iu_idx, local_idx)

        risk_pool_map = getattr(consignment, "risk_unit_to_sample_units", {}) or {}
        if risk_pool_map:
            selected_sample_unit_ids = []
            for risk_unit_id, requested in n_units_to_inspect.items():
                sample_pool = list(risk_pool_map.get(risk_unit_id, []))
                if not sample_pool:
                    continue
                requested = max(0, min(requested, len(sample_pool)))
                if requested == 0:
                    continue
                selected = rng.choice(sample_pool, size=requested, replace=False)
                selected_sample_unit_ids.extend(selected)

            # Deduplicate to avoid double-inspection if sample units appear in multiple risk groups.
            for sample_unit_id in sorted(set(selected_sample_unit_ids)):
                indexes_to_inspect.append(sample_unit_id)
                iu_and_local = sample_unit_local_index.get(sample_unit_id)
                if iu_and_local is not None:
                    iu_idx, local_idx = iu_and_local
                    inspection_units_to_inspect[iu_idx].append(local_idx)
        else:
            # Legacy fallback: keyed per inspection unit.
            current_idx = 0
            for inspection_unit in consignment.inspection_units:
                population = len(inspection_unit.included_unit_objects)
                requested = n_units_to_inspect.get(inspection_unit_counter, 0)
                requested = max(0, min(requested, population))
                indexes_to_inspect_temp = list(rng.choice(list(range(population)), size=requested, replace=False))
                inspection_units_to_inspect[inspection_unit_counter] = indexes_to_inspect_temp
                indexes_to_inspect_temp = [x + current_idx for x in indexes_to_inspect_temp]
                current_idx += population
                indexes_to_inspect = indexes_to_inspect + indexes_to_inspect_temp
                inspection_unit_counter += 1
    else:
        raise RuntimeError(f"Inspection process unit specified in config is: {unit}.  "
                           f"For Sampling Strategy = RBS, only supports that parameter being = sampling_units")
    indexes_to_inspect.sort()
    return indexes_to_inspect, inspection_units_to_inspect


def select_cluster_indexes(config, consignment, n_units_to_inspect):
    """Select units (indexes) from consignment based on sample size and
    cluster selection strategy.

    :param config: Configuration to be used
    :param consignment: Consignment to be inspected
    :param n_units_to_inspect: Number of units to inspect defined in sample functions.
    """
    unit = config["inspection"]["unit"]
    cluster_selection = config["inspection"]["cluster"]["cluster_selection"]

    if unit in ["item", "items"]:
        if cluster_selection == "random":
            n_boxes_to_inspect = (
                compute_n_clusters_to_inspect(config, consignment, n_units_to_inspect)
            )[0]
            # Choose box indexes randomly
            indexes_to_inspect = random.sample(
                list(range(consignment.num_boxes)), n_boxes_to_inspect
            )
        elif cluster_selection == "interval":
            interval = config["inspection"]["cluster"]["interval"]
            n_boxes_to_inspect = (
                compute_n_clusters_to_inspect(config, consignment, n_units_to_inspect)
            )[0]
            max_boxes = max(1, round(consignment.num_boxes / interval))
            # Check to see if interval is small enough to achieve n_boxes_to_inspect
            # If not, decrease interval.
            if n_boxes_to_inspect > max_boxes:
                interval = round(consignment.num_boxes / n_boxes_to_inspect)
            # Create list of indexes incremented by interval size
            indexes_to_inspect = []
            index = 0
            for unused_i in range(n_boxes_to_inspect):
                indexes_to_inspect.append(index)
                index += interval
        else:
            raise RuntimeError(f"Unknown cluster selection method: {cluster_selection}")
    elif unit in ["box", "boxes"]:
        raise RuntimeError(
            "Cannot use cluster selection strategy with box sampling unit"
        )
    else:
        raise RuntimeError(f"Unknown unit: {unit}")
    indexes_to_inspect.sort()
    return indexes_to_inspect


def select_units_to_inspect(
        config,
        consignment,
        n_units_to_inspect,
        rng: Generator = None,
):
    """Select units to inspect based on sampling and selection strategies.

    For RBS-based strategies, the function may return both sample-unit
    indexes and an inspection-unit–to–sample-unit mapping. For non-RBS
    strategies, it returns a list of indexes only.

    Args:
        config: Configuration dictionary.
        consignment: Consignment to be inspected.
        n_units_to_inspect: Number of units to inspect (or mapping for RBS).
        rng: Optional random number generator.

    Returns:
        Either:
        * list of unit indexes (non-RBS), or
        * tuple ``(indexes_to_inspect, inspection_units_to_inspect)`` for RBS.

    Raises:
        RuntimeError: If an unknown selection strategy is specified.
    """
    unit = config["inspection"]["unit"]
    selection_strategy = config["inspection"]["selection_strategy"]
    sample_strategy = config["inspection"]["sample_strategy"]

    if sample_strategy == "rbs":
        if selection_strategy == "random":
            return select_random_indexes_rbs(unit, consignment, n_units_to_inspect, rng=rng)
        elif selection_strategy == "cluster":
            return select_cluster_indexes(config, consignment, n_units_to_inspect)
        elif selection_strategy == "convenience":
            return _select_convenience_indexes(unit, consignment, n_units_to_inspect)
        else:
            raise RuntimeError(f"Unknown selection strategy: {selection_strategy}")
    else:
        if selection_strategy == "convenience":
            indexes_to_inspect = list(range(n_units_to_inspect))
        elif selection_strategy == "random":
            indexes_to_inspect = select_random_indexes(
                unit, consignment, n_units_to_inspect
            )
        elif selection_strategy == "cluster":
            # Compute number of boxes needed to achieve sample size
            # and select box indexes.
            indexes_to_inspect = select_cluster_indexes(
                config, consignment, n_units_to_inspect
            )
        else:
            raise RuntimeError(f"Unknown selection strategy: {selection_strategy}")
        return indexes_to_inspect


def inspect_sample_unit(sample_unit, effectiveness):
    """Test whether a sample unit is contaminated, given inspector effectiveness.

    Args:
        sample_unit: Sample-unit contamination indicator or count.
        effectiveness: Probability that the inspector will detect contamination
            when present (0–1).

    Returns:
        True if contamination is detected in this sample unit, False otherwise.
    """
    if sample_unit == 0:
        return False
    return random.random() < effectiveness

def inspect_item(item, effectiveness):
    """Tests whether item is contaminated considering effectiveness"""
    return item and random.random() < effectiveness

def inspect(
        config,
        consignment,
        n_units_to_inspect,
        detailed,
        rng: Generator = None,
):
    """Inspect selected units according to configuration and strategies.

    The function inspects units until detection and until completion, tracking
    counts of opened inspection units, inspected sample units, inspected plant
    units, and contaminated sample units.

    Args:
        config: Configuration dictionary.
        consignment: Consignment to be inspected.
        n_units_to_inspect: Number of units to inspect (or mapping, for RBS).
        detailed: If True, track detailed indices of inspected sample units.
        rng: Optional random number generator.

    Returns:
        A SimpleNamespace with various inspection statistics, including:
        * inspected_sample_unit_indexes
        * inspection_units_opened_completion / detection
        * sample_units_inspected_completion / detection
        * plant_units_inspected_completion / detection
        * contaminated_sample_units_completion / detection
        * number_sample_units_missed, number_units_missed
        * consignment_checked_ok (True if no contamination found).
    """
    # Disabling warnings, possible future TODO is splitting this function.
    # pylint: disable=too-many-locals,too-many-statements
    # pylint: disable=too-many-branches,too-many-nested-blocks

    if (config.get("inspection_process", None) is not None) and (config['inspection_process'] == "RBS-PIS"):
        # Detection is inspection-outcome state, so reset for each inspect() call.
        for inspection_unit in consignment.inspection_units:
            if hasattr(inspection_unit, "reset_detection"):
                inspection_unit.reset_detection()
            elif hasattr(inspection_unit, "is_detected"):
                inspection_unit.is_detected = False

        unit = config["inspection"]["unit"]
        selection_strategy = config["inspection"]["selection_strategy"]
        sample_strategy = config["inspection"]["sample_strategy"]
        sample_units_per_inspection_unit = consignment.sample_units_per_inspection_unit
        sample_unit_to_inspection = getattr(consignment, "sample_unit_to_inspection_unit", {}) or {}
        sample_unit_local_index = {}
        running_sample_index = 0
        for iu_idx, inspection_unit in enumerate(consignment.inspection_units):
            su_objects = getattr(inspection_unit, "included_unit_objects", [])
            if su_objects:
                for local_idx, sample_unit_obj in enumerate(su_objects):
                    su_id = getattr(sample_unit_obj, "id", None)
                    if su_id is not None:
                        sample_unit_local_index[su_id] = local_idx
                    else:
                        sample_unit_local_index[running_sample_index] = local_idx
                        running_sample_index += 1

        if sample_strategy == "rbs":
            indexes_to_inspect, inspection_units_to_inspect = select_units_to_inspect(
                config, consignment, n_units_to_inspect, rng=rng
            )
        else:
            indexes_to_inspect = select_units_to_inspect(
                config, consignment, n_units_to_inspect
            )

        effectiveness = get_validated_effectiveness(config)

        # Inspect selected inspection_units, count opened inspection_units, inspected sample_units, and contaminated
        # sample_units to detection and completion
        ret = types.SimpleNamespace(
            inspected_sample_unit_indexes=[],
            inspected_box_indexes=[],
            inspected_box_result=[],
            inspection_units_opened_completion=0,
            inspection_units_opened_detection=0,
            sample_units_inspected_completion=0,
            sample_units_inspected_detection=0,
            plant_units_inspected_completion=0,
            plant_units_inspected_detection=0,
            contaminated_sample_units_completion=0,
            contaminated_sample_units_detection=0,
            number_sample_units_missed=0,
            number_units_missed=0
        )

        if sample_strategy == "rbs":

            if unit in ["sample_unit", "sample_units", "item", "items"]:
                detected = False
                if selection_strategy == "cluster":
                    raise RuntimeError(f"Selection strategy = '{selection_strategy}' is not supported for"
                                       f" sampling_strategy = {sample_strategy}")
                else:
                    # All other sample_unit selection strategies inspected the same way
                    # Empty lists to hold opened inspection_units indexes, will be duplicates bc inspection_unit index
                    # computed per inspected sample_unit
                    inspection_units_opened_completion = []
                    inspection_units_opened_detection = []
                    # Loop through sample_units in sorted index list (sorted in index functions)
                    # Inspection progresses through indexes in ascending order
                    for sample_unit_index in indexes_to_inspect:
                        if detailed:
                            ret.inspected_sample_unit_indexes.append(sample_unit_index)
                        ret.sample_units_inspected_completion += 1

                        # Count sample units inspected (all plants in this sample unit)
                        iu_idx = sample_unit_to_inspection.get(
                            sample_unit_index,
                            math.floor(sample_unit_index / sample_units_per_inspection_unit),
                        )
                        su_local_idx = sample_unit_local_index.get(
                            sample_unit_index,
                            sample_unit_index % sample_units_per_inspection_unit,
                        )
                        try:
                            su_obj = consignment.inspection_units[iu_idx].included_unit_objects[su_local_idx]
                            ret.plant_units_inspected_completion += len(su_obj.plants)
                        except Exception:
                            pass
                        # Compute inspection_unit index number
                        inspection_units_opened_completion.append(
                            iu_idx)
                        if not detected:
                            ret.sample_units_inspected_detection += 1
                            try:
                                su_obj = consignment.inspection_units[iu_idx].included_unit_objects[su_local_idx]
                                ret.plant_units_inspected_detection += len(su_obj.plants)
                            except Exception:
                                pass
                            # Compute inspection_unit index number
                            inspection_units_opened_detection.append(
                                iu_idx
                            )

                        if inspect_sample_unit(consignment.sample_units[sample_unit_index], effectiveness):
                            consignment.inspection_units[iu_idx].is_detected = True
                            # Count every contaminated sample_unit in sample
                            ret.contaminated_sample_units_completion += 1
                            if not detected:
                                ret.contaminated_sample_units_detection += 1
                                detected = True
                        # Should be only 1 contaminated sample_unit if to detection
                        if detected:
                            assert ret.contaminated_sample_units_detection == 1
                    # Number of inspection_units opened is number of unique inspection_units indexes in inspection_units
                    # opened lists
                    ret.inspection_units_opened_completion = len(set(inspection_units_opened_completion))
                    ret.inspection_units_opened_detection = len(set(inspection_units_opened_detection))

                    inspection_unit_counter = 0
                    for inspect_unit in consignment.inspection_units:
                        contaminant_found = False
                        inspection_unit_contaminated = False
                        sample_unit_counter = 0
                        total_contaminated_sample_units = 0
                        total_contaminated_units = 0
                        for samp_unit in inspect_unit.included_unit_objects:
                            if sum(samp_unit.plants) > 0:
                                inspection_unit_contaminated = True
                                total_contaminated_sample_units += 1
                                total_contaminated_units += sum(samp_unit.plants)
                                if sample_unit_counter in inspection_units_to_inspect[inspection_unit_counter]:
                                    contaminant_found = True
                            sample_unit_counter += 1
                        if inspection_unit_contaminated and not contaminant_found:
                            ret.number_sample_units_missed += total_contaminated_sample_units
                            ret.number_units_missed += total_contaminated_units
                        inspection_unit_counter += 1

            elif unit in ["inspection_unit", "inspection_units", "box", "boxes"]:
                raise RuntimeError(f"Selection unit = '{unit}' within the inspect method of the"
                                   f" inspections.py module is not supported for"
                                   f" sampling_strategy = {sample_strategy}")
        else:
            if unit in ["sample_unit", "sample_units", "item", "items"]:
                detected = False
                if selection_strategy == "cluster":
                    # Compute num sample_units to inspect per inspection_unit to achieve sample size
                    # based on within inspection_unit proportion.
                    inspect_per_inspection_unit = (
                        compute_n_clusters_to_inspect(config, consignment, n_units_to_inspect)
                    )[1]
                    ret.inspection_units_opened_completion = len(indexes_to_inspect)
                    sample_units_inspected = 0
                    # Loop through selected inspection_unit indexes (random or interval selection)
                    for inspection_unit_index in indexes_to_inspect:
                        if not detected:
                            ret.inspection_units_opened_detection += 1
                        # Number of sample_units to inspect is based on either config within inspection_unit
                        # proportion or required number of sample_units to inspect per inspection_unit
                        # to achieve sample size.
                        sample_remainder = n_units_to_inspect - sample_units_inspected
                        # If sample_remainder is less than inspect_per_inspection_unit, set inspect_per_inspection_unit
                        # to sample_remainder to avoid inspecting more sample_units than computed
                        # sample size.
                        if sample_remainder < inspect_per_inspection_unit:
                            inspect_per_inspection_unit = sample_remainder
                        # In each inspection_unit, loop through first n sample_units (n = inspect_per_inspection_unit)
                        for sample_unit_in_inspection_unit_index, sample_unit in enumerate(
                                (consignment.inspection_units[inspection_unit_index]).included_units[
                                    0:inspect_per_inspection_unit]
                        ):
                            if detailed:
                                sample_unit_index = consignment.sample_unit_in_inspection_unit_to_sample_unit_index(
                                    inspection_unit_index, sample_unit_in_inspection_unit_index
                                )
                                ret.inspected_sample_unit_indexes.append(sample_unit_index)
                            ret.sample_units_inspected_completion += 1
                            if not detected:
                                ret.sample_units_inspected_detection += 1
                            if inspect_sample_unit(sample_unit, effectiveness):
                                consignment.inspection_units[inspection_unit_index].is_detected = True
                                # Count all contaminated sample_units in sample, regardless of
                                # detected variable
                                ret.contaminated_sample_units_completion += 1
                                if not detected:
                                    # Count contaminated sample_units in inspection_unit if not yet detected
                                    ret.contaminated_sample_units_detection += 1
                        if ret.contaminated_sample_units_detection > 0:
                            # Update detected variable if contaminated sample_units found in inspection_unit
                            detected = True
                        sample_units_inspected += inspect_per_inspection_unit
                    # assert (
                    #     ret.sample_units_inspected_completion == n_units_to_inspect
                    # ), """Check if number of sample_units is evenly divisible by sample_units per inspection_unit.
                    # Partial inspection_units not supported when using cluster selection."""
                else:  # All other sample_unit selection strategies inspected the same way
                    # Empty lists to hold opened inspection_units indexes, will be duplicates bc inspection_unit index
                    # computed per inspected sample_unit
                    inspection_units_opened_completion = []
                    inspection_units_opened_detection = []
                    # Loop through sample_units in sorted index list (sorted in index functions)
                    # Inspection progresses through indexes in ascending order
                    for sample_unit_index in indexes_to_inspect:
                        if detailed:
                            ret.inspected_sample_unit_indexes.append(sample_unit_index)
                        ret.sample_units_inspected_completion += 1
                        # Compute inspection_unit index number
                        iu_idx = sample_unit_to_inspection.get(
                            sample_unit_index,
                            math.floor(sample_unit_index / sample_units_per_inspection_unit),
                        )
                        inspection_units_opened_completion.append(
                            iu_idx)
                        if not detected:
                            ret.sample_units_inspected_detection += 1
                            # Compute inspection_unit index number
                            inspection_units_opened_detection.append(
                                iu_idx
                            )
                        if inspect_sample_unit(consignment.sample_units[sample_unit_index], effectiveness):
                            consignment.inspection_units[iu_idx].is_detected = True
                            # Count every contaminated sample_unit in sample
                            ret.contaminated_sample_units_completion += 1
                            if not detected:
                                ret.contaminated_sample_units_detection += 1
                                detected = True
                        # Should be only 1 contaminated sample_unit if to detection
                        if detected:
                            assert ret.contaminated_sample_units_detection == 1
                    # Number of inspection_units opened is number of unique inspection_units indexes in inspection_units
                    # opened lists
                    ret.inspection_units_opened_completion = len(set(inspection_units_opened_completion))
                    ret.inspection_units_opened_detection = len(set(inspection_units_opened_detection))
            elif unit in ["inspection_unit", "inspection_units", "box", "boxes"]:
                ret.inspected_box_indexes = indexes_to_inspect
                # Partial inspection_unit inspections allowed to reduce number of sample_units inspected if desired
                # Handle backward compatibility for within inspection unit proportion
                within_inspection_unit_proportion = config["inspection"].get("within_inspection_unit_proportion",
                                                                             config["inspection"].get(
                                                                                 "within_box_proportion", 1.0))
                inspect_per_inspection_unit = int(
                    math.ceil(within_inspection_unit_proportion * sample_units_per_inspection_unit))
                detected = False
                ret.inspection_units_opened_completion = n_units_to_inspect
                ret.sample_units_inspected_completion = n_units_to_inspect * inspect_per_inspection_unit
                for inspection_unit_index in indexes_to_inspect:
                    if not detected:
                        ret.inspection_units_opened_detection += 1
                    # In each inspection_unit, loop through first n sample_units (n = inspect_per_inspection_unit)
                    for sample_unit_in_inspection_unit_index, sample_unit in enumerate(
                            (consignment.inspection_units[inspection_unit_index]).included_units[
                                0:inspect_per_inspection_unit]
                    ):
                        if detailed:
                            sample_unit_index = consignment.sample_unit_in_inspection_unit_to_sample_unit_index(
                                inspection_unit_index, sample_unit_in_inspection_unit_index
                            )
                            ret.inspected_sample_unit_indexes.append(sample_unit_index)
                        if not detected:
                            ret.sample_units_inspected_detection += 1
                        if inspect_sample_unit(sample_unit, effectiveness):
                            consignment.inspection_units[inspection_unit_index].is_detected = True
                            # Count every contaminated sample_unit in sample
                            ret.contaminated_sample_units_completion += 1
                            # If first contaminated inspection_unit inspected,
                            # count contaminated sample_units in inspection_unit
                            if not detected:
                                ret.contaminated_sample_units_detection += 1
                    # If inspection_unit contained contaminated sample_units, changed detected variable
                    if ret.contaminated_sample_units_detection > 0:
                        detected = True
                        ret.inspected_box_result.append(1)
                    else:
                        ret.inspected_box_result.append(0)

        ret.consignment_checked_ok = ret.contaminated_sample_units_completion == 0
        return ret
    else:
        # Disabling warnings, possible future TODO is splitting this function.
        # pylint: disable=too-many-locals,too-many-statements
        # pylint: disable=too-many-branches,too-many-nested-blocks

        unit = config["inspection"]["unit"]
        selection_strategy = config["inspection"]["selection_strategy"]
        items_per_box = consignment.items_per_box

        indexes_to_inspect = select_units_to_inspect(
            config, consignment, n_units_to_inspect
        )

        effectiveness = get_validated_effectiveness(config)

        # Inspect selected boxes, count opened boxes, inspected items, and contaminated
        # items to detection and completion
        ret = types.SimpleNamespace(
            inspected_item_indexes=[],
            boxes_opened_completion=0,
            boxes_opened_detection=0,
            items_inspected_completion=0,
            items_inspected_detection=0,
            contaminated_items_completion=0,
            contaminated_items_detection=0,
        )

        if unit in ["item", "items"]:
            detected = False
            if selection_strategy == "cluster":
                # Compute num items to inspect per box to achieve sample size
                # based on within box proportion.
                inspect_per_box = (
                    compute_n_clusters_to_inspect(config, consignment, n_units_to_inspect)
                )[1]
                ret.boxes_opened_completion = len(indexes_to_inspect)
                items_inspected = 0
                # Loop through selected box indexes (random or interval selection)
                for box_index in indexes_to_inspect:
                    if not detected:
                        ret.boxes_opened_detection += 1
                    sample_remainder = n_units_to_inspect - items_inspected
                    # If sample_remainder is less than inspect_per_box, set inspect_per_box
                    # to sample_remainder to avoid inspecting more items than computed
                    # sample size.
                    if sample_remainder < inspect_per_box:
                        inspect_per_box = sample_remainder
                    # In each box, loop through first n items (n = inspect_per_box)
                    for item_in_box_index, item in enumerate(
                            (consignment.boxes[box_index]).items[0:inspect_per_box]
                    ):
                        if detailed:
                            item_index = consignment.item_in_box_to_item_index(
                                box_index, item_in_box_index
                            )
                            ret.inspected_item_indexes.append(item_index)
                        ret.items_inspected_completion += 1
                        if not detected:
                            ret.items_inspected_detection += 1
                        if inspect_item(item, effectiveness):
                            # Count all contaminated items in sample, regardless of
                            # detected variable
                            ret.contaminated_items_completion += 1
                            if not detected:
                                # Count contaminated items in box if not yet detected
                                ret.contaminated_items_detection += 1
                    if ret.contaminated_items_detection > 0:
                        # Update detected variable if contaminated items found in box
                        detected = True
                    items_inspected += inspect_per_box
                # assert (
                #     ret.items_inspected_completion == n_units_to_inspect
                # ), """Check if number of items is evenly divisible by items per box.
                # Partial boxes not supported when using cluster selection."""
            else:  # All other item selection strategies inspected the same way
                # Empty lists to hold opened boxes indexes, will be duplicates bc box index
                # computed per inspected item
                boxes_opened_completion = []
                boxes_opened_detection = []
                # Loop through items in sorted index list (sorted in index functions)
                # Inspection progresses through indexes in ascending order
                for item_index in indexes_to_inspect:
                    if detailed:
                        ret.inspected_item_indexes.append(item_index)
                    ret.items_inspected_completion += 1
                    # Compute box index number
                    boxes_opened_completion.append(math.floor(item_index / items_per_box))
                    if not detected:
                        ret.items_inspected_detection += 1
                        # Compute box index number
                        boxes_opened_detection.append(
                            math.floor(item_index / items_per_box)
                        )
                    if inspect_item(consignment.items[item_index], effectiveness):
                        # Count every contaminated item in sample
                        ret.contaminated_items_completion += 1
                        if not detected:
                            ret.contaminated_items_detection += 1
                            detected = True
                    # Should be only 1 contaminated item if to detection
                    if detected:
                        assert ret.contaminated_items_detection == 1
                # Number of boxes opened is number of unique boxes indexes in boxes
                # opened lists
                ret.boxes_opened_completion = len(set(boxes_opened_completion))
                ret.boxes_opened_detection = len(set(boxes_opened_detection))
        elif unit in ["box", "boxes"]:
            # Partial box inspections allowed to reduce number of items inspected if desired
            within_box_proportion = config["inspection"]["within_box_proportion"]
            inspect_per_box = int(math.ceil(within_box_proportion * items_per_box))
            detected = False
            ret.boxes_opened_completion = n_units_to_inspect
            ret.items_inspected_completion = n_units_to_inspect * inspect_per_box
            for box_index in indexes_to_inspect:
                if not detected:
                    ret.boxes_opened_detection += 1
                # In each box, loop through first n items (n = inspect_per_box)
                for item_in_box_index, item in enumerate(
                        (consignment.boxes[box_index]).items[0:inspect_per_box]
                ):
                    if detailed:
                        item_index = consignment.item_in_box_to_item_index(
                            box_index, item_in_box_index
                        )
                        ret.inspected_item_indexes.append(item_index)
                    if not detected:
                        ret.items_inspected_detection += 1
                    if inspect_item(item, effectiveness):
                        # Count every contaminated item in sample
                        ret.contaminated_items_completion += 1
                        # If first contaminated box inspected,
                        # count contaminated items in box
                        if not detected:
                            ret.contaminated_items_detection += 1
                # If box contained contaminated items, changed detected variable
                if ret.contaminated_items_detection > 0:
                    detected = True

        ret.consignment_checked_ok = ret.contaminated_items_completion == 0
        return ret


def get_sample_function(
        config,
        rng: Generator = None,
):
    """Return a function that computes sample size for a consignment.

    The returned function implements the sampling strategy specified in the
    configuration (proportion, hypergeometric, fixed_n, all, or rbs).

    Args:
        config: Configuration dictionary, expected to contain an
            ``inspection.sample_strategy`` entry.
        rng: Optional random number generator, used by some strategies.

    Returns:
        A callable ``sample(consignment)`` returning a sample size or mapping.

    Raises:
        RuntimeError: If the sample strategy is unknown.
    """
    sample_strategy = config["inspection"]["sample_strategy"]
    if sample_strategy == "proportion":

        def sample(consignment):
            return sample_proportion(config=config, consignment=consignment)

    elif sample_strategy == "hypergeometric":

        def sample(consignment):
            return sample_hypergeometric(config=config, consignment=consignment)

    elif sample_strategy == "fixed_n":

        def sample(consignment):
            return sample_n(config=config, consignment=consignment)

    elif sample_strategy == "all":

        def sample(consignment):
            return sample_all(config=config, consignment=consignment)

    elif sample_strategy == "rbs":

        def sample(consignment):
            return sample_rbs(
                config=config,
                consignment=consignment,
                rng=rng
            )

    else:
        raise RuntimeError(f"Unknown sample strategy: {sample_strategy}")
    return sample


def is_consignment_contaminated(consignment):
    """Return True if at least one box contains contaminants"""
    for box in consignment.boxes:
        if box:
            return True
    return False


def consignment_contamination_rate(consignment):
    """Return the (true) contamination rate of a consignment.

    Contamination rate is defined here as the number of contaminated
    sample units divided by the total number of sample units.

    Args:
        consignment: Consignment to evaluate.

    Returns:
        Contamination rate as a float.
    """
    if consignment.sample_units is not None:
        count = np.count_nonzero(consignment.plants)
        return count / consignment.num_plants
    elif consignment.items is not None:
        count = np.count_nonzero(consignment.items)
        return count / consignment.num_items
    else:
        return 0.0


def get_detection_and_confidence(
        consignment,
        compliance_table_dict,
        default_detection=0.15,
        default_confidence=0.95,
        print_compliance_levels: bool = False,
):
    """Fetch detection and confidence levels for risk units.

    Uses RiskUnitConfig to extract risk-unit attributes and identifies the
    matching detection and confidence levels from a compliance table. If
    values are missing or no match is found, defaults are used.

    Args:
        consignment: Consignment whose risk units (or inspection units) are
            evaluated.
        compliance_table_dict: Mapping from tuples of RBS variables to
            (detection_level, confidence_level).
        default_detection: Default detection level if no match is found.
        default_confidence: Default confidence level if no match is found.
        print_compliance_levels: If True, print per-risk-unit key and levels.

    Returns:
        Dictionary mapping risk-unit IDs (or fallback indices) to
        (detection_level, confidence_level) tuples.
    """
    risk_unit_config = RiskUnitConfig()
    rbs_variables = compliance_table_dict['rbs_variables']
    detect_confidence_levels = {}
    risk_units = consignment.risk_units if consignment.risk_units else []
    if not risk_units:
        risk_units = consignment.inspection_units

    if len(rbs_variables) == 0:
        for risk_unit_idx, risk_unit in enumerate(risk_units):
            risk_unit_id = getattr(risk_unit, "id", risk_unit_idx)
            detect_confidence_levels[risk_unit_id] = (default_detection, default_confidence)
        return detect_confidence_levels

    for risk_unit_idx, risk_unit in enumerate(risk_units):
        risk_unit_id = getattr(risk_unit, "id", risk_unit_idx)

        # Extract only the RBS variables we need
        values = {}
        for var in rbs_variables:
            # Get value using flexible lookup
            value = _get_risk_unit_attribute(risk_unit, var, risk_unit_config)
            values[var] = value

        for key, val in values.items():
            if isinstance(val, bool):
                values[key] = "TRUE" if val else "FALSE"

        # Check for missing values
        missing = [var for var, val in values.items() if val is None]
        if missing:
            key = None
            result = (default_detection, default_confidence)
            if print_compliance_levels:
                print(
                    f"Warning: Risk unit {risk_unit_id} missing values for: {missing}. "
                    f"Using defaults: detection={default_detection}, confidence={default_confidence}"
                )
        else:
            key = tuple(values[attr] for attr in rbs_variables)
            result = compliance_table_dict.get(key, (default_detection, default_confidence))

        if print_compliance_levels:
            key_str = key if key is not None else "<missing>"
            print(
                f"Risk unit {risk_unit_id}: key={key_str} -> "
                f"detection={result[0]}, confidence={result[1]}"
            )

        detect_confidence_levels[risk_unit_id] = result

    return detect_confidence_levels


def _get_risk_unit_attribute(
        risk_unit,
        attribute_name: str,
        risk_unit_config: RiskUnitConfig
) -> Any:
    """Get a risk-unit attribute, trying multiple name variations.

    The function tries:
        * the canonical attribute_name,
        * a mapped CSV column name from RiskUnitConfig,
        * lowercase/uppercase and space/underscore variants.

    Args:
        risk_unit: Risk-unit object whose attributes are queried.
        attribute_name: Canonical attribute name (e.g., ``"material_type"``).
        risk_unit_config: RiskUnitConfig instance providing attribute mapping.

    Returns:
        The attribute value or None if not found.
    """
    # List of possible attribute names to try, in order of preference
    names_to_try = [
        attribute_name,  # Exact match (e.g., "material_type")
    ]

    # Add CSV column name if mapped
    if attribute_name in risk_unit_config.attribute_mapping:
        csv_name = risk_unit_config.attribute_mapping[attribute_name]
        names_to_try.extend([
            csv_name,
            csv_name.lower(),
        ])

    # Add common variations
    names_to_try.extend([
        attribute_name.lower(),
        attribute_name.upper(),
        attribute_name.replace('_', ' '),
        attribute_name.replace(' ', '_'),
    ])

    # Try each possible name
    for name in names_to_try:
        if hasattr(risk_unit, name):
            value = getattr(risk_unit, name, None)
            if value is not None:
                return value

    return None


def count_contaminated_inspection_units(consignment):
    """Return number of inspection units containing contaminants."""
    count = 0
    for inspection_unit in consignment.inspection_units:
        if inspection_unit:
            count += 1
    return count


def count_contaminated_sample_units(consignment):
    """Return number of contaminated sample units."""
    count = np.count_nonzero(consignment.sample_units)
    return count


# Backward compatibility aliases
def count_contaminated_boxes(consignment):
    """Return number of boxes containing contaminants"""
    count = 0
    for box in consignment.boxes:
        if box:
            count += 1
    return count


def count_contaminated_items(consignment):
    """Return number of contaminated items"""
    count = np.count_nonzero(consignment.items)
    return count


def _norm(s: str) -> str:
    """Normalize a string for matching by lowercasing and stripping non-alphanum."""
    return re.sub(r'[^a-z0-9]+', '', s.lower())


def normalize_rbs_variables_against_consignment(
        rbs_variables,
        consignment,
):
    """Normalize RBS variable names to Consignment attributes via aliasing.

    This function maps free-form, user-provided RBS variable names to actual
    attribute names on a Consignment instance using case-insensitive and
    alias-based matching. Unmapped names are preserved.

    Args:
        rbs_variables: List of free-form RBS variable names.
        consignment: Consignment instance providing canonical attribute names.

    Returns:
        Tuple ``(updated_vars, mapping, unmapped)`` where:
        * ``updated_vars`` is the list of normalized variable names.
        * ``mapping`` maps original variable names to canonical attributes.
        * ``unmapped`` contains variable names that could not be mapped.
    """
    # 1) Canonical attribute keys from the instance (thanks to UserDict)
    canonical_attrs = set(consignment.keys())

    # 2) Auto-generate basic aliases from the canonical names
    #    (e.g., "material_type" -> "material type", "Material Type", etc.)
    auto_aliases = defaultdict(set)
    for attr in canonical_attrs:
        spaced = attr.replace('_', ' ')
        auto_aliases[attr].update({
            attr,
            spaced,
            spaced.title(),  # "Material Type"
            attr.title(),  # "Material_Type" (rare, but harmless)
        })

    # Add any pre-specified aliases (see reference.py file in slippage_model_utils)
    if 'origin' in canonical_attrs:
        auto_aliases['origin'].update(country_of_origin_names)
    if 'material_type' in canonical_attrs:
        auto_aliases['material_type'].update(pm_type_names)
    if 'port' in canonical_attrs:
        auto_aliases['port'].update(possible_pis_stations)

    # Build a lookup: normalized alias -> canonical attribute
    alias_index = {}
    for attr, names in auto_aliases.items():
        for name in names:
            alias_index[_norm(name)] = attr

    # Walk the input list, map to canonical attributes when possible
    updated_vars = []
    mapping = {}
    unmapped = []

    for original in rbs_variables:
        key = _norm(original)
        if key in alias_index:
            canonical = alias_index[key]
            mapping[original] = canonical
            updated_vars.append(canonical)
        else:
            # Heuristic fallback: try to match substrings like "origin" inside long names
            # (Keeps false positives low by requiring the canonical word to appear)
            matched = None
            for attr in canonical_attrs:
                if re.search(rf'\b{re.escape(attr.replace("_", " "))}\b', original, flags=re.I):
                    matched = attr
                    break
            if matched:
                mapping[original] = matched
                updated_vars.append(matched)
            else:
                unmapped.append(original)
                updated_vars.append(original)

    return updated_vars, mapping, unmapped


def fuzzy_match_attribute(original: str, canonical_attrs: Set[str]) -> Optional[str]:
    """Attempt fuzzy matching between a variable name and canonical attributes.

    Matching is based on case-insensitive substring and word-boundary matches.

    Args:
        original: Original variable name to match.
        canonical_attrs: Set of canonical attribute names.

    Returns:
        Matched canonical attribute name, or None if no match is found.
    """
    # Sort by length (longest first) to prefer more specific matches
    sorted_attrs = sorted(canonical_attrs, key=len, reverse=True)

    for attr in sorted_attrs:
        # Try exact word boundary match
        pattern = rf'\b{re.escape(attr.replace("_", " "))}\b'
        if re.search(pattern, original, flags=re.I):
            return attr

        # Try matching with underscores
        pattern = rf'\b{re.escape(attr)}\b'
        if re.search(pattern, original, flags=re.I):
            return attr

    return None


# Convenience function that creates a RiskUnitConfig from defaults
def normalize_rbs_variables_using_risk_unit_config(
        rbs_variables: List[str]
) -> Tuple[List[str], Dict[str, str], List[str]]:
    """Normalize RBS variable names using RiskUnitConfig and aliasing.

    This function maps free-form field names in ``rbs_variables`` to actual
    RiskUnit attributes defined in :class:`RiskUnitConfig`, using
    case-insensitive aliasing, CSV column names, and domain-specific aliases.

    Args:
        rbs_variables: List of variable names to normalize.

    Returns:
        Tuple ``(updated_vars, mapping, unmapped)`` where:
        * ``updated_vars``: normalized RBS variable names.
        * ``mapping``: mapping from original names to canonical attributes.
        * ``unmapped``: list of originals that could not be mapped.
    """
    risk_unit_config = RiskUnitConfig()
    if not rbs_variables:
        return [], {}, []

    # Get canonical attribute names from the config
    canonical_attrs = set(risk_unit_config.enabled_attributes)

    # Auto-generate basic aliases from the canonical names
    auto_aliases = defaultdict(set)
    for attr in canonical_attrs:
        spaced = attr.replace('_', ' ')
        auto_aliases[attr].update({
            attr,
            spaced,
            spaced.title(),  # "Material Type"
            spaced.upper(),  # "MATERIAL TYPE"
            spaced.lower(),  # "material type"
            attr.title(),  # "Material_Type"
            attr.upper(),  # "MATERIAL_TYPE"
        })

    # Add aliases from the attribute_mapping (CSV column names)
    for attr, csv_column in risk_unit_config.attribute_mapping.items():
        if attr in canonical_attrs:
            auto_aliases[attr].add(csv_column)
            # Also add normalized versions of CSV column name
            csv_spaced = csv_column.replace('_', ' ')
            auto_aliases[attr].update({
                csv_column,
                csv_spaced,
                csv_spaced.title(),
                csv_spaced.lower(),
                csv_spaced.upper(),
            })

    # Add domain-specific aliases (hardcoded knowledge)
    domain_aliases = get_domain_specific_aliases()
    for attr, aliases in domain_aliases.items():
        if attr in canonical_attrs:
            auto_aliases[attr].update(aliases)

    # Build a lookup: normalized alias -> canonical attribute
    alias_index = {}
    for attr, names in auto_aliases.items():
        for name in names:
            normalized = _norm(name)
            if normalized in alias_index and alias_index[normalized] != attr:
                # Collision detected - log it
                warnings.warn(
                    f"Alias collision detected: '{name}' (normalized: '{normalized}') "
                    f"maps to both '{alias_index[normalized]}' and '{attr}'. "
                    f"Using '{alias_index[normalized]}'."
                )
            else:
                alias_index[normalized] = attr

    # Walk the input list, map to canonical attributes when possible
    updated_vars = []
    mapping = {}
    unmapped = []

    for original in rbs_variables:
        if not original or not original.strip():
            warnings.warn(f"Empty or whitespace-only variable name found, skipping.")
            continue

        key = _norm(original)

        if key in alias_index:
            # Direct match found
            canonical = alias_index[key]
            mapping[original] = canonical
            updated_vars.append(canonical)
        else:
            # Heuristic fallback: try to match substrings
            matched = fuzzy_match_attribute(original, canonical_attrs)

            if matched:
                mapping[original] = matched
                updated_vars.append(matched)
            else:
                unmapped.append(original)
                updated_vars.append(original)

    # Provide informative feedback
    if mapping:
        print(f"Mapped {len(mapping)} compliance table variable(s) to RiskUnit attributes:")
        for orig, canonical in list(mapping.items())[:5]:
            print(f"  '{orig}' -> '{canonical}'")
        if len(mapping) > 5:
            print(f"  ... and {len(mapping) - 5} more")

    if unmapped:
        warnings.warn(
            f"\nCould not map {len(unmapped)} compliance table variable(s) to RiskUnit attributes.\n"
            f"Unmapped variables: {unmapped[:5]}{'...' if len(unmapped) > 5 else ''}\n"
            f"Available RiskUnit attributes: {sorted(canonical_attrs)}"
        )

    return updated_vars, mapping, unmapped
