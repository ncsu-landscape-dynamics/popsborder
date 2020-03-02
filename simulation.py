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
import random
import argparse
import csv
from collections import namedtuple
from datetime import datetime, timedelta


class ParameterShipmentGenerator:
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
        """Generate Inspection Unit"""
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
    def __init__(self, stems_per_box, filename, separator=","):
        self.infile = open(filename)
        self.reader = csv.DictReader(self.infile, delimiter=separator)
        self.stems_per_box = stems_per_box

    def generate_shipment(self):
        try:
            record = self.reader.next()
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


def inspect_always(shipment, date):
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
    def tp(self):
        print("Inspection worked, didn't miss anything (no pest) [TP]")

    def tn(self):
        print("Inspection worked, found pest [TN]")

    def fp(self, shipment):
        print(
            "Inspection failed, missed {} boxes with pest [FP]".format(
                count_diseased(shipment)
            )
        )

    def fn(self):
        raise RuntimeError("False negative (programmer error)")


class MuteReporter(object):
    def tp(self):
        pass

    def tn(self):
        pass

    def fp(self, shipment):
        pass

    def fn(self):
        raise RuntimeError("False negative (programmer error)")


class Form280(object):
    def __init__(self, file, disposition_codes, separator=","):
        self.file = file
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
        else:
            print(
                "F280: {date:%Y-%m-%d} | {shipment[port]} | {shipment[origin]}"
                " | {shipment[flower]} | {disposition_code}".format(
                    shipment, **locals()
                )
            )


class SuccessRates(object):
    def __init__(self, reporter):
        self.ok = 0
        self.tp = 0
        self.tn = 0
        self.fp = 0
        self.reporter = reporter

    def record_success_rate(self, checked_ok, actually_ok, shipment):
        if checked_ok and actually_ok:
            self.tp += 1
            self.ok += 1
            self.reporter.tp()
        elif not checked_ok and not actually_ok:
            self.tn += 1
            self.reporter.tn()
        elif checked_ok and not actually_ok:
            self.fp += 1
            self.reporter.fp(shipment)
        elif not checked_ok and actually_ok:
            self.reporter.fn()


SimulationResult = namedtuple(
    "SimulationResult",
    ["missing", "num_inspections", "num_boxes_inspected", "num_boxes"],
)


def simulation(config, num_shipments, f280_file):
    # allow for an empty disposition code specification
    disposition_codes = config.get("disposition_codes", {})
    form280 = Form280(f280_file, disposition_codes=disposition_codes)
    reporter = PrintReporter()
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

    for i in range(num_shipments):
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
        missing = 100 * float(success_rates.fp) / (num_diseased)
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


USAGE = """Usage:
  {} <number of simulations> <number of shipments> <config file>
"""


def load_configuration(filename):
    if filename.endswith(".json"):
        import json

        return json.load(open(filename))
    elif filename.endswith(".yaml") or filename.endswith(".yml"):
        import yaml

        if hasattr(yaml, "full_load"):
            return yaml.full_load(open(filename))
        return yaml.load(open(filename))
    else:
        sys.exit("Unknown file extension (file: {})".format(filename))


def main():
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
    args = parser.parse_args()

    num_simulations = args.num_simulations
    num_shipments = args.num_shipments
    config = load_configuration(args.config_file)

    total_missing = 0
    total_num_inspections = 0
    total_num_boxes = 0
    total_num_boxes_inspected = 0
    f280_file = None
    if args.output_file:
        f280_file = open(args.output_file, "w")
    for i in range(num_simulations):
        result = simulation(config, num_shipments, f280_file)
        total_missing += result.missing
        total_num_inspections += result.num_inspections
        total_num_boxes += result.num_boxes
        total_num_boxes_inspected += result.num_boxes_inspected
    # make these relative (reusing the variables)
    total_missing /= float(num_simulations)
    total_num_inspections /= float(num_simulations)
    total_num_boxes /= float(num_simulations)
    total_num_boxes_inspected /= float(num_simulations)
    print("On average, missing {0:.0f}% of shipments with pest.".format(total_missing))
    print(
        "On average, inspecting {0:.0f}% of shipments.".format(
            100 * total_num_inspections / float(num_shipments)
        )
    )
    print(
        "On average, inspected {0:.0f}% of boxes.".format(
            100 * total_num_boxes_inspected / total_num_boxes
        )
    )
    print("---")
    print("slippage: {0:.2f}".format(total_missing))
    print("num_inspections: {0:.0f}".format(total_num_inspections))
    print("total_num_boxes_inspected: {0:.0f}".format(total_num_boxes_inspected))
    if args.output_file:
        f280_file.close()


if __name__ == "__main__":
    main()
