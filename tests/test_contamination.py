"""Test configuration loading functions"""

import datetime

import pytest

from popsborder.consignments import Consignment
from popsborder.contamination import get_contamination_config_for_consignment
from popsborder.inputs import load_configuration_yaml_from_text

CONFIG = """\
contamination:
  consignments:
    - commodity: Liatris
      origin: Netherlands
      contamination:
        arrangement: random_box
    - commodity: Tulipa
      origin: Netherlands
      start_date: 2022-09-29
      end_date: 2022-10-15
      contamination:
        arrangement: random_box
        contamination_unit: box
    - commodity: Gerbera
      origin: Netherlands
      end_date: 2022-04-10
      contamination:
        arrangement: random_box
    - commodity: Gerbera
      origin: Netherlands
      start_date: 2022-08-20
      contamination:
        contamination_unit: item
    - commodity: Hyacinthus
      origin: Israel
    - commodity: Rose
      origin: Netherlands
      use_contamination_defaults: false
      contamination:
        contamination_unit: box
    - commodity: Rose
      origin: Mexico
      use_contamination_defaults: true
      contamination:
        contamination_unit: box
    - commodity: Sedum
      origin: Colombia
      port: FL Miami Air CBP
  contamination_unit: item
  arrangement: random
"""


def simple_consignment(flower, origin, date=None):
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


def test_consignment_matches_contamination_rule():
    """Check that consignment is selected based on a rule"""
    main_config = load_configuration_yaml_from_text(CONFIG)
    consignment = simple_consignment(flower="Sedum", origin="Colombia")
    config = get_contamination_config_for_consignment(
        main_config["contamination"], consignment
    )
    assert config == {"contamination_unit": "item", "arrangement": "random"}


def test_consignment_with_no_contamination():
    """Check that consignment is not selected based on a rule"""
    main_config = load_configuration_yaml_from_text(CONFIG)
    consignment = simple_consignment(flower="Rosa", origin="Colombia")
    config = get_contamination_config_for_consignment(
        main_config["contamination"], consignment
    )
    assert config is None


@pytest.mark.parametrize(
    "date",
    [
        datetime.date(2022, 9, 29),
        datetime.date(2022, 10, 1),
        datetime.date(2022, 10, 10),
        datetime.date(2022, 10, 15),
    ],
)
def test_consignment_matches_contamination_rule_within_date_interval(date):
    """Check that consignment is selected based on a rule with start and end dates"""
    main_config = load_configuration_yaml_from_text(CONFIG)
    consignment = simple_consignment(flower="Tulipa", origin="Netherlands", date=date)
    config = get_contamination_config_for_consignment(
        main_config["contamination"], consignment
    )
    assert config == {"contamination_unit": "box", "arrangement": "random_box"}


@pytest.mark.parametrize(
    "date",
    [
        datetime.date(2022, 1, 4),
        datetime.date(2022, 9, 28),
        datetime.date(2022, 10, 16),
        datetime.date(2021, 10, 1),
    ],
)
def test_consignment_matches_contamination_rule_outside_of_date_interval(date):
    """Check that consignment is not selected based on a rule with dates"""
    main_config = load_configuration_yaml_from_text(CONFIG)
    consignment = simple_consignment(flower="Tulipa", origin="Netherlands", date=date)
    config = get_contamination_config_for_consignment(
        main_config["contamination"], consignment
    )
    assert config is None


@pytest.mark.parametrize(
    "date",
    [datetime.date(2021, 1, 5), datetime.date(2022, 1, 5), datetime.date(2022, 4, 10)],
)
def test_consignment_matches_contamination_rule_before_end_date(date):
    """Check that consignment is selected based on a rule with end date"""
    main_config = load_configuration_yaml_from_text(CONFIG)
    consignment = simple_consignment(flower="Gerbera", origin="Netherlands", date=date)
    config = get_contamination_config_for_consignment(
        main_config["contamination"], consignment
    )
    assert config == {"arrangement": "random_box"}


@pytest.mark.parametrize(
    "date",
    [
        datetime.date(2022, 8, 20),
        datetime.date(2022, 10, 5),
        datetime.date(2023, 10, 5),
    ],
)
def test_consignment_matches_contamination_rule_after_start_date(date):
    """Check that consignment is selected based on a rule with start date"""
    main_config = load_configuration_yaml_from_text(CONFIG)
    consignment = simple_consignment(flower="Gerbera", origin="Netherlands", date=date)
    config = get_contamination_config_for_consignment(
        main_config["contamination"], consignment
    )
    assert config == {"contamination_unit": "item"}


@pytest.mark.parametrize(
    "date",
    [datetime.date(2022, 4, 11), datetime.date(2022, 5, 5), datetime.date(2022, 8, 19)],
)
def test_consignment_between_two_date_rules(date):
    """Check that consignment is not selected in presence of start and end date rules"""
    main_config = load_configuration_yaml_from_text(CONFIG)
    consignment = simple_consignment(flower="Gerbera", origin="Netherlands", date=date)
    config = get_contamination_config_for_consignment(
        main_config["contamination"], consignment
    )
    assert config is None


def test_contamination_config_for_consignment_no_default():
    """Check that consignment has only its unique config (defaults not requested)"""
    main_config = load_configuration_yaml_from_text(CONFIG)
    consignment = simple_consignment(flower="Liatris", origin="Netherlands")
    config = get_contamination_config_for_consignment(
        main_config["contamination"], consignment
    )
    assert config == {"arrangement": "random_box"}


def test_contamination_config_for_consignment_implicit_default():
    """Check that consignment inherits the top-level config"""
    main_config = load_configuration_yaml_from_text(CONFIG)
    consignment = simple_consignment(flower="Hyacinthus", origin="Israel")
    config = get_contamination_config_for_consignment(
        main_config["contamination"], consignment
    )
    assert config == {"contamination_unit": "item", "arrangement": "random"}


def test_contamination_config_for_consignment_no_default_explicitly():
    """Check that consignment has only its unique config (defaults disabled)"""
    main_config = load_configuration_yaml_from_text(CONFIG)
    consignment = simple_consignment(flower="Rose", origin="Netherlands")
    config = get_contamination_config_for_consignment(
        main_config["contamination"], consignment
    )
    assert config == {"contamination_unit": "box"}


def test_contamination_config_for_consignment_with_default():
    """Check that consignment has has combination of defaults and its own config"""
    main_config = load_configuration_yaml_from_text(CONFIG)
    consignment = simple_consignment(flower="Rose", origin="Mexico")
    config = get_contamination_config_for_consignment(
        main_config["contamination"], consignment
    )
    assert config == {"contamination_unit": "box", "arrangement": "random"}
