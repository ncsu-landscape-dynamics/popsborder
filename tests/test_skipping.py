"""Test functions for skipping inspections directly"""

import pytest

from popsborder.consignments import get_consignment_generator
from popsborder.inputs import load_configuration_yaml_from_text
from popsborder.simulation import random_seed
from popsborder.skipping import get_inspection_needed_function, inspect_always

BASE_CONSIGNMENT_CONFIG = """\
consignment:
  generation_method: parameter_based
  items_per_box:
    default: 200
    air:
      default: 200
    maritime:
      default: 200
  parameter_based:
    boxes:
      min: 1
      max: 100
    origins:
      - Netherlands
      - Mexico
      - Israel
    flowers:
      - Hyacinthus
      - Rosa
      - Gerbera
    ports:
      - NY JFK CBP
      - FL Miami Air CBP
      - HI Honolulu CBP
"""

NAIVE_CFRP_CONFIG = """\
release_programs:
  naive_cfrp:
    flowers:
      - Hyacinthus
      - Gerbera
      - Rosa
      - Actinidia
    max_boxes: 10
"""

DOES_NOT_EXIST_PROGRAM_CONFIG = """\
release_programs:
  does_not_exist:
    flowers:
      - Hyacinthus
      - Gerbera
"""


def test_naive_cfrp():
    """Check that naive CFRP program is accepted and gives expected results"""
    consignment_generator = get_consignment_generator(
        load_configuration_yaml_from_text(BASE_CONSIGNMENT_CONFIG)
    )
    is_needed_function = get_inspection_needed_function(
        load_configuration_yaml_from_text(NAIVE_CFRP_CONFIG)
    )
    # The following assumes what is the default returned by the get function,
    # i.e., it relies on its internals, not the interface.
    # pylint: disable=comparison-with-callable
    assert is_needed_function != inspect_always
    for seed in range(10):
        # We run with different, but fixed seeded so we can know which seed fails.
        random_seed(seed)
        consignment = consignment_generator.generate_consignment()
        inspect, program = is_needed_function(consignment, consignment.date)
        assert isinstance(inspect, bool)
        assert program == "naive_cfrp" or program is None


def test_program_rejected():
    """Check that program which does not exist is rejected"""
    with pytest.raises(RuntimeError) as error:
        get_inspection_needed_function(
            load_configuration_yaml_from_text(DOES_NOT_EXIST_PROGRAM_CONFIG)
        )
    assert "does_not_exist" in str(error)
