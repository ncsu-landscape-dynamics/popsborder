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


def test_consignment_attribute_access():
    """Check that consignment supports attribute access"""
    consignment = simple_consignment(origin="Mexico")
    assert consignment.origin == "Mexico"


def test_consignment_dict_access():
    """Check that consignment supports dictionary-like (index) access"""
    consignment = simple_consignment(origin="Mexico")
    assert consignment["origin"] == "Mexico"


def test_consignment_attribute_access_unknown():
    """Check that consignment invalid attribute access raises exception"""
    consignment = simple_consignment()
    with pytest.raises(AttributeError) as error:
        consignment.does_not_exist  # pylint: disable=pointless-statement
    assert "does_not_exist" in str(error.value)


def test_consignment_dict_access_unknown():
    """Check that consignment invalid dictionary-like access raises exception"""
    consignment = simple_consignment()
    with pytest.raises(KeyError) as error:
        consignment["does_not_exist"]  # pylint: disable=pointless-statement
    assert "does_not_exist" in str(error.value)


def test_consignment_has_attr():
    """Check that consignment works with hasattr"""
    consignment = simple_consignment()
    assert hasattr(consignment, "origin")
    assert not hasattr(consignment, "does_not_exist")


def test_consignment_flower_commodity():
    """Check that consignment supports both commodity and flower as names for access"""
    consignment = simple_consignment(flower="Tulipa")
    assert consignment.flower == "Tulipa"
    assert consignment.commodity == "Tulipa"


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
