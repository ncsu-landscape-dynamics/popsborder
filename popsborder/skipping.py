# Simulation of contaminated consignments and their inspections
# Copyright (C) 2018-2025 Vaclav Petras and others (see below)

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


"""Skipping inspections of consignments

.. codeauthor:: Vaclav Petras <wenzeslaus gmail com>
"""

import functools
import random
from collections import defaultdict

from .inputs import load_cfrp_schedule, load_skip_lot_consignment_records


def get_inspection_needed_function(config):
    """Based on config, return function to determine if inspection is needed.

    The returned function returns a tuple. The first item is a boolean telling if the
    consignment should be inspected. The second item is a string which is the name of
    the release program applied or None if no release program was applied.
    """
    if "release_programs" in config:
        for name in sorted(config["release_programs"].keys()):
            # Notably, this does not support multiple programs at once.
            # We simply return whatever is the first program alphabetically
            # or raise exception if there is an unknown program name.
            if name == "cfrp":
                return CutFlowerReleaseProgram(config["release_programs"][name])
            if name == "fixed_skip_lot":
                return FixedComplianceLevelSkipLot(config["release_programs"][name])
            if name == "dynamic_skip_lot":
                return DynamicComplianceLevelSkipLot(config["release_programs"][name])
            elif name == "naive_cfrp":
                return functools.partial(
                    naive_cfrp, config["release_programs"][name], name
                )
            else:
                raise RuntimeError(f"Unknown release program: {name}")
    return inspect_always


def inspect_always(consignment, date):  # pylint: disable=unused-argument
    """Inspect always"""
    return True, None


def is_naive_flower_of_the_day(cfrp, flower, date):
    """Return True if the flower is FoTD based on naive criteria"""
    i = date.day % len(cfrp)
    if flower == cfrp[i]:
        return True
    return False


def naive_cfrp(config, name, consignment, date):
    """Decide if the consignment should be inspected based on naive CFRP

    Returns tuple with boolean and string. The boolean requests inspection and the
    string is name of the program provided as parameter.
    """
    flower = consignment.flower
    cfrp = config["flowers"]
    max_boxes = config["max_boxes"]
    # we have flowers in the CFRP, flower is in CFRP, and not too big consignment
    if cfrp and flower in cfrp and consignment.num_boxes <= max_boxes:
        if is_naive_flower_of_the_day(cfrp, flower, date):
            return True, name  # is FotD, inspect
        return False, name  # not FotD, release
    return True, None  # not in CFRP or large, inspect


class CutFlowerReleaseProgram:
    """Cut Flower Release Program (CFRP)

    Constructs CFRP, esp. the schedule, from the configuration during initialization.
    Objects can be called as functions to evaluate if consignments should be inspected
    using this program.
    """

    def __init__(self, config, schedule=None):
        self._program_name = config.get("name", "cfrp")
        if schedule:
            self._schedule = schedule
        else:
            schedule_config = config["schedule"]
            self._schedule = load_cfrp_schedule(
                schedule_config["file_name"],
                date_format=schedule_config.get("date_format"),
            )
        self._ports = config.get("ports")

    def __call__(self, consignment, date):
        """Decide if the consignment should be inspected based on CFRP

        Returns a tuple which contains a boolean indicating whether or not the
        consignment should be inspected and a string which is the name of the
        program (default is 'cfrp') if it was applied. If the program was not
        applied, None is returned.
        """
        # Check if we are in a participating port.
        if self._ports and consignment.port not in self._ports:
            return True, None  # inspect, not in CFRP
        # Look up flower-origin combo is in the program.
        dates_for_flower = self._schedule.get((consignment.flower, consignment.origin))
        if dates_for_flower:
            if date in dates_for_flower:
                return True, self._program_name  # inspect, is FotD
            return False, self._program_name  # release, in CFRP, but not FotD
        return True, None  # inspect, not in CFRP


class FixedComplianceLevelSkipLot:
    """A skip lot program which uses predefined compliance levels for consignments"""

    def __init__(self, config, consignment_records=None):
        """Creates internal consignment records, levels, and defaults.

        Consignment records are read from config under key 'consignment_records',
        from a file linked in config under consignment_records/file_name,
        or directly from the consignment_records parameter.
        While the records in configuration are in a list, the parameter is a dictionary
        with consignment property values as keys and compliance level names as values.
        """
        self._program_name = config.get("name", "fixed_skip_lot")
        self._tracked_properties = config.get("track")
        self._default_level = config.get("default_level")

        levels = config.get("levels")
        self._levels = {}
        for level in levels:
            if "name" not in level:
                raise ValueError("Each level needs to have 'name'")
            if "sampling_fraction" not in level:
                raise ValueError("Each level needs to have 'sampling_fraction'")
            self._levels[level["name"]] = level

        if consignment_records:
            self._consignment_records = consignment_records.copy()
        else:
            records_config = config["consignment_records"]
            if "file_name" in records_config:
                self._consignment_records = load_skip_lot_consignment_records(
                    consignment_records["file_name"],
                    tracked_properties=self._tracked_properties,
                )
            elif isinstance(records_config, list):
                self._consignment_records = {}
                for record in records_config:
                    key = []
                    for tracked_property in self._tracked_properties:
                        key.append(record[tracked_property])
                    self._consignment_records[tuple(key)] = record["compliance_level"]
            else:
                raise ValueError(
                    "The 'consignment_records' config needs to be a list "
                    "or contain 'file_name'"
                )

    def compute_record_key_for_consignment(self, consignment):
        """Get compliance record key for the given given consignment.

        The key is based on consignment's properties which are tracked properties.
        """
        key = []
        for name in self._tracked_properties:
            try:
                property_value = getattr(consignment, name)
            except AttributeError as error:
                raise ValueError(
                    f"Consignment does not have a property '{name}'"
                ) from error
            key.append(property_value)
        return tuple(key)

    def compliance_level_for_consignment(self, consignment):
        """Get compliance level associated with a given consignment.

        The level is selected based on consignment properties.
        """
        key = self.compute_record_key_for_consignment(consignment)
        if key not in self._consignment_records:
            self._consignment_records[key] = self._default_level
            return self._default_level
        return self._consignment_records[key]

    def sampling_fraction_for_level(self, level):
        """Get ratio of items or boxes to inspect associated with a compliance level"""
        return self._levels[level]["sampling_fraction"]

    def __call__(self, consignment, date):
        """Decide whether the consignment should be inspected or not.

        Returns boolean (True for inspect) and this program name (always because it
        is always applied even to unknown consignments because there is a default
        compliance level).
        """
        level = self.compliance_level_for_consignment(consignment)
        sampling_fraction = self.sampling_fraction_for_level(level)
        if random.random() <= sampling_fraction:
            return True, self._program_name
        return False, self._program_name


class DynamicComplianceLevelSkipLot:
    """A skip lot program which dynamically adjusts compliance levels

    Compliance is tracked by compliance group and compliance levels are adjusted based
    on inspection results from previous inspections in the given group.
    The consignment groups are based on tracked properties.
    """

    # Given the configuration, we expect to have many attributes.
    # pylint: disable=too-many-instance-attributes

    def __init__(self, config):
        self._program_name = config.get("name", "dynamic_skip_lot")
        self._tracked_properties = config.get("track")
        if not self._tracked_properties:
            raise ValueError(
                "'track' for tracking consignment properties "
                "needs to be a list with at least one element"
            )

        levels = config.get("levels")
        self._levels = []
        for level in levels:
            if "sampling_fraction" not in level:
                raise ValueError("Each level needs to have 'sampling_fraction'")
            # Ordering is determined by order, not by name.
            self._levels.append(level)
        # We use one-based level numbers rather than zero-based indices.
        self._min_level = 1
        self._max_level = len(self._levels)

        self._start_level = self.get_level_number_from_level_name(
            config.get("start_level", 1)
        )
        self._monitoring_level = config.get("monitoring_level")
        self._decrease_levels = config.get("decrease_levels")
        if self._monitoring_level is not None and self._decrease_levels is not None:
            raise ValueError(
                "Cannot specify both 'monitoring_level' and 'decrease_levels'"
            )
        if self._monitoring_level is not None:
            self._monitoring_level = self.get_level_number_from_level_name(
                self._monitoring_level
            )
        if self._decrease_levels is not None:
            if isinstance(self._decrease_levels, bool):
                self._decrease_levels = int(self._decrease_levels)
            if not isinstance(self._decrease_levels, int):
                raise ValueError(
                    f"'decrease_levels' ({self._decrease_levels}) must be an integer "
                    f"or boolean, not {type(self._decrease_levels)}"
                )

        self._clearance_number = config.get("clearance_number")
        # Min and max records needed for new clearance level evaluation.
        self._min_records = self._clearance_number
        self._max_records = self._clearance_number

        # Quick restating can be defined by a boolean or by special clearance number.
        self._quick_restate_clearance_number = config.get(
            "quick_restate_clearance_number", None
        )
        self._quick_restating = config.get("quick_restating", None)
        # Special clearance number implies quick restating when not explicitly
        # specified, but explicit False disables quick restating.
        if self._quick_restating is None:
            self._quick_restating = self._quick_restate_clearance_number is not None
        if self._quick_restating and self._quick_restate_clearance_number is None:
            self._quick_restate_clearance_number = self._clearance_number
            self._min_records = min(
                self._clearance_number, self._quick_restate_clearance_number
            )
            self._max_records = max(
                self._clearance_number, self._quick_restate_clearance_number
            )

        self._inspection_records = defaultdict(list)
        self._compliance_levels = defaultdict(lambda: self._start_level)
        self._previous_compliance_levels = {}

    def compute_record_key_for_consignment(self, consignment):
        """Get compliance record key for the given given consignment.

        The key is based on consignment's properties which are tracked properties.
        """
        key = []
        for name in self._tracked_properties:
            try:
                property_value = getattr(consignment, name)
            except AttributeError as error:
                raise ValueError(
                    f"Consignment does not have a property '{name}'"
                ) from error
            key.append(property_value)
        return tuple(key)

    def get_level_number_from_level_name(self, name):
        """Convert a level name to a level number (1-based index).

        If the input is an integer, it is returned as-is, so it is safe to pass
        a level number. If the input is a string, it must match one of the names
        assigned to levels. ValueError is raised if no match is found.

        Level names can be numbers and if they are passed as strings, the
        corresponding level  number (1-based index) is still returned based on
        matching the name (rather than considering it as a level number).
        """
        if isinstance(name, int):
            return name
        for index, level in enumerate(self._levels):
            if "name" not in level:
                continue
            if level["name"] == name:
                return index + 1
        raise ValueError(f"Unknown level name '{name}'")

    def add_inspection_result(self, consignment, inspected: bool, result: bool):
        """
        Update the compliance level of a consignment based on an inspection result.

        Parameters:
        consignment: Inspected consignment
        inspected: True if the consignment was inspected, False otherwise
        result: True if the consignment was compliant, False otherwise
        """
        key = self.compute_record_key_for_consignment(consignment)
        if not result:
            self.adjust_compliance_level_after_negative_result(key)
        self._inspection_records[key].append((inspected, result))
        if len(self._inspection_records[key]) < self._min_records:
            # Consider increasing compliance level only
            # if we have enough compliant records.
            return
        num_inspected = 0
        num_compliant = 0
        for recorded_inspected, recorded_result in reversed(
            self._inspection_records[key]
        ):
            if recorded_inspected:
                num_inspected += 1
                if recorded_result:
                    num_compliant += 1
            if num_inspected == self._max_records:
                # Look only at last N records.
                break
        if num_compliant == self._clearance_number:
            # For large number of records, this would be the same as number of
            # inspected, but for small number of records we didn't reach the
            # clearance number of records yet.
            self._inspection_records[key].clear()
            self.increase_compliance_level(key)
        if (
            self._quick_restating
            and num_compliant == self._quick_restate_clearance_number
        ):
            self.restore_compliance_level(key)

    def increase_compliance_level(self, key):
        """Increase compliance level for a given key."""
        if self._compliance_levels[key] == self._max_level:
            return
        self._compliance_levels[key] += 1

    def adjust_compliance_level_after_negative_result(self, key):
        """Adjust compliance level after a negative inspection.

        The exact adjustment depends on the configuration. If 'decrease_levels' is
        set, the compliance level is decreased by that many levels. If
        'monitoring_level' is set, the compliance level is reset to that level.
        If neither is set, the compliance level is reset to the start level.
        """
        if self._decrease_levels:
            self.decrease_compliance_level(key, num_levels=self._decrease_levels)
        elif self._monitoring_level:
            if self._compliance_levels[key] <= self._monitoring_level:
                self.decrease_compliance_level(key, num_levels=1)
            else:
                self.reset_compliance_level(key, self._monitoring_level)
        else:
            if self._compliance_levels[key] <= self._start_level:
                self.decrease_compliance_level(key, num_levels=1)
            else:
                self.reset_compliance_level(key, self._start_level)

    def decrease_compliance_level(self, key, num_levels=1):
        """Decrease compliance level for a given key."""
        self._compliance_levels[key] = max(
            self._min_level, self._compliance_levels[key] - num_levels
        )

    def reset_compliance_level(self, key, level):
        """Reset the compliance level for a given key to the start level."""
        if self._quick_restating:
            self._previous_compliance_levels[key] = self._compliance_levels[key]
        self._compliance_levels[key] = level

    def restore_compliance_level(self, key):
        """Restore the compliance level for a given key to its previous value."""
        if key in self._previous_compliance_levels:
            self._compliance_levels[key] = self._previous_compliance_levels[key]

    def compliance_level_for_consignment(self, consignment):
        """Get compliance level associated with a given consignment.

        The level is selected based on consignment properties.
        """
        key = self.compute_record_key_for_consignment(consignment)
        if key not in self._compliance_levels:
            return self._start_level
        return self._compliance_levels[key]

    def sampling_fraction_for_level(self, level):
        """Get ratio of items or boxes to inspect associated with a compliance level"""
        return self._levels[level - 1]["sampling_fraction"]

    def __call__(self, consignment, date):
        """Decide whether the consignment should be inspected or not.

        Returns boolean (True for inspect) and this program name (always because it
        is always applied even to unknown consignments because there is a default
        compliance level).

        Returns a tuple which contains a boolean indicating whether or not the
        consignment should be inspected and a string which is the name of the
        program.
        """
        level = self.compliance_level_for_consignment(consignment)
        sampling_fraction = self.sampling_fraction_for_level(level)
        if random.random() <= sampling_fraction:
            return True, self._program_name
        return False, self._program_name
