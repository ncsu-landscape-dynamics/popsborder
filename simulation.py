#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Simulation for evaluataion of pathways
# Copyright (C) 2018 Vaclav Petras

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
Simulation for evaluataion of pathways

.. codeauthor:: Vaclav Petras <wenzeslaus gmail com>
"""

from __future__ import print_function, division

import sys
import math
import types
import random
import argparse
import weakref
import csv
from collections import namedtuple
from datetime import datetime, timedelta


if not hasattr(weakref, "finalize"):
    from backports import weakref


class ParameterShipmentGenerator:
    """Generate a shipments based on configuration parameters"""

    def __init__(self, parameters, ports, start_date):
        """Set parameters for shipement generation

        :param parameters: Shipment parameters
        :param ports: List of ports to choose from
        """
        self.params = parameters
        self.ports = ports
        self.num_generated = 0
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d")
        self.date = start_date

    def generate_shipment(self):
        """Generate a new shipment"""
        # flowers or commodities
        port = random.choice(self.ports)
        flowers = self.params["flowers"]
        origins = self.params["origins"]
        flower = random.choice(flowers)
        origin = random.choice(origins)
        num_boxes_min = self.params["boxes"]["min"]
        num_boxes_max = self.params["boxes"]["max"]
        num_boxes = random.randint(num_boxes_min, num_boxes_max)
        boxes = [False] * num_boxes
        self.num_generated += 1
        # two shipments every nth day
        if self.num_generated % 3:
            self.date += timedelta(days=1)

        return dict(
            flower=flower,
            num_boxes=num_boxes,
            arrival_time=self.date,
            boxes=boxes,
            origin=origin,
            port=port,
        )


class F280ShipmentGenerator:
    """Generate a shipments based on existing F280 records"""

    def __init__(self, stems_per_box, filename, separator=","):
        self.infile = open(filename)
        self.reader = csv.DictReader(self.infile, delimiter=separator)
        self.stems_per_box = stems_per_box

    def generate_shipment(self):
        """Generate a new shipment"""
        try:
            record = next(self.reader)
        except StopIteration:
            raise RuntimeError(
                "More shipments requested than number of records in provided F280"
            )

        stems = int(record["QUANTITY"])
        if record["PATHWAY"] == "Airport":
            stems_per_box = self.stems_per_box["air"]["default"]
        elif record["PATHWAY"] == "Maritime":
            stems_per_box = self.stems_per_box["Maritime"]["default"]
        else:
            stems_per_box = self.stems_per_box["default"]

        num_boxes = int(round(stems / float(stems_per_box)))
        if num_boxes < 1:
            num_boxes = 1
        boxes = [False] * num_boxes

        date = datetime.strptime(record["REPORT_DT"], "%Y-%m-%d")
        return dict(
            flower=record["COMMODITY"],
            num_boxes=num_boxes,
            arrival_time=date,
            boxes=boxes,
            origin=record["ORIGIN_NM"],
            port=record["LOCATION"],
        )


def add_pest(config, shipment):
    """Add pest to shipment

    Assuming a list of boxes with the non-infested boxes set to False.

    Each item (box) in boxes (list) is set to True if a pest/pathogen is
    there, False otherwise.
    """
    pest_probability = config["shipment"]["pest"]["probability"]
    pest_ratio = config["shipment"]["pest"]["ratio"]
    if random.random() < pest_probability:
        return
    for i in range(len(shipment["boxes"])):
        if random.random() < pest_ratio:
            shipment["boxes"][i] = True


def inspect_first(shipment):
    if shipment["boxes"][0]:
        return False, 1
    return True, 1


def inspect_one_random(shipment):
    if random.choice(shipment["boxes"]):
        return False, 1
    return True, 1


def inspect_all(shipment):
    return not is_shipment_diseased(shipment), shipment["num_boxes"]


def inspect_first_n(num_boxes, shipment):
    num_boxes = min(len(shipment["boxes"]), num_boxes)
    for i in range(num_boxes):
        if shipment["boxes"][i]:
            return False, i + 1
    return True, num_boxes


def inspect_shipment_percentage(config, shipment):
    """Inspect shipments based on the percetantage strategy

    :param config: Configuration to be used
    :param shipement: Shipment to be inspected
    """
    ratio = config["proportion"]
    min_boxes = config.get("min_boxes", 1)
    # closest higher integer
    boxes_to_inspect = int(math.ceil(ratio * len(shipment["boxes"])))
    boxes_to_inspect = max(min_boxes, boxes_to_inspect)
    boxes_to_inspect = min(len(shipment["boxes"]), boxes_to_inspect)
    # in any case, first n boxes
    strategy = config["end_strategy"]
    if strategy == "to_completion":
        pest = 0
        for i in range(boxes_to_inspect):
            if shipment["boxes"][i]:
                pest += 1
        return pest == 0, boxes_to_inspect
    elif strategy == "to_detection":
        for i in range(boxes_to_inspect):
            if shipment["boxes"][i]:
                return False, i + 1
        return True, boxes_to_inspect
    else:
        raise RuntimeError(
            "Unknown end inspection strategy: {strategy}".format(**locals())
        )


def is_flower_of_the_day(cfrp, flower, date):
    """Return True if the flower is FoTD based on naive criteria"""
    i = date.day % len(cfrp)
    if flower == cfrp[i]:
        print("{} is flower of the day".format(flower))
        return True
    return False


def naive_cfrp(config, shipment, date):
    """Decided if the shipment should be expected based on CFRP and size"""
    # returns 2 bools: should_inspect, CFRP applied
    flower = shipment["flower"]
    cfrp = config["flowers"]
    max_boxes = config["max_boxes"]
    # we have flowers in the CFRP, flower is in CFRP, and not too big shipment
    if cfrp and flower in cfrp and shipment["num_boxes"] <= max_boxes:
        if is_flower_of_the_day(cfrp, flower, date):
            return True, "naive_cfrp"  # is FotD, inspect
        return False, "naive_cfrp"  # not FotD, release
    return True, None  # not in CFRP or large, inspect


def inspect_always(shipment, date):  # pylint: disable=unused-argument
    """Inspect always"""
    return True, None


def is_shipment_diseased(shipment):
    for box in shipment["boxes"]:
        if box:
            return True
    return False


def count_diseased(shipment):
    count = 0
    for box in shipment["boxes"]:
        if box:
            count += 1
    return count


class PrintReporter(object):
    """Reporter class which prints a message for each shipment"""
    # Reporter objects carry functions, but many not use any attributes.
    # pylint: disable=no-self-use,missing-function-docstring
    def true_negative(self):
        print("Inspection worked, didn't miss anything (no pest) [TP]")

    def true_positive(self):
        print("Inspection worked, found pest [TN]")

    def false_negative(self, shipment):
        print(
            "Inspection failed, missed {} boxes with pest [FP]".format(
                count_diseased(shipment)
            )
        )


class MuteReporter(object):
    """Reporter class which is completely silent"""
    # pylint: disable=no-self-use,missing-function-docstring
    def true_negative(self):
        pass

    def true_positive(self):
        pass

    def false_negative(self, shipment):
        pass


class Form280(object):
    def __init__(self, file, disposition_codes, separator=","):
        self.print_to_stdout = False
        self.file = None
        if file:
            if file in ("-", "stdout", "print"):
                self.print_to_stdout = True
            else:
                self.file = open(file, "w")
                self._finalizer = weakref.finalize(self, self.file.close)
        self.codes = disposition_codes
        # selection and order of columns to output
        columns = ["REPORT_DT", "LOCATION", "ORIGIN_NM", "COMMODITY", "disposition"]

        if self.file:
            self.writer = csv.writer(
                self.file,
                delimiter=separator,
                quotechar='"',
                quoting=csv.QUOTE_NONNUMERIC,
            )
            self.writer.writerow(columns)

    def disposition(self, ok, must_inspect, applied_program):
        codes = self.codes
        if applied_program in ["naive_cfrp"]:
            if must_inspect:
                if ok:
                    disposition = codes.get("cfrp_inspected_ok", "OK CFRP Inspected")
                else:
                    disposition = codes.get(
                        "cfrp_inspected_pest", "Pest Found CFRP Inspected"
                    )
            else:
                disposition = codes.get("cfrp_not_inspected", "CFRP Not Inspected")
        else:
            if ok:
                disposition = codes.get("inspected_ok", "OK Inspected")
            else:
                disposition = codes.get("inspected_pest", "Pest Found")
        return disposition

    def fill(self, date, shipment, ok, must_inspect, applied_program):
        disposition_code = self.disposition(ok, must_inspect, applied_program)
        if self.file:
            self.writer.writerow(
                [
                    date.strftime("%Y-%m-%d"),
                    shipment["port"],
                    shipment["origin"],
                    shipment["flower"],
                    disposition_code,
                ]
            )
        elif self.print_to_stdout:
            print(
                "F280: {date:%Y-%m-%d} | {shipment[port]} | {shipment[origin]}"
                " | {shipment[flower]} | {disposition_code}".format(
                    shipment, **locals()
                )
            )


class SuccessRates(object):
    """Record and accumulate success rates"""

    def __init__(self, reporter):
        """Initialize values to zero and set the reporter object"""
        self.ok = 0
        self.true_positive = 0
        self.true_negative = 0
        self.false_negative = 0
        self.reporter = reporter

    def record_success_rate(self, checked_ok, actually_ok, shipment):
        """Record testing result for one shipment

        :param checked_ok: True if the shipment tested negative on presence of pest
        :param checked_ok: True if the shipment actually does not have pest
        :param shipmemt: The shipement itself (for reporting purposes)
        """
        if checked_ok and actually_ok:
            self.true_negative += 1
            self.ok += 1
            self.reporter.true_negative()
        elif not checked_ok and not actually_ok:
            self.true_negative += 1
            self.reporter.true_negative()
        elif checked_ok and not actually_ok:
            self.false_negative += 1
            self.reporter.false_negative(shipment)
        elif not checked_ok and actually_ok:
            raise RuntimeError(
                "Inspection result is infested,"
                " but actually the shipment is not infested (programmer error)"
            )


SimulationResult = namedtuple(
    "SimulationResult",
    ["missing", "num_inspections", "num_boxes_inspected", "num_boxes"],
)


def simulation(config, num_shipments, f280_file, verbose=False):
    """Simulate shipments, their infestation, and their inspection

    :param config: Simulation configuration as a dictionary
    :param num_shipments: Number of shipments to generate
    :param f280_file: Filename for output F280 records
    :param verbose: If True, prints messages about each shipment
    """
    # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    # allow for an empty disposition code specification
    disposition_codes = config.get("disposition_codes", {})
    form280 = Form280(f280_file, disposition_codes=disposition_codes)
    if verbose:
        reporter = PrintReporter()
    else:
        reporter = MuteReporter()
    success_rates = SuccessRates(reporter)
    num_inspections = 0
    total_num_boxes_inspected = 0
    total_num_boxes = 0

    if "release_programs" in config:
        if "naive_cfrp" in config["release_programs"]:

            def is_inspection_needed(shipment, date):
                return naive_cfrp(
                    config["release_programs"]["naive_cfrp"], shipment, date
                )

        else:
            raise RuntimeError("Unknown release program: {program}".format(**locals()))
    else:
        is_inspection_needed = inspect_always

    if "input_F280" in config:
        shipment_generator = F280ShipmentGenerator(
            stems_per_box=config["stems_per_box"], filename=config["input_F280"]
        )
    else:
        shipment_generator = ParameterShipmentGenerator(
            parameters=config["shipment"],
            ports=config["ports"],
            start_date="2020-04-01",
        )

    inspection_strategy = config["inspection"]["strategy"]
    if inspection_strategy == "percentage":

        def inspect(shipment):
            return inspect_shipment_percentage(
                config=config["inspection"]["percentage"], shipment=shipment
            )

    elif inspection_strategy == "first_n":

        def inspect(shipment):
            return inspect_first_n(
                num_boxes=config["inspection"]["first_n_boxes"], shipment=shipment
            )

    elif inspection_strategy == "first":
        inspect = inspect_first
    elif inspection_strategy == "one_random":
        inspect = inspect_one_random
    elif inspection_strategy == "all":
        inspect = inspect_all
    else:
        raise RuntimeError(
            "Unknown inspection strategy: {inspection_strategy}".format(**locals())
        )

    for unused_i in range(num_shipments):
        shipment = shipment_generator.generate_shipment()
        add_pest(config, shipment)
        must_inspect, applied_program = is_inspection_needed(
            shipment, shipment["arrival_time"]
        )
        if must_inspect:
            shipment_checked_ok, num_boxes_inspected = inspect(shipment)
            num_inspections += 1
            total_num_boxes_inspected += num_boxes_inspected
            total_num_boxes += shipment["num_boxes"]
        else:
            shipment_checked_ok = True  # assuming or hoping it's ok
        form280.fill(
            shipment["arrival_time"],
            shipment,
            shipment_checked_ok,
            must_inspect,
            applied_program,
        )
        shipment_actually_ok = not is_shipment_diseased(shipment)
        success_rates.record_success_rate(
            shipment_checked_ok, shipment_actually_ok, shipment
        )

    num_diseased = num_shipments - success_rates.ok
    if num_diseased:
        # avoiding float division by zero
        missing = 100 * float(success_rates.false_negative) / (num_diseased)
        if verbose:
            print("Missing {0:.0f}% of shipments with pest.".format(missing))
    else:
        # we didn't miss anything
        missing = 0
    return SimulationResult(
        missing=missing,
        num_inspections=num_inspections,
        num_boxes=total_num_boxes,
        num_boxes_inspected=total_num_boxes_inspected,
    )


def run_simulation(config, num_simulations, num_shipments, output_f280_file, verbose):
    """Run the simulation function specified number of times

    See :func:`simulation` function for explanation of parameters.

    Returns averages computed from the individual simulation runs.
    """
    try:
        # namedtuple is not applicable since we need modifications
        totals = types.SimpleNamespace(
            missing=0, num_inspections=0, num_boxes=0, num_boxes_inspected=0,
        )
    except AttributeError:
        # Python 2 fallback
        totals = lambda: None  # noqa: E731
        totals.missing = 0
        totals.num_inspections = 0
        totals.num_boxes = 0
        totals.num_boxes_inspected = 0

    for unused_i in range(num_simulations):
        result = simulation(config, num_shipments, output_f280_file, verbose)
        totals.missing += result.missing
        totals.num_inspections += result.num_inspections
        totals.num_boxes += result.num_boxes
        totals.num_boxes_inspected += result.num_boxes_inspected
    # make these relative (reusing the variables)
    totals.missing /= float(num_simulations)
    totals.num_inspections /= float(num_simulations)
    totals.num_boxes /= float(num_simulations)
    totals.num_boxes_inspected /= float(num_simulations)
    return totals


USAGE = """Usage:
  {} <number of simulations> <number of shipments> <config file>
"""


def load_configuration(filename):
    """Get the configuration from a JSON or YAML file"""
    if filename.endswith(".json"):
        import json  # pylint: disable=import-outside-toplevel

        return json.load(open(filename))
    elif filename.endswith(".yaml") or filename.endswith(".yml"):
        import yaml  # pylint: disable=import-outside-toplevel

        if hasattr(yaml, "full_load"):
            return yaml.full_load(open(filename))
        return yaml.load(open(filename))
    else:
        sys.exit("Unknown file extension (file: {})".format(filename))


def main():
    """Process command line parameters and run the simulation"""
    parser = argparse.ArgumentParser(description="Pathway Simulation")
    required = parser.add_argument_group("required arguments")
    required.add_argument(
        "--num-simulations", type=int, required=True, help="Number of simulations"
    )
    required.add_argument(
        "--num-shipments", type=int, required=True, help="Number of shipments"
    )
    required.add_argument(
        "--config-file", type=str, required=True, help="Path to configuration file"
    )
    required.add_argument(
        "--output-file", type=str, required=False, help="Path to output F280 csv file"
    )
    required.add_argument(
        "--verbose", action="store_true", help="Print a lot of diagnostic messages",
    )
    args = parser.parse_args()

    totals = run_simulation(
        config=load_configuration(args.config_file),
        num_simulations=args.num_simulations,
        num_shipments=args.num_shipments,
        output_f280_file=args.output_file,
        verbose=args.verbose,
    )

    print("On average, missing {0:.0f}% of shipments with pest.".format(totals.missing))
    print(
        "On average, inspecting {0:.0f}% of shipments.".format(
            100 * totals.num_inspections / float(args.num_shipments)
        )
    )
    print(
        "On average, inspected {0:.0f}% of boxes.".format(
            100 * totals.num_boxes_inspected / totals.num_boxes
        )
    )
    print("---")
    print("slippage: {0:.2f}".format(totals.missing))
    print("num_inspections: {0:.0f}".format(totals.num_inspections))
    print("total_num_boxes_inspected: {0:.0f}".format(totals.num_boxes_inspected))


if __name__ == "__main__":
    main()
