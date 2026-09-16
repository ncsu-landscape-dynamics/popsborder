# Simulation of contaminated consignments and their inspections
# Copyright (C) 2018-2022 Vaclav Petras and others (see below)
# © 2026 The Johns Hopkins University Applied Physics Laboratory LLC

"""
==========================================================================================
Johns Hopkins University Applied Physics Laboratory (JHU/APL) Extensions and Modifications
==========================================================================================

Contributors: Gary Lin, Joseph Agor (JHU/APL)

Modifications:
    New Functions Added
    -------------------
    - load_compliance_lookup_csv():
        * Loads compliance level CSV files for RBS inspection workflows
        * Parses country/material type combinations with associated detection and confidence levels
        * Returns dictionary structure for efficient compliance level lookup during simulation

    - load_input_consignment_data():
        * Loads RBS calculator data for realistic consignment generation
        * Supports various input formats (CSV, Excel) for consignment parameter specifications
        * Integrates with synthetic data generation workflows for enhanced simulation realism
    -------------------

    Configuration Enhancements
    --------------------------
    - Enhanced configuration validation for new terminology (inspection_units vs boxes, sample_units vs items)
    - Added backward compatibility parameter mapping throughout configuration loading
    - Improved error handling and validation for RBS-specific configuration parameters
    --------------------------
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


"""Inputs, especially loading of configuration.

.. codeauthor:: Vaclav Petras <wenzeslaus gmail com>
.. codeauthor:: Gary Lin <Gary.Lin jhuapl edu>
.. codeauthor:: Joseph Agor <Joseph.Agor jhuapl edu>
"""

import copy
import json
import math
import sys
import types
from collections.abc import Iterable, Mapping
from pathlib import Path
import csv
from typing import Dict, Tuple, List, Set, Union, Optional
import warnings
import chardet
import pandas as pd


def text_to_value(arg):
    """Convert text to int, float, bool, JSON, or return as-is.

    If the argument is not a string, it is returned unchanged. For string
    inputs, the function attempts conversions in this order:

    1. Integer
    2. Float
    3. Boolean (JSON-style and common variants)
    4. JSON (via ``json.loads``)

    If conversion is not possible, the original text is returned. For an empty
    string, None is returned.

    Args:
        arg: Value to convert.

    Returns:
        Converted value (int, float, bool, list, dict, etc.) or original text.
        Returns None for an empty string.
    """
    # This is a short function with return statements only.
    # pylint: disable=too-many-return-statements
    if not isinstance(arg, str):
        return arg
    if not arg:
        return None
    try:
        return int(arg)
    except ValueError:
        try:
            return float(arg)
        except ValueError:
            # Supports JSON booleans, Python-like booleans, and all YAML booleans.
            # We do not support old YAML booleans.
            if arg in ["true", "True", "TRUE"]:
                return True
            if arg in ["false", "False", "FALSE"]:
                return False
            try:
                return json.loads(arg)
            except json.JSONDecodeError:
                # add yaml.safe_load here?
                # Return the original value.
                return arg


def update_nested_dict_by_dict(dictionary, update):
    """Recursively update a nested dictionary by another nested dictionary.

    Args:
        dictionary: Destination dictionary to update (modified in-place).
        update: Nested dictionary whose keys/values should be merged into
            ``dictionary``.

    Returns:
        The updated ``dictionary``.
    """
    for key, value in update.items():
        if isinstance(value, Mapping):
            dictionary[key] = update_nested_dict_by_dict(dictionary.get(key, {}), value)
        else:
            dictionary[key] = value
    return dictionary


def update_nested_dict_by_item(dictionary, keys, value):
    """Update nested dictionary by a nested keys–value pair.

    An item is a list of keys to navigate the nested dictionary and a value to
    place in the given position.

    When a key can be represented as an int, it is used as a list index. The
    list must already exist and be large enough, or the only index used must
    be 0.

    Floating point keys are not supported.

    Args:
        dictionary: Dictionary (possibly nested) to update.
        keys: Sequence of keys representing a path in the nested structure.
        value: Value to set at the given nested location.
    """
    if len(keys) == 1:
        key = keys[0]
        try:
            key = int(key)
        except ValueError:
            pass
        dictionary[key] = value
    else:
        if keys[0] not in dictionary:
            try:
                # Test if the next key is an integer and thus index in a list.
                int(keys[1])
                # In case it is a list, we require keys are items are filled in order.
                dictionary[keys[0]] = [None]
            except ValueError:
                dictionary[keys[0]] = {}
        update_nested_dict_by_item(dictionary[keys[0]], keys[1:], value)


def record_to_nested_dictionary(record):
    """Convert a flat dictionary with slash-separated keys into a nested dictionary.

    Keys in ``record`` are expected to be strings of the form
    ``"key/subkey/subsubkey"``. This function navigates/creates nested
    dictionaries and places the corresponding values at the appropriate level.

    Args:
        record: Dictionary with slash-separated string keys.

    Returns:
        A nested dictionary structure.

    Raises:
        ValueError: If any key is not a string.
    """
    out = {}
    for path, value in record.items():
        try:
            keys = path.split("/")
        except AttributeError as error:
            raise ValueError(
                f"Record items need to be strings, not {path} ({type(path).__name__})"
            ) from error
        update_nested_dict_by_item(out, keys, value)
    return out


def update_config(config, record):
    """Update a config dictionary using a record of slash-separated keys.

    Args:
        config: Original configuration dictionary.
        record: Dictionary with slash-separated keys that should override
            or extend the configuration.

    Returns:
        A deep-copied and updated configuration dictionary.
    """
    config = copy.deepcopy(config)
    update = record_to_nested_dictionary(record)
    update_nested_dict_by_dict(config, update)
    return config


def load_configuration_yaml_from_text(text):
    """Return configuration dictionary from YAML text.

    The function uses ``yaml.full_load`` (if available) for safe loading.

    Args:
        text: YAML string to parse.

    Returns:
        Parsed configuration dictionary.
    """
    import yaml  # pylint: disable=import-outside-toplevel

    if hasattr(yaml, "full_load"):
        return yaml.full_load(text)
    return yaml.load(text)  # pylint: disable=no-value-for-parameter


def load_one_configuration(
    filename: Union[str, Path, Iterable],
    sheet: Optional[str] = None,
    key_column: Optional[str] = None,
    value_column: Optional[str] = None,
):
    """Load configuration from a single JSON, YAML, CSV, XLSX, or ODS source.

    If ``filename`` is already an iterable of records, it is treated as such
    and converted directly into a nested dictionary.

    Otherwise, the file extension determines how the configuration is loaded:

    * ``.json`` → JSON
    * ``.yaml`` / ``.yml`` → YAML
    * ``.csv`` / ``.xlsx`` / ``.ods`` → table-based config via :func:`load_config_table`

    Additionally, ``filename`` may contain a ``"::"``-suffix specifying table
    info (sheet name, key/value columns), which is parsed by
    :func:`table_info_from_text`.

    Args:
        filename: Path to configuration file or iterable of records.
        sheet: Optional override for sheet name (table files).
        key_column: Optional override for key column (table files).
        value_column: Optional override for value column (table files).

    Returns:
        A configuration dictionary (possibly nested).

    Raises:
        SystemExit: If an unknown file extension is encountered.
    """
    # If filename is already an iterable of records, treat it as such.
    if isinstance(filename, Iterable) and not isinstance(filename, (str, Path)):
        return record_to_nested_dictionary(filename)

    filename_str = str(filename)
    if "::" in filename_str:
        filename_str, info_text = filename_str.rsplit("::", maxsplit=1)
        info = table_info_from_text(info_text)
    else:
        info = table_info_from_text("")

    path = Path(filename_str)

    if sheet:
        info.sheet = sheet
    if key_column:
        info.key_column = key_column
    if value_column:
        info.value_column = value_column

    suffix = path.suffix.lower()
    if suffix == ".json":
        with path.open() as f:
            return json.load(f)
    elif suffix in [".yaml", ".yml"]:
        import yaml  # pylint: disable=import-outside-toplevel

        with path.open() as f:
            if hasattr(yaml, "full_load"):
                return yaml.full_load(f)
            return yaml.load(f)  # pylint: disable=no-value-for-parameter
    elif suffix in [".csv", ".xlsx", ".ods"]:
        return load_config_table(
            path,
            sheet=info.sheet,
            key_column=info.key_column,
            value_column=info.value_column,
        )
    else:
        sys.exit(f"Unknown file extension (file: {path})")


def resolve_included_files(dictionary: dict, base_file_name: Optional[Union[str, Path]] = None) -> None:
    """Materialize nested configuration files referenced under ``include_file``.

    This function traverses a nested configuration dictionary and replaces
    ``{"include_file": {...}}`` entries with the content of the included files.

    Args:
        dictionary: Configuration dictionary (modified in-place).
        base_file_name: Optional base file path used to resolve relative
            included file paths.
    """
    for key, value in dictionary.items():
        if isinstance(value, dict):
            if len(value) == 1 and "include_file" in value:
                value = value["include_file"]
                nested_file = value["file_name"]
                if base_file_name:
                    parent = Path(base_file_name).parent
                    nested_file = parent / nested_file
                nested_sheet = value.get("sheet")
                nested_key_column = value.get("key_column")
                nested_value_column = value.get("value_column")
                file_format = value.get("file_format")
                if file_format == "list":
                    values = load_scenario_table(nested_file)
                    new_value = []
                    for item in values:
                        new_value.append(record_to_nested_dictionary(item))
                else:
                    new_value = load_one_configuration(
                        nested_file,
                        sheet=nested_sheet,
                        key_column=nested_key_column,
                        value_column=nested_value_column,
                    )
                dictionary[key] = new_value
            else:
                resolve_included_files(value, base_file_name)


def load_configuration(
    filename: Union[str, Path],
    sheet: Optional[str] = None,
    key_column: Optional[str] = None,
    value_column: Optional[str] = None,
):
    """Load configuration from a JSON/YAML or table file.

    The format is decided based on the file extension and may be:

    * JSON (``.json``)
    * YAML (``.yaml`` / ``.yml``)
    * CSV/XLSX/ODS table (see :func:`load_config_table`)

    After loading, any nested files referenced via ``include_file`` entries
    are resolved and materialized.

    Args:
        filename: Configuration file path.
        sheet: Optional sheet name for spreadsheet-based configs.
        key_column: Optional key column specification.
        value_column: Optional value column specification.

    Returns:
        Configuration dictionary (possibly nested).
    """
    if isinstance(filename, str):
        filename = Path(filename)
    config = load_one_configuration(
        filename, sheet=sheet, key_column=key_column, value_column=value_column
    )
    resolve_included_files(config, base_file_name=filename)
    return config


def table_info_from_text(text, sheet=None, key_column=None, value_column=None):
    """Convert a comma-separated string of key-value pairs to table info.

    Items are separated by commas. Keys and values can be separated by
    ``=`` or ``:``, as well as variants including spaces. If an item has
    no explicit key, it is treated as the ``key_column`` value.

    Recognized keys are ``'sheet'``, ``'key_column'``, and ``'value_column'``.

    Args:
        text: Comma-separated key-value specification string.
        sheet: Default sheet name.
        key_column: Default key column specification.
        value_column: Default value column specification.

    Returns:
        A SimpleNamespace with attributes ``sheet``, ``key_column``,
        and ``value_column``.

    Raises:
        ValueError: If an unknown key is encountered.
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


def load_config_table(
    filename: Union[str, Path],
    sheet: Optional[str] = None,
    key_column: Optional[str] = None,
    value_column: Optional[str] = None,
):
    """Load configuration from CSV, ODS, or XLSX into a list of records.

    Values that can be converted into int or float are converted. Cells that
    can be parsed as JSON are loaded into Python data structures (dicts,
    lists, etc.). The entire file is read into memory.

    Args:
        filename: Path to the configuration table.
        sheet: Optional sheet name (for ``.xlsx`` or ``.ods``).
        key_column: Optional key column specification.
        value_column: Optional value column specification.

    Returns:
        Nested configuration dictionary derived from flat table.
    """
    path = Path(filename)
    suffix = path.suffix.lower()

    if suffix not in [".csv", ".ods"]:
        return load_config_xlsx(
            path, sheet=sheet, key_column=key_column, value_column=value_column
        )

    if suffix == ".ods":
        return load_config_ods(
            path, sheet=sheet, key_column=key_column, value_column=value_column
        )

    return load_config_csv(path, key_column=key_column, value_column=value_column)


def column_from_string(arg, default, fallback):
    """Return zero-based column index derived from a column specification.

    Values convertible to an integer are treated as one-based column indices
    and converted to zero-based indices. Non-integer values are passed to the
    ``fallback`` function (e.g., for spreadsheet-style letters).

    For None or an empty string, the ``default`` value is returned.

    Args:
        arg: Column specification (int-like or string).
        default: Default zero-based column index.
        fallback: Callable used for non-integer column specifications.

    Returns:
        Zero-based column index as an integer.
    """
    if not arg:
        return default
    else:
        try:
            return int(arg) - 1
        except ValueError:
            return fallback(arg)


def validate_key(arg):
    """Validate a configuration key and normalize it.

    This function accepts any value intended to be a configuration key and
    returns a usable string key without leading or trailing whitespace.
    Keys that are invalid (empty, contain whitespace, NaN, or None) return
    None and should be ignored.

    Args:
        arg: Raw key value from a config table.

    Returns:
        A normalized key string, or None if the key is invalid.
    """
    if isinstance(arg, str):
        # Allow for whitespace around the key.
        arg = arg.strip()
        if not arg or " " in arg:
            return None
        return arg
    if arg is None:
        return None
    if isinstance(arg, float) and math.isnan(arg):
        # NaN is None in our context since we don't use NaN in configuration
        # and Pandas reader defaults to NaN for no-data values.
        return None
    # All keys should be strings, so convert numbers and anything else to strings.
    return str(arg)


def load_config_csv(
    filename: Union[str, Path],
    key_column: Optional[str] = None,
    value_column: Optional[str] = None,
):
    """Load configuration from a CSV table.

    The ``key_column`` and ``value_column`` parameters can be one-based column
    indices or spreadsheet-like column letters (``A-Z``). Rows without keys or
    with invalid keys are ignored (see :func:`validate_key`).

    Values that can be converted from string to other types are converted
    automatically (see :func:`text_to_value`).

    Args:
        filename: Path to CSV configuration file.
        key_column: Key column specification.
        value_column: Value column specification.

    Returns:
        Nested configuration dictionary derived from the CSV table.
    """
    path = Path(filename)
    table = {}
    with path.open() as file:
        # pylint: disable=import-outside-toplevel
        import csv

        key_column_idx = column_from_string(
            key_column, default=0, fallback=lambda x: ord(x) - ord("A")
        )
        value_column_idx = column_from_string(
            value_column, default=key_column_idx + 1, fallback=lambda x: ord(x) - ord("A")
        )

        for row in csv.reader(file):
            key = validate_key(row[key_column_idx])
            if key:
                value = text_to_value(row[value_column_idx])
                table[key] = value

    return record_to_nested_dictionary(table)


def load_config_xlsx(
    filename: Union[str, Path],
    sheet: Optional[str] = None,
    key_column: Optional[str] = None,
    value_column: Optional[str] = None,
):
    """Load configuration from an XLSX spreadsheet.

    The ``sheet`` parameter specifies the sheet name (if omitted, the active
    sheet is used). The ``key_column`` and ``value_column`` parameters can be
    one-based indices or spreadsheet-like column letters.

    See :func:`load_config_csv` for details on how keys and values are handled.

    Args:
        filename: Path to XLSX file.
        sheet: Optional sheet name.
        key_column: Key column specification.
        value_column: Value column specification.

    Returns:
        Nested configuration dictionary derived from the XLSX table.
    """
    path = Path(filename)
    table = {}

    # pylint: disable=import-outside-toplevel
    import openpyxl
    from openpyxl.utils import column_index_from_string

    key_column_idx = column_from_string(
        key_column, default=0, fallback=lambda x: column_index_from_string(x) - 1
    )
    value_column_idx = column_from_string(
        value_column,
        default=key_column_idx + 1,
        fallback=lambda x: column_index_from_string(x) - 1,
    )

    import warnings

    with warnings.catch_warnings():
        # We want to use validation functions in the spreadsheet,
        # but it does not matter whether they are supported by the reader here.
        warnings.filterwarnings(
            "ignore", message="Data Validation extension is not supported"
        )
        workbook = None
        try:
            workbook = openpyxl.load_workbook(path, read_only=True)
            ws = workbook[sheet] if sheet else workbook.active
            for row in ws.iter_rows(values_only=True):
                key = validate_key(row[key_column_idx])
                if key:
                    value = text_to_value(row[value_column_idx])
                    table[key] = value
        finally:
            # Read-only mode requires an explicit close and
            # the workbook object is not a context manager.
            if workbook:
                workbook.close()
    return record_to_nested_dictionary(table)


def load_config_ods(
    filename: Union[str, Path],
    sheet: Optional[Union[int, str]] = None,
    key_column: Optional[str] = None,
    value_column: Optional[str] = None,
):
    """Load configuration from an ODS spreadsheet.

    The ``sheet`` parameter specifies the sheet index or name. The
    ``key_column`` and ``value_column`` parameters can be one-based indices
    or spreadsheet-like column letters. When columns are specified with
    letters and the value column precedes the key column, only single-letter
    columns are supported.

    See :func:`load_config_csv` for details on key and value handling.

    Args:
        filename: Path to ODS file.
        sheet: Sheet index or name.
        key_column: Key column specification.
        value_column: Value column specification.

    Returns:
        Nested configuration dictionary derived from the ODS table.
    """
    table = {}

    # pylint: disable=import-outside-toplevel
    import pandas

    sheet = sheet if sheet else 0

    key_column = column_from_string(key_column, default=0, fallback=lambda x: x)
    value_column = column_from_string(value_column, default=1, fallback=lambda x: x)

    # The columns are always returned in the order as in the table, not in
    # the order specified in the parameter, so we need to know the relative order
    # of the two columns.
    flip_order = False
    # Assuming both are of the same type.
    if isinstance(key_column, int) and isinstance(value_column, int):
        cols = [key_column, value_column]
        if key_column > value_column:
            flip_order = True
    else:
        cols = f"{key_column},{value_column}"
        # Multi-letter columns which are in opposite order are not handled.
        if (
            len(key_column) == 1
            and len(value_column) == 1
            and ord(key_column) > ord(value_column)
        ):
            flip_order = True

    if flip_order:
        key_column_index = 2
        value_column_index = 1
    else:
        key_column_index = 1
        value_column_index = 2

    data = pandas.read_excel(
        Path(filename), sheet_name=sheet, header=None, usecols=cols
    )
    table = {}
    for row in data.itertuples():
        key = validate_key(row[key_column_index])
        if key:
            value = text_to_value(row[value_column_index])
            if isinstance(value, float) and math.isnan(value):
                value = None
            table[key] = value
    return record_to_nested_dictionary(table)


def add_dict_config_to_table(table, value, keys=None):
    """Add a nested dictionary to a mapping representing a table.

    Args:
        table: Mapping from slash-separated keys to scalar values.
        value: Nested dictionary.
        keys: Internal recursion parameter; list of nested keys.
    """
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
    """Convert a nested dictionary to a flattened table mapping.

    Args:
        value: Nested configuration dictionary.

    Returns:
        A mapping from slash-separated key paths to scalar values.
    """
    table = {}
    add_dict_config_to_table(table, value)
    return table


def print_table_config(config, file=None):
    """Print a table mapping as key|value lines.

    This function prints each key–value pair, separated by a pipe. Iterable
    values (except strings) are JSON-encoded. It does not quote or escape the
    separator in values.

    Args:
        config: Mapping from keys to values.
        file: Optional file-like object to write to (defaults to stdout).
    """
    for key, value in config.items():
        if isinstance(value, Iterable) and not isinstance(value, str):
            value = json.dumps(value)
        print(f"{key}|{value}", file=file)


def load_scenario_table(filename: Union[str, Path]):
    """Load a scenario table from CSV, XLSX, or ODS into a list of dictionaries.

    Values that can be converted to numeric types or JSON are converted using
    :func:`text_to_value`.

    Args:
        filename: Path to scenario table file.

    Returns:
        List of dictionaries, one per row in the scenario table.
    """
    path = Path(filename)
    table = []

    if path.suffix.lower() != ".csv":
        import openpyxl

        workbook = None
        try:
            workbook = openpyxl.load_workbook(path, read_only=True)
            sheet = workbook.active
            # Get header.
            header = [cell.value for cell in sheet[1]]
            # Read rows excluding the header.
            for old_row in sheet.iter_rows(min_row=2):
                new_row = {}
                for key, cell in zip(header, old_row):
                    new_row[key] = text_to_value(cell.value)
                table.append(new_row)
        finally:
            if workbook:
                workbook.close()
        return table

    # CSV path
    with path.open() as file:
        import csv

        for row in csv.DictReader(file):
            for key, value in row.items():
                row[key] = text_to_value(value)
            table.append(row)
    return table


def load_cfrp_schedule(filename, date_format=None):
    """Load a cut flower release program (CFRP) schedule from CSV.

    The CSV is expected to contain columns ``date``, ``origin_nm``, and
    ``commodity`` (case-insensitive). Each row defines one combination of
    date, origin, and commodity.

    Args:
        filename: Path to CFRP schedule CSV file.
        date_format: Date format string for parsing the date column. If not
            provided, defaults to ``"%Y-%m-%d"``.

    Returns:
        Dictionary mapping ``(commodity, origin)`` tuples to sets of dates.
    """
    if not date_format:
        date_format = "%Y-%m-%d"
    schedule = {}
    # Read as CSV
    with open(filename) as file:
        # Import file- or format-specific items only when need.
        # pylint: disable=import-outside-toplevel
        import csv
        from datetime import datetime

        for row in csv.DictReader(file):
            for key, value in row.items():
                if key.lower() == "date":
                    date = datetime.strptime(value, date_format).date()
                elif key.lower() == "origin_nm":
                    origin = value
                elif key.lower() == "commodity":
                    commodity = value
            combo = (commodity, origin)
            if combo not in schedule:
                # Using set to ensure we have no duplicate dates.
                schedule[combo] = set()
            schedule[combo].add(date)
    return schedule


def load_skip_lot_consignment_records(filename, tracked_properties):
    """Load skip-lot consignment records with associated compliance levels.

    Only ``tracked_properties`` are considered and are assumed to uniquely
    identify consignment records with distinct compliance levels. If the
    compliance level can be converted to a number, it is converted.

    Args:
        filename: Path to a CSV file containing consignment records.
        tracked_properties: Iterable of column names that uniquely identify a
            consignment.

    Returns:
        Dictionary mapping tuples of tracked property values to compliance
        levels.
    """
    records = {}
    # Read as CSV
    with open(filename) as file:
        # Import file- or format-specific items only when need.
        # pylint: disable=import-outside-toplevel
        import csv

        for row in csv.DictReader(file):
            combo = []
            for tracked_property in tracked_properties:
                combo.append(row[tracked_property])
            level = row["compliance_level"]
            records[tuple(combo)] = text_to_value(level)
    return records


def get_validated_effectiveness(config):
    """Validate and return inspector effectiveness from configuration.

    Args:
        config: Configuration dictionary with an ``inspection.effectiveness``
            entry.

    Returns:
        Effectiveness value between 0 and 1 inclusive.

    Raises:
        ValueError: If the effectiveness is outside of [0, 1].
    """
    effectiveness = config["inspection"].get("effectiveness", 1)
    if 0 <= effectiveness <= 1:
        return effectiveness
    raise ValueError("Effectiveness must be between 0 and 1")


def load_compliance_lookup_csv(filepath: Path):
    """Build a compliance lookup table from a CSV file.

    The table maps:
      * key   → N-tuple of values from all columns before ``'Compliance'``.
      * value → (Detection Level, Confidence Levels).

    The function populates a dictionary with:
      * ``'rbs_variables'``: list of key column names.
      * key tuples → (Detection Level, Confidence Levels).

    Args:
        filepath: Path to the compliance CSV file.

    Returns:
        Dictionary containing RBS variables and key-specific detection/
        confidence tuples.

    Raises:
        ValueError: If the file is empty or required columns are missing.
    """
    comp_table = {}

    with open(filepath, newline="", encoding="utf-8-sig") as f:
        r = csv.reader(f)
        headers = [h.strip() for h in next(r)]
        if not headers:
            raise ValueError("CSV appears to be empty or missing a header row.")

        required = {"Compliance", "Detection Level", "Confidence Levels"}
        missing = [c for c in required if c not in headers]
        if missing:
            raise ValueError(f"Missing required column(s): {', '.join(missing)}")

        comp_idx = headers.index("Compliance")
        key_cols = headers[:comp_idx]  # all columns BEFORE 'Compliance' will be excluded
        comp_table['rbs_variables'] = list(key_cols)

        for row in r:
            # Map row to header names (short rows are padded automatically by zip)
            row_map = {h: (row[i].strip() if i < len(row) else "") for i, h in enumerate(headers)}

            key = tuple(row_map[col] for col in key_cols)
            value = (row_map["Detection Level"], row_map["Confidence Levels"])
            comp_table[key] = value  # last occurrence wins

    return comp_table


def detect_encoding(filepath: Path) -> str:
    """Detect the encoding of a text file.

    Args:
        filepath: Path to the file.

    Returns:
        Detected encoding string.
    """
    with open(filepath, 'rb') as f:
        raw_data = f.read(10000)  # Read first 10KB
        result = chardet.detect(raw_data)
        return result['encoding']


def load_compliance_mapping_csv(filepath: Path) -> Dict[str, Tuple[str, str]]:
    """Load the compliance mapping table.

    Expected columns: ``Compliance | Detection Level | Confidence Levels``.

    Args:
        filepath: Path to the compliance mapping CSV file.

    Returns:
        Dictionary mapping compliance codes to (Detection Level, Confidence
        Levels) pairs.

    Raises:
        ValueError: If required columns are missing or file is empty.
        FileNotFoundError: If ``filepath`` does not exist.
        UnicodeDecodeError: If the file cannot be decoded with any tried
            encoding.
    """
    if not filepath.exists():
        raise FileNotFoundError(f"Compliance mapping file not found: {filepath}")

    # Auto-detect encoding if not provided
    try:
        encoding = detect_encoding(filepath)
        print(f"Auto-detected encoding for {filepath.name}: {encoding}")
    except Exception as e:
        warnings.warn(f"Could not detect encoding, trying common encodings: {e}")
        encoding = 'utf-8'

    # Try multiple encodings
    encodings_to_try = [
        encoding,
        'utf-8-sig',
        'utf-8',
        'latin-1',
        'iso-8859-1',
        'cp1252',
        'windows-1252'
    ]

    last_error = None
    for enc in encodings_to_try:
        try:
            return _load_compliance_mapping_with_encoding(filepath, enc)
        except UnicodeDecodeError as e:
            last_error = e
            continue
        except Exception as e:
            # If it's not an encoding error, raise it
            raise

    # If all encodings failed
    raise UnicodeDecodeError(
        'utf-8', b'', 0, 1,
        f"Failed to decode file with any encoding. Last error: {last_error}"
    )


def _load_compliance_mapping_with_encoding(filepath: Path, encoding: str) -> Dict[str, Tuple[str, str]]:
    """Load compliance mapping CSV with a specific encoding.

    Args:
        filepath: Path to the CSV file.
        encoding: Text encoding to use.

    Returns:
        Mapping from compliance codes to (Detection Level, Confidence Levels)
        tuples.

    Raises:
        ValueError: If the file is empty, missing a header row, or missing
            required columns.
    """
    mapping = {}

    with open(filepath, newline="", encoding=encoding, errors='replace') as f:
        reader = csv.reader(f)

        # Read and validate headers
        try:
            headers = [h.strip() for h in next(reader)]
        except StopIteration:
            raise ValueError("Compliance mapping CSV file is empty.")

        if not headers or all(h == "" for h in headers):
            raise ValueError("Compliance mapping CSV is missing a header row.")

        # Validate required columns
        required = {"Compliance", "Detection Level", "Confidence Levels"}
        missing = required - set(headers)
        if missing:
            raise ValueError(
                f"Compliance mapping CSV missing required column(s): {', '.join(sorted(missing))}"
            )

        # Get column indices
        comp_idx = headers.index("Compliance")
        det_level_idx = headers.index("Detection Level")
        conf_levels_idx = headers.index("Confidence Levels")

        # Process data rows - track all occurrences
        compliance_occurrences = {}  # compliance -> list of (row_num, full_row_data)

        for row_num, row in enumerate(reader, start=2):
            if not row or all(cell.strip() == "" for cell in row):
                continue  # Skip empty rows

            if len(row) <= max(comp_idx, det_level_idx, conf_levels_idx):
                warnings.warn(f"Row {row_num} has insufficient columns, skipping.")
                continue

            # Build row map with all columns
            row_map = {
                h: (row[i].strip() if i < len(row) else "")
                for i, h in enumerate(headers)
            }

            compliance = row_map["Compliance"]
            detection_level = row_map["Detection Level"]
            confidence_levels = row_map["Confidence Levels"]

            if not compliance:
                warnings.warn(f"Row {row_num} has empty Compliance value, skipping.")
                continue

            # Track all occurrences of this compliance value with full row data
            if compliance not in compliance_occurrences:
                compliance_occurrences[compliance] = []
            compliance_occurrences[compliance].append((row_num, row_map))

            mapping[compliance] = (detection_level, confidence_levels)

        # Find duplicates (compliance values that appear more than once)
        duplicates = {k: v for k, v in compliance_occurrences.items() if len(v) > 1}

        # Enhanced duplicate warning with table format showing all occurrences
        if duplicates:
            total_duplicate_rows = sum(len(occurrences) for occurrences in duplicates.values())
            first_dup_compliance = next(iter(duplicates.keys()))
            first_dup_row = duplicates[first_dup_compliance][0][0]

            # Build the warning message
            dup_lines = [
                f"Found {len(duplicates)} duplicate Compliance value(s) in mapping "
                f"({total_duplicate_rows} total rows affected). "
                f"Last occurrence will be used. First duplicate at row {first_dup_row}: '{first_dup_compliance}'",
                ""  # Blank line for readability
            ]

            # Determine max duplicates to show in detail
            max_keys_to_show = 3
            keys_shown = 0

            for compliance, occurrences in list(duplicates.items())[:max_keys_to_show]:
                keys_shown += 1

                # Show header for this duplicate group
                dup_lines.append(f"\nDuplicate #{keys_shown} - Compliance: '{compliance}'")
                dup_lines.append(f"  Found {len(occurrences)} occurrence(s):")

                # Table header with ALL columns
                header = "  Row | " + " | ".join(headers)
                dup_lines.append(header)
                dup_lines.append("  " + "-" * (len(header) - 2))

                # Show all occurrences of this duplicate
                for row_num, row_data in occurrences:
                    # Build row display with all columns in order
                    row_values = [row_data.get(h, "") for h in headers]
                    row_display = f"  {row_num:4d} | " + " | ".join(str(v) for v in row_values)
                    dup_lines.append(row_display)

            # Summary if there are more duplicates
            if len(duplicates) > max_keys_to_show:
                remaining = len(duplicates) - max_keys_to_show
                dup_lines.append(f"\n... and {remaining} more duplicate Compliance value(s) not shown")

            warnings.warn("\n".join(dup_lines))

    return mapping


def load_compliance_table_csv(
        filepath: Path,
        use_parquet: bool = True
) -> Dict:
    """Load an RBS compliance table with automatic format and encoding handling.

    This function loads a compliance table either from a parquet file (if
    available and ``use_parquet`` is True) or from a CSV file, performing
    encoding detection if needed.

    For CSV, the function returns a dictionary with:

    * ``'rbs_variables'``: list of key column names.
    * key tuples → compliance codes.
    * ``'_compliance_values'``: set of all compliance codes found.

    Args:
        filepath: Path to compliance file (.csv or .parquet).
        use_parquet: If True and a matching ``.parquet`` file exists, load
            that instead of CSV.

    Returns:
        Dictionary representing the compliance table.

    Raises:
        FileNotFoundError: If no appropriate file is found.
        UnicodeDecodeError: If CSV decoding fails under all tried encodings.
    """
    # Check for parquet version
    parquet_path = filepath.with_suffix('.parquet')
    if use_parquet and parquet_path.exists():
        df = pd.read_parquet(parquet_path)
        print(f"Loaded {len(df):,} rows from parquet")
    else:
        # Fall back to CSV
        if not filepath.exists():
            raise FileNotFoundError(f"Compliance table file not found: {filepath}")

        # Auto-detect encoding if not provided
        try:
            encoding = detect_encoding(filepath)
            print(f"Auto-detected encoding for {filepath.name}: {encoding}")
        except Exception as e:
            warnings.warn(f"Could not detect encoding, trying common encodings: {e}")
            encoding = 'utf-8'

        # Try multiple encodings
        encodings_to_try = [
            encoding,
            'utf-8-sig',
            'utf-8',
            'latin-1',
            'iso-8859-1',
            'cp1252',
            'windows-1252'
        ]

        last_error = None
        for enc in encodings_to_try:
            try:
                return _load_compliance_table_with_encoding(filepath, enc)
            except UnicodeDecodeError as e:
                last_error = e
                continue
            except Exception as e:
                raise

        raise UnicodeDecodeError(
            'utf-8', b'', 0, 1,
            f"Failed to decode file with any encoding. Last error: {last_error}"
        )

    rbs_variables = [col for col in df.columns if col != 'Compliance']

    # Convert to numpy for faster iteration
    keys_array = df[rbs_variables].values
    compliance_array = df['Compliance'].values

    compliance_dict = {
        'rbs_variables': rbs_variables,
        '_compliance_values': set(compliance_array)
    }

    # Build dictionary using numpy arrays (faster)
    for i in range(len(keys_array)):
        key = tuple(keys_array[i])
        compliance_dict[key] = compliance_array[i]

    return compliance_dict


def _load_compliance_table_with_encoding(filepath: Path, encoding: str) -> Dict:
    """Load an RBS compliance table from CSV using a specific encoding.

    Args:
        filepath: Path to the CSV file.
        encoding: Encoding to use when reading.

    Returns:
        Dictionary representing the compliance table with:

        * ``'rbs_variables'``: key column names.
        * key tuples → compliance codes.
        * ``'_compliance_values'``: set of all compliance codes.

    Raises:
        ValueError: If the file is empty, missing a header, or missing the
            ``'Compliance'`` column.
    """
    compliance_table = {}

    with open(filepath, newline="", encoding=encoding, errors='replace') as f:
        reader = csv.reader(f)

        # Read and validate headers
        try:
            headers = [h.strip() for h in next(reader)]
        except StopIteration:
            raise ValueError("Compliance table CSV file is empty.")

        if not headers or all(h == "" for h in headers):
            raise ValueError("Compliance table CSV is missing a header row.")

        # Validate required column
        if "Compliance" not in headers:
            raise ValueError("Compliance table CSV missing required column: 'Compliance'")

        # Identify key columns (everything before 'Compliance')
        comp_idx = headers.index("Compliance")
        key_cols = headers[:comp_idx]

        if not key_cols:
            raise ValueError("No key columns found before 'Compliance' column.")

        compliance_table['rbs_variables'] = list(key_cols)

        # Process data rows - track all occurrences
        key_occurrences = {}  # key -> list of (row_num, full_row_data)
        compliance_values = set()

        for row_num, row in enumerate(reader, start=2):
            if not row or all(cell.strip() == "" for cell in row):
                continue  # Skip empty rows

            # Build row map with proper padding
            row_map = {
                h: (row[i].strip() if i < len(row) else "")
                for i, h in enumerate(headers)
            }

            # Create key tuple from key columns
            key = tuple(row_map[col] for col in key_cols)
            compliance = row_map["Compliance"]

            # Track compliance values
            if compliance:
                compliance_values.add(compliance)

            # Track all occurrences of this key with full row data
            if key not in key_occurrences:
                key_occurrences[key] = []
            key_occurrences[key].append((row_num, row_map))

            compliance_table[key] = compliance

        # Find duplicates (keys that appear more than once)
        duplicates = {k: v for k, v in key_occurrences.items() if len(v) > 1}

        # Enhanced duplicate warning with table format showing all occurrences
        if duplicates:
            total_duplicate_rows = sum(len(occurrences) for occurrences in duplicates.values())
            first_dup_key = next(iter(duplicates.keys()))
            first_dup_row = duplicates[first_dup_key][0][0]

            # Build the warning message
            dup_lines = [
                f"Found {len(duplicates)} duplicate key(s) in compliance table "
                f"({total_duplicate_rows} total rows affected). "
                f"Last occurrence will be used. First duplicate at row {first_dup_row}",
                ""  # Blank line for readability
            ]

            # Determine max duplicates to show in detail
            max_keys_to_show = 3
            keys_shown = 0

            for dup_key, occurrences in list(duplicates.items())[:max_keys_to_show]:
                keys_shown += 1

                # Show header for this duplicate group
                dup_lines.append(f"\nDuplicate #{keys_shown} - Key: {dup_key}")
                dup_lines.append(f"  Found {len(occurrences)} occurrence(s):")

                # Table header with ALL columns
                header = "  Row | " + " | ".join(headers)
                dup_lines.append(header)
                dup_lines.append("  " + "-" * (len(header) - 2))

                # Show all occurrences of this duplicate
                for row_num, row_data in occurrences:
                    # Build row display with all columns in order
                    row_values = [row_data.get(h, "") for h in headers]
                    row_display = f"  {row_num:4d} | " + " | ".join(str(v) for v in row_values)
                    dup_lines.append(row_display)

            # Summary if there are more duplicates
            if len(duplicates) > max_keys_to_show:
                remaining = len(duplicates) - max_keys_to_show
                dup_lines.append(f"\n... and {remaining} more duplicate key(s) not shown")

            warnings.warn("\n".join(dup_lines))

        # Store compliance values for validation
        compliance_table['_compliance_values'] = compliance_values

    return compliance_table


def build_compliance_lookup_table(
        compliance_table_filepath: Path,
        mapping_filepath: Path,
        validate_completeness: bool = True
) -> Dict:
    """Build a complete compliance lookup table by joining table and mapping.

    The compliance table associates RBS variables with a compliance code, and
    the mapping associates compliance codes with (Detection Level, Confidence
    Levels). This function joins the two to provide direct lookup of those
    levels from RBS variables.

    Args:
        compliance_table_filepath: Path to compliance table CSV
            (key columns + ``Compliance``).
        mapping_filepath: Path to compliance mapping CSV
            (``Compliance -> Detection/Confidence``).
        validate_completeness: If True, warns about missing or unused mappings.

    Returns:
        Dictionary with:
            * ``'rbs_variables'``: list of key column names.
            * key tuples → (Detection Level, Confidence Levels).

    Raises:
        ValueError: If validation fails (currently only warns without raising).
    """
    # Load both tables
    compliance_table = load_compliance_table_csv(filepath=compliance_table_filepath)
    mapping = load_compliance_mapping_csv(filepath=mapping_filepath)

    # Build final lookup table
    comp_table = {
        'rbs_variables': compliance_table['rbs_variables']
    }

    # Track unmapped compliance values
    unmapped = set()

    # Join the tables
    for key, compliance in compliance_table.items():
        if key in ('rbs_variables', '_compliance_values'):
            continue

        if compliance in mapping:
            comp_table[key] = mapping[compliance]
        else:
            unmapped.add(compliance)
            comp_table[key] = ("UNKNOWN", "UNKNOWN")

    # Validation
    if validate_completeness:
        compliance_in_rbs = compliance_table.get('_compliance_values', set())
        compliance_in_mapping = set(mapping.keys())

        # Check for unmapped compliance values
        if unmapped:
            warnings.warn(
                f"Found {len(unmapped)} Compliance value(s) in compliance table "
                f"without mapping: {sorted(unmapped)}"
            )

        # Check for unused mappings
        unused = compliance_in_mapping - compliance_in_rbs
        if unused:
            warnings.warn(
                f"Found {len(unused)} Compliance value(s) in mapping table "
                f"not used in compliance table: {sorted(unused)}"
            )

    return comp_table