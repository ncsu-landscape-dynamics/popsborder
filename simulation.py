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

from __future__ import print_function

import sys
import random
import argparse


# global configuration usable in all functions
CONFIG = None


def generate_shipment(port, arrival_time):
    """Generate Inspectional Unit

    Each item (box) in boxes (list) is set to True if a pest/pathogen is there,
    False otherwise.
    """
    # flowers or commodities
    flowers = CONFIG['shipment']['flowers']
    origins = CONFIG['shipment']['origins']
    flower = random.choice(flowers)
    origin = random.choice(origins)
    num_boxes_min = CONFIG['shipment']['boxes']['min']
    num_boxes_max = CONFIG['shipment']['boxes']['max']
    num_boxes = random.randint(num_boxes_min, num_boxes_max)
    pest_probability = CONFIG['shipment']['pest']['probability']
    pest_ratio = CONFIG['shipment']['pest']['ratio']

    if random.random() < pest_probability:
        boxes = [random.random() < pest_ratio for i in range(num_boxes)]
    else:
        boxes = [False] * num_boxes
    return dict(flower=flower, num_boxes=num_boxes, arrival_time=arrival_time,
                boxes=boxes, origin=origin, port=port)


def inspect_shipment1(shipment):
    if shipment['boxes'][0]:
        return False
    return True


def inspect_shipment2(shipment):
    if random.choice(shipment['boxes']):
        return False
    return True


def inspect_shipment3(shipment):
    return not is_shipment_diseased(shipment)


def inspect_shipment4(shipment):
    boxes_to_inspect = CONFIG['inspection']['first_n_boxes']
    for i in range(min(len(shipment['boxes']), boxes_to_inspect)):
        if shipment['boxes'][i]:
            return False
    return True


def is_flower_of_the_day(cfrp, flower, date):
    i = date % len(cfrp)
    if flower == cfrp[i]:
        print("{} is flower of the day".format(flower))
        return True
    return False


def should_inspect1(shipment, date):
    """Decided if the shipment should be expected based on CFRP and size"""
    flower = shipment['flower']
    cfrp = CONFIG['inspection']['cfrp']['flowers']
    max_boxes = CONFIG['inspection']['cfrp']['max_boxes']
    # we have flowers in the CFRP, flower is in CFRP, and not too big shipment
    if cfrp and flower in cfrp and shipment['num_boxes'] <= max_boxes:
        if is_flower_of_the_day(cfrp, flower, date):
            return True  # is FotD, inspect
        return False  # not FotD, release
    return True  # not in CFRP or large, inspect


def should_inspect2(shipment, date):
    """Inspect always"""
    return True


def is_shipment_diseased(shipment):
    for box in shipment['boxes']:
        if box:
            return True
    return False


def count_diseased(shipment):
    count = 0
    for box in shipment['boxes']:
        if box:
            count += 1
    return count


class PrintReporter(object):
    def tp(self):
        print("Inspection worked, didn't miss anything (no pest) [TP]")

    def tn(self):
        print("Inspection worked, found pest [TN]")

    def fp(self, shipment):
        print("Inspection failed, missed {} boxes with pest [FP]".format(
                count_diseased(shipment)))

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
    def fill(self, date, shipment, ok):
        dispensation = "RELEASE" if ok else "PROHIBIT"
        print("F280: {date} {shipment[port]} {shipment[origin]}"
              " {shipment[flower]} {dispensation}".format(
                  shipment, **locals()))


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


def simulation(num_shipments):
    ports = CONFIG['ports']

    form280 = Form280()
    reporter = PrintReporter()
    success_rates = SuccessRates(reporter)
    date = 1

    for i in range(num_shipments):
        port = random.choice(ports)
        arrival_time = i
        shipment = generate_shipment(port, arrival_time)
        if should_inspect1(shipment, date):
            shipment_checked_ok = inspect_shipment4(shipment)
        else:
            shipment_checked_ok = True  # assuming or hoping it's ok
        form280.fill(date, shipment, shipment_checked_ok)
        shipment_actually_ok = not is_shipment_diseased(shipment)
        success_rates.record_success_rate(
            shipment_checked_ok, shipment_actually_ok, shipment)
        # two shipments every nth day
        if i % 3:
            date += 1

    num_diseased = num_shipments - success_rates.ok
    if num_diseased:
        # avoiding float division by zero
        missing = 100 * float(success_rates.fp) / (num_diseased)
        print("Missing {0:.0f}% of shipments with pest.".format(missing))
        return missing
    else:
        return 0  # we didn't miss anything


USAGE = """Usage:
  {} <number of simulations> <number of shipments> <config file>
"""


def load_configuration(filename):
    if sys.argv[3].endswith(".json"):
        import json
        return json.load(open(sys.argv[3]))
    elif sys.argv[3].endswith(".yaml") or sys.argv[3].endswith(".yml"):
        import yaml
        return yaml.load(open(sys.argv[3]))
    else:
        sys.exit("Unknown file extension (file: {})".format(sys.argv[3]))


def main():
    global CONFIG
    parser = argparse.ArgumentParser(description='Pathway Simulation')
    parser.add_argument('num_simulations', type=int,
                        help="Number of simulations")
    parser.add_argument('num_shipments', type=int,
                        help="Number of shipments")
    parser.add_argument('config_file', type=file,
                        help="Path to configuration file")
    args = parser.parse_args()

    num_simulations = args.num_simulations
    num_shipments = args.num_shipments
    CONFIG = load_configuration(sys.argv[3])

    missing = 0
    for i in range(num_simulations):
        missing += simulation(num_shipments)
    missing /= num_simulations
    print("On average, missing {0:.0f}% of shipments with pest.".format(
        missing))
    print("result={0:.2f}".format(missing))


if __name__ == '__main__':
    main()
