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


def generate_shipment(port, arrival_time):
    # flowers or commodities
    flowers = ['Rose', 'Tulip', 'Acer', 'Actinidia', 'Aegilops', 'Ananas']
    countries = ['Argentina', 'Estonia', 'Taiwan', 'Hawaii']
    flower = random.choice(flowers)
    origin = random.choice(countries)
    num_items = random.randint(1, 50)
    if random.random() < 0.2:
        diseased = [random.random() < 0.5 for i in range(num_items)]
    else:
        diseased = [False] * num_items
    return dict(flower=flower, num_items=num_items, arrival_time=arrival_time,
                diseased=diseased, origin=origin)


def inspect_shipment1(shipment):
    if shipment['diseased'][0]:
        return False
    return True


def inspect_shipment2(shipment):
    if random.choice(shipment['diseased']):
        return False
    return True


def inspect_shipment3(shipment):
    return not is_shipment_diseased(shipment)


def inspect_shipment4(shipment):
    for i in range(min(len(shipment['diseased']), 2)):
        if shipment['diseased'][i]:
            return False
    return True


def is_flower_of_the_day(cfrp, flower, date):
    i = date % len(cfrp)
    if flower == cfrp[i]:
        return True
    return False


def should_inspect1(shipment, date):
    flower = shipment['flower']
    cfrp = ['Rose', 'Tulip', 'Acer', 'Actinidia']
    if flower in cfrp:
        if (is_flower_of_the_day(cfrp, flower, date) or
                shipment['num_items'] > 5):
            return True  # FotD or large, inspect
        return False  # not FotD, skip
    return True  # not in CFRP, inspect


def should_inspect2(shipment, date):
    """Inspect always"""
    return True


def is_shipment_diseased(shipment):
    for item in shipment['diseased']:
        if item:
            return True
    return False


def count_diseased(shipment):
    count = 0
    for item in shipment['diseased']:
        if item:
            count += 1
    return count


class PrintReporter(object):
    def tp(self):
        print("Inspection worked, didn't miss anything (no disease) [TP]")

    def tn(self):
        print("Inspection worked, found diseased [TN]")

    def fp(self, shipment):
        print("Inspection failed, missed {} diseased items [FP]".format(
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
    ports = ['RDU', 'Miami']

    reporter = MuteReporter()
    success_rates = SuccessRates(reporter)
    date = 1

    for i in range(num_shipments):
        port = random.choice(ports)
        arrival_time = i
        shipment = generate_shipment(port, arrival_time)
        if should_inspect2(shipment, date):
            shipment_checked_ok = inspect_shipment4(shipment)
        else:
            shipment_checked_ok = True  # assuming or hoping it's ok
        shipment_actually_ok = not is_shipment_diseased(shipment)
        success_rates.record_success_rate(
            shipment_checked_ok, shipment_actually_ok, shipment)
        # n shipments per day
        if i % 10:
            date += 1

    # TODO: here we have potential float division by zero
    num_diseased = num_shipments - success_rates.ok
    missing = 100 * float(success_rates.fp) / (num_diseased)
    print("Missing {}% of diseased shipments.".format(missing))
    return missing


USAGE = """Usage:
  {} <number of simulations> <number of shipments>
"""


def main():
    if len(sys.argv) != 3:
        sys.exit(USAGE.format(sys.argv[0]))
    num_simulations = sys.argv[1]
    num_shipments = sys.argv[2]
    if not num_simulations or not num_shipments:
        sys.exit(USAGE.format(sys.argv[0]))
    num_simulations = int(num_simulations)
    num_shipments = int(num_shipments)
    missing = 0
    for i in range(num_simulations):
        missing += simulation(num_shipments)
    missing /= num_simulations
    print("In average, missing {0:.0f}% of diseased shipments.".format(
        missing))


if __name__ == '__main__':
    main()
