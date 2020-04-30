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

    totals, sim_params = run_simulation(
        config=load_configuration(args.config_file),
        num_simulations=args.num_simulations,
        num_shipments=args.num_shipments,
        seed=args.seed,
        output_f280_file=args.output_file,
        verbose=args.verbose,
        pretty=args.pretty,
    )

##    print(
##        "On average, inspecting {0:.0f}% of shipments.".format(
##            100 * totals.num_inspections / float(args.num_shipments)
##        )
##    )
    print("\n")
    print("Simulation parameters:")
    print("-----------------------")
    print("shipments:\n\t Number shipments simulated: {0}".format(args.num_shipments))
    print("\t Avg. number of boxes per shipment: {0}".format(totals.num_boxes / args.num_shipments))
    print("\t Avg. number of stems per shipment: {0}".format(totals.num_stems / args.num_shipments))
    print("infestation:\n\t type: {0}".format(sim_params.infestation_type))
    if sim_params.infestation_type == "fixed_value":
        print("\t infestation rate: {0}". format(sim_params.infestation_param))
    elif sim_params.infestation_type == "beta":
        print("\t infestation distribution parameters: {0}". format(sim_params.infestation_param))
    print("\t pest arrangement: {0}".format(sim_params.pest_arrangement))
    if sim_params.pest_arrangement == "clustered":
        print("\t cluster width: {0} stems\n\t maximum infested stems per cluster: {1} stems"
            .format(sim_params.cluster_width, sim_params.max_stems_per_cluster)
        )
    print("inspection:\n\t unit: {0}\n\t proportion of box inspected: {1}\n\t sample strategy: {2}"
        .format(sim_params.inspection_unit, sim_params.within_box_pct, sim_params.sample_strategy)
    )
    if sim_params.sample_strategy == "percentage":
        print("\t proportion: {0}".format(sim_params.sample_params))
    elif sim_params.sample_strategy == "hypergeometric":
        print("\t detection level: {0}".format(sim_params.sample_params))
    elif sim_params.sample_strategy == "fixed_n":
        print("\t sample size: {0}".format(sim_params.sample_params))
    print("\t selection strategy: {0}".format(sim_params.selection_strategy))
    print("\n")

    print("Simulation results:")
    print("-----------------------")
    print("Avg. % shipments slipped: {0:.2f}%".format(totals.missing))
    print("Avg. infestation rate: {0:.3f}".format(totals.true_infestation_rate))
    if not totals.missed_infestation_rate is None:
            print("Avg. infestation rate of slipped shipments: {0:.3f}"
                .format(totals.missed_infestation_rate)
            )
    if not totals.intercepted_infestation_rate is None:
        print("Avg. infestation rate of intercepted shipments: {0:.3f}"
            .format(totals.intercepted_infestation_rate)
        )
    print("Avg. number of boxes opened per shipment:\n\t to completion: {0:.0f}\n\t to detection: {1:.0f}"
        .format(totals.avg_boxes_opened_completion, totals.avg_boxes_opened_detection)
    )
    print("Avg. number of stems inspected per shipment:\n\t to completion: {0:.0f}\n\t to detection: {1:.0f}"
        .format(totals.avg_stems_inspected_completion, totals.avg_stems_inspected_detection)
    )
    print("Avg. % sample completed if sample ends at detection: {0:.2f}%"
        .format(totals.pct_sample_if_to_detection)
    )
    print("Avg. % infested stems unreported if sample ends at detection: {0:.2f}%"
        .format(totals.pct_pest_unreported_if_detection)
    )


if __name__ == "__main__":
    main()
