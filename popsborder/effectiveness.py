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

"""Effectiveness configuration and validation"""


def validate_effectiveness(config, verbose=False):
    """Set the effectiveness of the inspector.

    If effective is not set or even out of range, return 1. Otherwise, return the
    effectiveness set by user.

    :param config: Configuration file
    :param verbose: Print the message if True
    """
    effectiveness = 1

    if isinstance(config, dict):
        if "effectiveness" in config["inspection"]:
            if 0 <= config["inspection"]["effectiveness"] <= 1:
                effectiveness = config["inspection"]["effectiveness"]
            else:
                if verbose:
                    print(
                        "Effectiveness out of range: it should be between "
                        "0 and 1."
                    )
    return effectiveness
