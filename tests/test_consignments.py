"""Test consignments generation and objects"""

import datetime

import pytest

from popsborder.consignments import Consignment


def simple_consignment(flower="Tulipa", origin="Netherlands", date=None):
    """Get consignment with some default values"""
    return Consignment(
        flower=flower,
        num_items=0,
        items=0,
        items_per_box=0,
        num_boxes=0,
        date=date,
        boxes=[],
        pathway="airport",
        port="FL Miami Air CBP",
        origin=origin,
    )


@pytest.mark.parametrize(
    "date",
    [
        datetime.date(2022, 9, 29),
        datetime.date(2022, 10, 1),
        datetime.datetime(2022, 10, 10),
        datetime.datetime(2022, 10, 15),
    ],
)
def test_consignment_date_comapares(date):
    """Check that consignment date attribute compares with date objects"""
    consignment = simple_consignment(date=date)
    assert consignment.date > datetime.date(2022, 9, 28)
