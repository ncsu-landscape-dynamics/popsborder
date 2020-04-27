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
Various outputs for pathways simulation

.. codeauthor:: Vaclav Petras <wenzeslaus gmail com>
"""

from __future__ import print_function, division

import shutil
import weakref
import csv

from .inspections import count_diseased_boxes

if not hasattr(weakref, "finalize"):
    from backports import weakref  # pylint: disable=import-error


def pretty_content(array, config=None):
    """Return string with array content nicelly visualized as unicode text

    Values evaluating to False are replaced with a flower, others with a bug.
    """
    config = config if config else {}
    flower_sign = config.get("flower", "\N{Black Florette}")
    bug_sign = config.get("bug", "\N{Bug}")
    spaces = config.get("spaces", True)
    if spaces:
        separator = " "
    else:
        separator = ""

    def replace(number):
        if number:
            return bug_sign
        else:
            return flower_sign

    pretty = [replace(i) for i in array]
    return separator.join(pretty)


# Pylint 2.4.4 does not see usage of a variables in a format string.
def pretty_header(shipment, line=None, config=None):  # pylint: disable=unused-argument
    """Return header for a shipment

    Basic info about the shipment is included and the remainining space
    in a terminal window is filled with horizonal box characters.
    (The assumption is that this will be printed in the terminal.)
    """
    config = config if config else {}
    size = 80
    if hasattr(shutil, "get_terminal_size"):
        size = shutil.get_terminal_size().columns
    if line is None:
        # We test None but not for "" to allow use of an empty string.
        line = config.get("horizontal_line", "heavy")
    if line.lower() == "heavy":
        horizontal = "\N{Box Drawings Heavy Horizontal}"
    elif line.lower() == "light":
        horizontal = "\N{Box Drawings Light Horizontal}"
    elif line == "space":
        horizontal = " "
    else:
        horizontal = line
    header = (
        "{horizontal}{horizontal} Shipment"
        " {horizontal}{horizontal}"
        " Boxes: {shipment[num_boxes]} {horizontal}{horizontal}"
        " Stems: {shipment[num_stems]} "
    ).format(**locals())
    if size > len(header):
        size = size - len(header)
    else:
        size = 0
    rule = horizontal * size  # pylint: disable=possibly-unused-variable
    return "{header}{rule}".format(**locals())


def pretty_shipment_stems(shipment, config=None):
    """Pretty-print shipment focusing on individual stems"""
    config = config if config else {}
    # pylint: disable=possibly-unused-variable
    header = pretty_header(shipment, config=config)
    body = pretty_content(shipment["stems"], config=config)
    return "{header}\n{body}".format(**locals())


def pretty_shipment_boxes(shipment, config=None):
    """Pretty-print shipment showing individual stems in boxes"""
    config = config if config else {}
    line = config.get("box_line", "|")
    spaces = config.get("spaces", True)
    if line == "pipe":
        line = "|"
    if spaces:
        separator = " {} ".format(line)
    else:
        separator = line
    # pylint: disable=possibly-unused-variable
    header = pretty_header(shipment, config=config)
    body = separator.join(
        [pretty_content(box.stems, config=config) for box in shipment["boxes"]]
    )
    return "{header}\n{body}".format(**locals())


def pretty_shipment_boxes_only(shipment, config=None):
    """Pretty-print shipment showing individual boxes"""
    config = config if config else {}
    # pylint: disable=possibly-unused-variable
    line = config.get("horizontal_line", "light")
    header = pretty_header(shipment, line=line, config=config)
    body = pretty_content(shipment["boxes"], config=config)
    return "{header}\n{body}".format(**locals())


def pretty_print_shipment(shipment, style, config=None):
    """Pretty-print shipment in a given style

    :param style: Style of pretty-printing (boxes, boxes_only, stems)
    """
    config = config if config else {}
    if style == "boxes":
        return pretty_shipment_boxes(shipment, config=config)
    elif style == "boxes_only":
        return pretty_shipment_boxes_only(shipment, config=config)
    elif style == "stems":
        return pretty_shipment_stems(shipment, config=config)
    else:
        raise ValueError(
            "Unknown style value for pretty printing of shipments: {pretty}".format(
                **locals()
            )
        )


class PrintReporter(object):
    """Reporter class which prints a message for each shipment"""

    # Reporter objects carry functions, but many not use any attributes.
    # pylint: disable=no-self-use,missing-function-docstring
    def true_negative(self):
        print("Inspection worked, didn't miss anything (no pest) [TN]")

    def true_positive(self):
        print("Inspection worked, found pest [TP]")

    def false_negative(self, shipment):
        print(
            "Inspection failed, missed {} boxes with pest [FN]".format(
                count_diseased_boxes(shipment)
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
    """Creates F280 records from the simulated data"""

    def __init__(self, file, disposition_codes, separator=","):
        """Prepares file for writing

        :param file: Name of the file to write to or ``-`` (dash) for printing
        :param disposition_codes: Conversion table for output disposition codes
        :param separator: Value (field) separator for the output CSV file
        """
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
                lineterminator="\n",
                quoting=csv.QUOTE_NONNUMERIC,
            )
            self.writer.writerow(columns)

    def disposition(self, ok, must_inspect, applied_program):
        """Get disposition code for the given parameters

        Provides defaults if the disposition code table does not contain
        a specific value.

        See :meth:`fill` for details about the parameters.
        """
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
        """Fill one entry in the F280 form

        :param date: Shipment or inspection date
        :param shipment: Shipment which was tested
        :param ok: True if the shipment was tested negative (no pest present)
        :param must_inspect: True if the shipment was selected for inspection
        :param apllied_program: Identifier of the program applied or None
        """
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
            self.true_positive += 1
            self.reporter.true_positive()
        elif checked_ok and not actually_ok:
            self.false_negative += 1
            self.reporter.false_negative(shipment)
        elif not checked_ok and actually_ok:
            raise RuntimeError(
                "Inspection result is infested,"
                " but actually the shipment is not infested (programmer error)"
            )
