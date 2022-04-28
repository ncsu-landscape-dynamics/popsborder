"""Test fixed skip lot functionality"""

import pytest

from popsborder.consignments import Consignment, get_consignment_generator
from popsborder.inputs import (
    load_configuration_yaml_from_text,
    load_skip_lot_consignment_records,
)
from popsborder.simulation import random_seed
from popsborder.skipping import (
    FixedComplianceLevelSkipLot,
    get_inspection_needed_function,
    inspect_always,
)

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

CONFIG = """\
release_programs:
  fixed_skip_lot:
    name: Skip Lot
    track:
      - origin
      - commodity
    levels:
      - name: 1
        sampling_fraction: 1
      - name: 2
        sampling_fraction: 0.5
      - name: 3
        sampling_fraction: 0
    default_level: 1
    consignment_records:
      - origin: Netherlands
        commodity: Hyacinthus
        compliance_level: 2
      - origin: Mexico
        commodity: Gerbera
        compliance_level: 3
"""

RECORDS_CSV_TEXT = """\
origin,commodity,compliance_level
Netherlands,Hyacinthus,2
Mexico,Gerbera,3
"""


def simple_consignment(flower, origin, date=None, port="FL Miami Air CBP"):
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
        port=port,
        origin=origin,
    )


def test_fixed_skip_lot():
    """Check that fixed skip lot program is accepted and gives expected results"""
    consignment_generator = get_consignment_generator(
        load_configuration_yaml_from_text(BASE_CONSIGNMENT_CONFIG)
    )
    is_needed_function = get_inspection_needed_function(
        load_configuration_yaml_from_text(CONFIG)
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
        # Testing custom name (program name should be always present for skip lot)
        assert program == "Skip Lot"


def test_load_consignment_records(tmp_path):
    """Check that schedule loads from a CSV file with custom date format"""
    file = tmp_path / "records.csv"
    file.write_text(RECORDS_CSV_TEXT)
    records = load_skip_lot_consignment_records(
        file, tracked_properties=["origin", "commodity"]
    )
    assert records == {("Netherlands", "Hyacinthus"): 2, ("Mexico", "Gerbera"): 3}


def test_sometimes_inspect_in_program():
    """Inspection is requested at least sometimes when consignment is in the program"""
    program = FixedComplianceLevelSkipLot(
        load_configuration_yaml_from_text(CONFIG)["release_programs"]["fixed_skip_lot"]
    )
    consignment = simple_consignment(flower="Hyacinthus", origin="Netherlands")
    inspected = 0
    for seed in range(10):
        random_seed(seed)
        inspect, program_name = program(consignment, consignment.date)
        inspected += int(inspect)
        assert program_name == "Skip Lot"
    assert inspected, "With the seeds, we expect at least one inspection to happen"


def test_never_inspect_in_program():
    """Inspection is not requested when consignment is in a zero inspections level"""
    program = FixedComplianceLevelSkipLot(
        load_configuration_yaml_from_text(CONFIG)["release_programs"]["fixed_skip_lot"]
    )
    consignment = simple_consignment(flower="Gerbera", origin="Mexico")
    for seed in range(10):
        random_seed(seed)
        inspect, program_name = program(consignment, consignment.date)
        assert (
            not inspect
        ), "We disabled inspections completely for this inspection level"
        assert program_name == "Skip Lot"


def test_inspect_not_in_program():
    """Check inspection is requested when consignment is not in the program"""
    program = FixedComplianceLevelSkipLot(
        load_configuration_yaml_from_text(CONFIG)["release_programs"]["fixed_skip_lot"]
    )
    consignment = simple_consignment(flower="Rosa", origin="Netherlands")
    for seed in range(10):
        random_seed(seed)
        inspect, program_name = program(consignment, consignment.date)
        assert inspect
        assert program_name == "Skip Lot"


@pytest.mark.parametrize(["level", "fraction"], [(1, 1), (2, 0.5), (3, 0)])
def test_fraction(level, fraction):
    """Correct fraction is returned for a level"""
    program = FixedComplianceLevelSkipLot(
        load_configuration_yaml_from_text(CONFIG)["release_programs"]["fixed_skip_lot"]
    )
    assert program.sampling_fraction_for_level(level) == fraction


@pytest.mark.parametrize(
    ["consignment", "level"],
    [
        (simple_consignment(flower="Hyacinthus", origin="Netherlands"), 2),
        (simple_consignment(flower="Gerbera", origin="Mexico"), 3),
        (simple_consignment(flower="Rosa", origin="Israel"), 1),
    ],
)
def test_level(consignment, level):
    """Correct level is returned for a shipment"""
    program = FixedComplianceLevelSkipLot(
        load_configuration_yaml_from_text(CONFIG)["release_programs"]["fixed_skip_lot"]
    )
    assert program.compliance_level_for_consignment(consignment) == level
