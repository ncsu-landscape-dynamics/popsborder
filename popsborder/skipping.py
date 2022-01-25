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
        self._config = config
        self._program_name = self._config.get("name", "cfrp")
        if schedule:
            self._schedule = schedule
        else:
            self._schedule = self._load_schedule()

    def _load_schedule(self):
        """Load schedule from file based on configuration"""
        # TODO: Maybe a year-month-day=>list of flowers dictionary is better.
        # TODO: On the other hand, flowers=>dates dictionary could be used also
        # as a list of eligible flowers.
        # with open(self._config["schedule"])
        return {}

    def __call__(self, consignment, date):
        """Decide if the consignment should be inspected based on CFRP"""
        # returns 2 bools: should_inspect, CFRP applied
        # we have flowers in the CFRP, flower is in CFRP
        dates_for_flower = self._schedule.get((consignment.flower, consignment.origin))
        if dates_for_flower:
            if date in dates_for_flower:
                return True, self._program_name  # is FotD, inspect
            return False, self._program_name  # not FotD, release
        return True, None  # not in CFRP, inspect
