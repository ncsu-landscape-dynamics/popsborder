#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Simulation for evaluataion of pathways
# Copyright (C) 2018-2020 Vaclav Petras

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


"""
CLI for the simulation of pathways

.. codeauthor:: Vaclav Petras <wenzeslaus gmail com>
"""

from __future__ import print_function, division

import argparse

from .simulation import run_simulation, load_configuration

USAGE = """Usage:
  {} <number of simulations> <number of shipments> <config file>
"""


class CustomHelpFormatter(argparse.RawTextHelpFormatter):
    """Help formatter to have uppercase, not lowercase usage"""

    def add_usage(self, usage, actions, groups, prefix=None):
        """Add usage text"""
        if prefix is None:
            prefix = "Usage: "
        return super(CustomHelpFormatter, self).add_usage(
            usage, actions, groups, prefix
        )


def get_executable_name():
    """Get name of the executable

    Returns "python -m module" if executed with python -m in command line
    using Python 3 (it does not work in Python 2).
    This does not account for execution with python3.

    This is a workaround for:
    argparse support for "python -m module" in help
    https://bugs.python.org/issue22240
    """
    if globals().get("__spec__") is None:
        return None
    else:
        return "python -m {}".format(__spec__.name.partition(".")[0])


def main():
    """Process command line parameters and run the simulation"""
    parser = argparse.ArgumentParser(
        description="Pathway simulation of infested shipments",
        formatter_class=CustomHelpFormatter,
        add_help=False,
        prog=get_executable_name(),
    )
    basic = parser.add_argument_group("Simulation parameters (required)")
    basic.add_argument(
        "--num-shipments", type=int, required=True, help="Number of shipments"
    )
    basic.add_argument(
        "--config-file", type=str, required=True, help="Path to configuration file"
    )
    optional = parser.add_argument_group("Running simulations (optional)")
    optional.add_argument(
        "--num-simulations",
        type=int,
        required=False,
        default=1,
        help="Number of simulations to run",
    )
    optional.add_argument(
        "--seed", type=int, required=False, help="Seed for random generator"
    )
    output_group = parser.add_argument_group("Output (optional)")
    output_group.add_argument(
        "--output-file", type=str, required=False, help="Path to output F280 csv file"
    )
    pretty_choices = (
        ("boxes", "Show boxes with individual stems (default)"),
        ("stems", "Show individual stems only"),
        ("boxes_only", "Show only boxes as the items"),
    )
    output_group.add_argument(
        "--pretty",
        type=str,
        const="boxes",  # default behavior for pretty
        nargs="?",  # value is optional
        choices=[i[0] for i in pretty_choices],
        help=(
            "Show pretty unicode output for each shipment\n"
            + "\n".join(["\n    ".join(i) for i in pretty_choices])
        ),
    )
    output_group.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print messages about each shipment inspection process",
    )
    output_group.add_argument(
        "-h",
        "--help",
        action="help",
        default=argparse.SUPPRESS,
        help="Show this help message and exit",
    )
    args = parser.parse_args()

    totals = run_simulation(
        config=load_configuration(args.config_file),
        num_simulations=args.num_simulations,
        num_shipments=args.num_shipments,
        seed=args.seed,
        output_f280_file=args.output_file,
        verbose=args.verbose,
        pretty=args.pretty,
    )

    print("On average, missing {0:.0f}% of shipments with pest.".format(totals.missing))
    print(
        "On average, inspecting {0:.0f}% of shipments.".format(
            100 * totals.num_inspections / float(args.num_shipments)
        )
    )
    print(
        "On average, inspected {0:.0f}% of boxes.".format(
            totals.pct_boxes_opened_completion
        )
    )
    print("---")
    print("slippage: {0:.2f}".format(totals.missing))
    print("num_inspections: {0:.0f}".format(totals.num_inspections))
    print(
        "total_num_boxes_inspected: {0:.0f}".format(totals.avg_boxes_opened_completion)
    )
    print("true_infestation_rate: {0:.3f}".format(totals.true_infestation_rate))


if __name__ == "__main__":
    main()
