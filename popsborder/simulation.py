# Simulation of contaminated consignments and their inspections
# Copyright (C) 2018-2021 Vaclav Petras and others (see below)

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


"""Single and multiple runs of the simulation

.. codeauthor:: Vaclav Petras <wenzeslaus gmail com>
.. codeauthor:: Kellyn P. Montgomery <kellynmontgomery gmail com>
"""

import random
import sys
import types
from collections.abc import Iterable, Mapping
from pathlib import Path

import numpy as np

from .consignments import get_consignment_generator, get_contaminant_function
from .inspections import (
    consignment_contamination_rate,
    get_inspection_needed_function,
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
)


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
    if detailed:
        item_details = []
        inspected_item_details = []

    consignment_generator = get_consignment_generator(config)
    add_contaminant = get_contaminant_function(config)
    is_inspection_needed = get_inspection_needed_function(config)
    sample = get_sample_function(config)
    tolerance_level = config["inspection"]["tolerance_level"]

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

    num_contaminated = num_consignments - success_rates.ok
    if num_contaminated:
        # avoiding float division by zero
        missing = 100 * float(success_rates.false_negative) / (num_contaminated)
        false_neg = success_rates.false_negative
        if verbose:
            print("Missing {0:.0f}% of contaminated consignments.".format(missing))
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
    )
    if detailed:
        simulation_results.details = [item_details, inspected_item_details]

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
):
    """Run the simulation function specified number of times

    See :func:`simulation` function for explanation of parameters.

    Returns averages computed from the individual simulation runs otherwise
    it relies on :func:`simulation` function to do the hard work.
    """
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
    )

    for i in range(num_simulations):
        result = simulation(
            config=config,
            num_consignments=num_consignments,
            seed=seed + i if seed is not None else None,
            output_f280_file=output_f280_file,
            verbose=verbose,
            pretty=pretty,
            detailed=detailed,
        )
        if detailed and i == 0:
            # details are from first run of simulation only
            details = result.details
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

    if detailed:
        # details are items and inspected item from first simulation run only
        # totals are an average of all simulation runs
        return details, totals
    else:
        return totals


def load_configuration_yaml_from_text(text):
    """Return configuration dictionary from YAML in a string"""
    import yaml  # pylint: disable=import-outside-toplevel

    if hasattr(yaml, "full_load"):
        return yaml.full_load(text)
    return yaml.load(text)  # pylint: disable=no-value-for-parameter


def load_configuration(filename, sheet=None, key_column=None, value_column=None):
    """Get the configuration from a JSON or YAML file

    The format is decided based on the file extension.
    It uses full_load() (FullLoader) to read YAML.

    The parameter can be a string or a path object (path-like object).

    If the *filename* contains `::`, anything after the last `::` is considered
    parameters determining where in the spreadsheet or table are the relevant
    columns. The format is multiple key-value pairs with key and value separated by
    `=`, `:`, or `: ` and individual keys separated by `,`.
    The same information can be passed directly as function parameters.
    If both are provided, function parameters take precedence.
    """
    if isinstance(filename, Iterable) and not isinstance(filename, str):
        from .scenarios import record_to_nested_dictionary

        return record_to_nested_dictionary(filename)

    filename_str = str(filename)
    if "::" in filename_str:
        filename, info = filename_str.rsplit("::", maxsplit=1)
        info = table_info_from_text(info)
    else:
        info = table_info_from_text("")
    filename = Path(filename)
    if sheet:
        info.sheet = sheet
    if key_column:
        info.key_column = key_column
    if value_column:
        info.value_column = value_column

    if str(filename).endswith(".json"):
        import json  # pylint: disable=import-outside-toplevel

        return json.load(open(filename))
    elif str(filename).endswith(".yaml") or str(filename).endswith(".yml"):
        import yaml  # pylint: disable=import-outside-toplevel

        if hasattr(yaml, "full_load"):
            return yaml.full_load(open(filename))
        return yaml.load(open(filename))  # pylint: disable=no-value-for-parameter
    elif filename.suffix.lower() in [".csv", ".xlsx", ".ods"]:
        return load_config_table(
            filename,
            sheet=info.sheet,
            key_column=info.key_column,
            value_column=info.value_column,
        )
    else:
        sys.exit("Unknown file extension (file: {})".format(filename))


def table_info_from_text(text, sheet=None, key_column=None, value_column=None):
    """Convert comma-separated list of key-value pairs to info about table

    Items are separated by comma. Key and value can be separated by
    `=` or `:` and also by `: ` and ` = ` because spaces surrounding
    key and value are removed.

    If there is no key-value pair, the whole value is used as a
    value for key_column.

    Function parameters are used as default values.

    Accepted keys are 'sheet', 'key_column', and 'value_column'.
    """
    info = types.SimpleNamespace(
        sheet=sheet, key_column=key_column, value_column=value_column
    )
    if not text:
        return info
    items = text.split(",")
    for item in items:
        key = None
        for separator in ["=", ":"]:
            if separator in item:
                key, value = item.split(separator, maxsplit=1)
                key = key.strip()
                value = value.strip()
                break
        if not key:
            info.key_column = item
        elif key in ["sheet", "key_column", "value_column"]:
            setattr(info, key, value)
        else:
            raise ValueError(f"Unknown key '{key}' in table info specification")
    return info


def load_config_table(filename, sheet=None, key_column=None, value_column=None):
    """Load a CSV file into a list of dictionaries

    Values which can be converted into int or float are converted. Cells which can be
    parsed as JSON, will be loaded into Python data structures (dicts, lists, etc.).

    A whole file is read and loaded into memory unlike with the ``csv.reader()``
    function.
    """
    # pylint: disable=import-outside-toplevel
    table = {}

    from .scenarios import record_to_nested_dictionary, text_to_value

    # Read spreadsheet formats
    if Path(filename).suffix.lower() not in [".csv", ".ods"]:
        import openpyxl
        from openpyxl.utils import column_index_from_string

        if key_column is None:
            key_column = 0
        else:
            try:
                key_column = int(key_column) - 1
            except ValueError:
                key_column = column_index_from_string(key_column) - 1
        if value_column is None:
            value_column = key_column + 1
        else:
            try:
                value_column = int(value_column) - 1
            except ValueError:
                value_column = column_index_from_string(value_column) - 1

        import warnings

        with warnings.catch_warnings():
            # We want to use validation functions in the spreadsheet,
            # but it does not matter whether they are supported by the reader here.
            warnings.filterwarnings(
                "ignore", message="Data Validation extension is not supported"
            )
            workbook = None
            try:
                workbook = openpyxl.load_workbook(filename, read_only=True)
                if sheet:
                    sheet = workbook[sheet]
                else:
                    sheet = workbook.active
                # Read rows excluding the header.
                for row in sheet.iter_rows(values_only=True):
                    key = row[key_column]
                    if key:
                        # Consider only rows with filled key to allow
                        # for empty rows for formatting purposes.
                        value = text_to_value(row[value_column])
                        table[key] = value
            finally:
                # Read-only mode requires an explicit close and
                # the workbook object is not a context manager.
                if workbook:
                    workbook.close()
            return record_to_nested_dictionary(table)

    if Path(filename).suffix.lower() == ".ods":
        import pandas

        sheet = sheet if sheet else 0
        if key_column is None:
            key_column = 0
        else:
            try:
                key_column = int(key_column) - 1
            except ValueError:
                pass
        if value_column is None:
            value_column = 1
        else:
            try:
                value_column = int(value_column) - 1
            except ValueError:
                pass
        data = pandas.read_excel(
            Path(filename),
            sheet_name=sheet,
            header=None,
            usecols=[key_column, value_column],
        )
        table = {}
        for row in data.itertuples():
            if row[1]:
                table[row[1]] = text_to_value(row[2])
        return record_to_nested_dictionary(table)

    # Read as CSV
    with open(filename) as file:
        import csv

        if key_column is None:
            key_column = 0
        else:
            key_column = int(key_column) - 1
        if value_column is None:
            value_column = key_column + 1
        else:
            value_column = int(value_column) - 1
        for row in csv.reader(file):
            key = row[key_column]
            value = text_to_value(row[value_column])
            table[key] = value

    return record_to_nested_dictionary(table)


def add_dict_config_to_table(table, value, keys=None):
    if keys is None:
        keys = []
    if isinstance(value, Mapping):
        for nested_key, nested_value in value.items():
            new_keys = keys.copy()
            new_keys.append(nested_key)
            add_dict_config_to_table(table, value=nested_value, keys=new_keys)
    else:
        table["/".join(keys)] = value


def dict_config_to_table(value):
    table = {}
    add_dict_config_to_table(table, value)
    return table


def print_table_config(config, file=None):
    for key, value in config.items():
        if isinstance(value, Iterable) and not isinstance(value, str):
            import json

            value = json.dumps(value)
        print(f"{key};{value}", file=file)
