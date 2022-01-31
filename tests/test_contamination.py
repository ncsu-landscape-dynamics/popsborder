"""Test configuration loading functions"""

from popsborder.consignments import Consignment
from popsborder.inputs import load_configuration_yaml_from_text
from popsborder.contamination import (
    get_contamination_config_for_consignment,
)

CONFIG = """\
contamination:
  consignments:
    - commodity: Liatris
      origin: Netherlands
      contamination:
        arrangement: random_box
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


def simple_consignment(flower, origin):
    """Get consignment with some default values"""
    return Consignment(
        flower=flower,
        num_items=0,
        items=0,
        items_per_box=0,
        num_boxes=0,
        date=None,
        boxes=[],
        pathway="airport",
        port="FL Miami Air CBP",
        origin=origin,
    )


def test_consignment_matches_contamination_rule():
    main_config = load_configuration_yaml_from_text(CONFIG)
    consignment = simple_consignment(flower="Sedum", origin="Colombia")
    config = get_contamination_config_for_consignment(
        main_config["contamination"], consignment
    )
    assert config == {"contamination_unit": "item", "arrangement": "random"}


def test_consignment_with_no_contamination():
    main_config = load_configuration_yaml_from_text(CONFIG)
    consignment = simple_consignment(flower="Rosa", origin="Colombia")
    config = get_contamination_config_for_consignment(
        main_config["contamination"], consignment
    )
    assert config is None


def test_contamination_config_for_consignment_no_default():
    main_config = load_configuration_yaml_from_text(CONFIG)
    consignment = simple_consignment(flower="Liatris", origin="Netherlands")
    config = get_contamination_config_for_consignment(
        main_config["contamination"], consignment
    )
    assert config == {"arrangement": "random_box"}


def test_contamination_config_for_consignment_implicit_default():
    main_config = load_configuration_yaml_from_text(CONFIG)
    consignment = simple_consignment(flower="Hyacinthus", origin="Israel")
    config = get_contamination_config_for_consignment(
        main_config["contamination"], consignment
    )
    assert config == {"contamination_unit": "item", "arrangement": "random"}


def test_contamination_config_for_consignment_no_default_explicitly():
    main_config = load_configuration_yaml_from_text(CONFIG)
    consignment = simple_consignment(flower="Rose", origin="Netherlands")
    config = get_contamination_config_for_consignment(
        main_config["contamination"], consignment
    )
    assert config == {"contamination_unit": "box"}


def test_contamination_config_for_consignment_with_default():
    main_config = load_configuration_yaml_from_text(CONFIG)
    consignment = simple_consignment(flower="Rose", origin="Mexico")
    config = get_contamination_config_for_consignment(
        main_config["contamination"], consignment
    )
    assert config == {"contamination_unit": "box", "arrangement": "random"}
