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


"""Skipping inspections of consignments

.. codeauthor:: Vaclav Petras <wenzeslaus gmail com>
"""

import functools
import random

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
    Objects can be called as functions to evalute if consignments should be inspected
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
            if "ratio_inspected" not in level:
                raise ValueError("Each level needs to have 'ratio_inspected'")
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

    def compliance_level_for_consignment(self, consignment):
        """Get compliance level associated with a given consignment.

        The level is selected based on consignment properties.
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
        key = tuple(key)
        if key not in self._consignment_records:
            self._consignment_records[key] = self._default_level
            return self._default_level
        return self._consignment_records[key]

    def ratio_inspected_for_level(self, level):
        """Get ratio of items or boxes to inspect associated with a compliance level"""
        return self._levels[level]["ratio_inspected"]

    def __call__(self, consignment, date):
        """Decide whether the consignment should be inspected or not.

        Returns boolean (True for inspect) and this program name (always because it
        is always applied even to unknown consignments because there is a default
        compliance level).
        """
        level = self.compliance_level_for_consignment(consignment)
        ratio_inspected = self.ratio_inspected_for_level(level)
        if random.random() <= ratio_inspected:
            return True, self._program_name
        return False, self._program_name
