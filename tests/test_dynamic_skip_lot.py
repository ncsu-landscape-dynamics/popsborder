"""Test dynamic skip lot functionality"""

import pytest

from popsborder.consignments import Consignment, get_consignment_generator
from popsborder.inputs import load_configuration_yaml_from_text
from popsborder.simulation import random_seed
from popsborder.skipping import (
    DynamicComplianceLevelSkipLot,
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
  dynamic_skip_lot:
    name: Test Dynamic Skip Lot
    track:
      - origin
      - commodity
    levels:
      - name: Compliance Level 1
        sampling_fraction: 1
      - name: Compliance Level 2
        sampling_fraction: 0.5
      - name: Compliance Level 3
        sampling_fraction: 0.25
      - name: Compliance Level 4
        sampling_fraction: 0.1
    start_level: Compliance Level 1
    clearance_number: 10
"""


RESTATING_CONFIG = """\
release_programs:
  dynamic_skip_lot:
    name: Test Dynamic Skip Lot
    track:
      - origin
      - commodity
    levels:
      - name: Compliance Level 1
        sampling_fraction: 1
      - name: Compliance Level 2
        sampling_fraction: 0.5
      - name: Compliance Level 3
        sampling_fraction: 0.25
      - name: Compliance Level 4
        sampling_fraction: 0.1
    start_level: Compliance Level 1
    clearance_number: 10
    quick_restate_clearance_number: 5
"""

MONITORING_CONFIG = """\
release_programs:
  dynamic_skip_lot:
    name: Monitoring Level Test
    track:
      - origin
      - commodity
    levels:
      - name: Compliance Level 1
        sampling_fraction: 1
      - name: Compliance Level 2
        sampling_fraction: 0.5
      - name: Compliance Level 3
        sampling_fraction: 0.25
      - name: Compliance Level 4
        sampling_fraction: 0.1
    start_level: Compliance Level 4
    clearance_number: 10
    monitoring_level: Compliance Level 2
"""

DECREASING_CONFIG = """\
release_programs:
  dynamic_skip_lot:
    name: Dynamic Skip Lot with Decreasing Levels
    track:
      - origin
      - commodity
    levels:
      - sampling_fraction: 1
      - sampling_fraction: 0.5
      - sampling_fraction: 0.25
      - sampling_fraction: 0.125
      - sampling_fraction: 0.0625
      - sampling_fraction: 0.03125
      - sampling_fraction: 0.015625
      - sampling_fraction: 0.0078125
      - sampling_fraction: 0.00390625
      - sampling_fraction: 0.001953125
    start_level: 3
    clearance_number: 4
    decrease_levels: 2
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


def test_configuration_loaded():
    """Check that dynamic skip lot program is accepted and gives expected results"""
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
    assert isinstance(is_needed_function, DynamicComplianceLevelSkipLot)
    for seed in range(10):
        # We run with different, but fixed seeded so we can know which seed fails.
        random_seed(seed)
        consignment = consignment_generator.generate_consignment()
        inspect, program = is_needed_function(consignment, consignment.date)
        assert isinstance(inspect, bool)
        # Testing custom name (program name should be always present for skip lot)
        assert program == "Test Dynamic Skip Lot"


def test_sometimes_inspect_in_program():
    """Inspection is requested at least sometimes when consignment is in the program"""
    program = DynamicComplianceLevelSkipLot(
        load_configuration_yaml_from_text(CONFIG)["release_programs"][
            "dynamic_skip_lot"
        ]
    )
    consignment = simple_consignment(flower="Hyacinthus", origin="Netherlands")
    inspected = 0
    for seed in range(10):
        random_seed(seed)
        inspect, program_name = program(consignment, consignment.date)
        inspected += int(inspect)
    assert (
        inspected
    ), "With the given seeds, we expect at least one inspection to happen"


def test_inspect_without_records():
    """Check inspection is always requested

    We set the default level which to always inspect.
    """
    program = DynamicComplianceLevelSkipLot(
        load_configuration_yaml_from_text(CONFIG)["release_programs"][
            "dynamic_skip_lot"
        ]
    )
    consignment = simple_consignment(flower="Rosa", origin="Netherlands")
    for seed in range(10):
        random_seed(seed)
        inspect, program_name = program(consignment, consignment.date)
        assert inspect


def test_inspect_and_record():
    """Check that level changes based on the inspection results"""
    program = DynamicComplianceLevelSkipLot(
        load_configuration_yaml_from_text(CONFIG)["release_programs"][
            "dynamic_skip_lot"
        ]
    )
    consignment = simple_consignment(flower="Rosa", origin="Netherlands")

    # First, we simulate compliant consignments.
    for seed in range(10):
        random_seed(seed)
        assert program.compliance_level_for_consignment(consignment) == 1, seed
        inspect, program_name = program(consignment, consignment.date)
        assert inspect
        program.add_inspection_result(consignment, inspect, result=True)

    # This is deterministic with the sampling fraction 1.
    assert program.compliance_level_for_consignment(consignment) == 2

    # Now, we simulate more compliant consignments, but not all will be inspected.
    inspected = 0
    not_inspected = 0
    for seed in range(20):
        random_seed(seed)
        inspect, program_name = program(consignment, consignment.date)
        inspected += int(inspect)
        not_inspected += int(not inspect)
        program.add_inspection_result(consignment, inspect, result=True)

    assert (
        inspected
    ), "With the given seeds, we expect at least one inspection to happen"
    assert (
        not_inspected
    ), "With the given seeds, we expect at least one inspection to be skipped"
    assert (
        program.compliance_level_for_consignment(consignment) == 3
    ), "With the given the seeds, we should move up a level"

    # Now, we simulate a non-compliant consignment.
    inspect, program_name = program(consignment, consignment.date)
    program.add_inspection_result(consignment, inspect, result=False)
    # Compliance level should drop to the default.
    assert program.compliance_level_for_consignment(consignment) == 1

    # More non-compliant consignments should keep the compliance level the same.
    for seed in range(10):
        random_seed(seed)
        inspect, program_name = program(consignment, consignment.date)
        assert inspect
        program.add_inspection_result(consignment, inspect, result=False)
        assert program.compliance_level_for_consignment(consignment) == 1

    # Now, we simulate compliant consignments again.
    for seed in range(10):
        random_seed(seed)
        assert program.compliance_level_for_consignment(consignment) == 1
        inspect, program_name = program(consignment, consignment.date)
        assert inspect
        program.add_inspection_result(consignment, inspect, result=True)

    # This is deterministic with the sampling fraction 1.
    assert program.compliance_level_for_consignment(consignment) == 2

    # Adding one compliant consignment should not change the compliance level.
    inspect, program_name = program(consignment, consignment.date)
    assert inspect
    program.add_inspection_result(consignment, inspect, result=True)
    assert program.compliance_level_for_consignment(consignment) == 2

    # Now, we simulate many compliant consignments.
    for seed in range(60):
        random_seed(seed)
        inspect, program_name = program(consignment, consignment.date)
        program.add_inspection_result(consignment, inspect, result=True)
    assert (
        program.compliance_level_for_consignment(consignment) == 4
    ), "With the given seeds, compliance level should reach the maximum level"


def test_inspect_and_record_quick_restating():
    """Check that quick restating works"""
    program = DynamicComplianceLevelSkipLot(
        load_configuration_yaml_from_text(RESTATING_CONFIG)["release_programs"][
            "dynamic_skip_lot"
        ]
    )
    consignment = simple_consignment(flower="Rosa", origin="Netherlands")

    # Now, we simulate compliant consignments, but not all will be inspected.
    inspected = 0
    not_inspected = 0
    for seed in range(40):
        random_seed(seed)
        inspect, program_name = program(consignment, consignment.date)
        inspected += int(inspect)
        not_inspected += int(not inspect)
        program.add_inspection_result(consignment, inspect, result=True)

    assert (
        inspected
    ), "With the given seeds, we expect at least one inspection to happen"
    assert (
        not_inspected
    ), "With the given seeds, we expect at least one inspection to be skipped"
    assert (
        program.compliance_level_for_consignment(consignment) == 3
    ), "With the given the seeds, we should move up a level"

    # Now, we simulate a non-compliant consignment.
    inspect, program_name = program(consignment, consignment.date)
    program.add_inspection_result(consignment, inspect, result=False)
    # Compliance level should drop to the default.
    assert program.compliance_level_for_consignment(consignment) == 1

    for seed in range(5):
        random_seed(seed)
        inspect, program_name = program(consignment, consignment.date)
        program.add_inspection_result(consignment, inspect, result=True)
    # Previous compliance level should be restated.
    assert program.compliance_level_for_consignment(consignment) == 3


def test_inspect_and_record_monitoring():
    """Check that monitoring works"""
    program = DynamicComplianceLevelSkipLot(
        load_configuration_yaml_from_text(MONITORING_CONFIG)["release_programs"][
            "dynamic_skip_lot"
        ]
    )
    consignment = simple_consignment(flower="Rosa", origin="Netherlands")

    # Now, we simulate compliant consignments, but not all will be inspected.
    inspected = 0
    not_inspected = 0
    for seed in range(5):
        random_seed(seed)
        inspect, program_name = program(consignment, consignment.date)
        inspected += int(inspect)
        not_inspected += int(not inspect)
        program.add_inspection_result(consignment, inspect, result=True)

    assert (
        not_inspected
    ), "With the given seeds, we expect at least one inspection to be skipped"
    assert (
        program.compliance_level_for_consignment(consignment) == 4
    ), "Starting level is the maximum"

    # Now, we simulate a non-compliant consignment.
    inspect, program_name = program(consignment, consignment.date)
    program.add_inspection_result(consignment, inspect, result=False)
    # Compliance level should drop to the monitoring level.
    assert program.compliance_level_for_consignment(consignment) == 2

    for seed in range(20):
        random_seed(seed)
        inspect, program_name = program(consignment, consignment.date)
        program.add_inspection_result(consignment, inspect, result=True)
    # Previous compliance level should be restated with the given seeds.
    assert program.compliance_level_for_consignment(consignment) == 3


def test_inspect_and_record_decreasing_levels():
    """Check that decreasing levels work"""
    program = DynamicComplianceLevelSkipLot(
        load_configuration_yaml_from_text(DECREASING_CONFIG)["release_programs"][
            "dynamic_skip_lot"
        ]
    )
    consignment = simple_consignment(flower="Rosa", origin="Netherlands")

    # Now, we simulate compliant consignments, but not all will be inspected.
    inspected = 0
    not_inspected = 0
    for seed in range(40):
        random_seed(seed)
        inspect, program_name = program(consignment, consignment.date)
        inspected += int(inspect)
        not_inspected += int(not inspect)
        program.add_inspection_result(consignment, inspect, result=True)

    assert (
        inspected
    ), "With the given seeds, we expect at least one inspection to happen"
    assert (
        not_inspected
    ), "With the given seeds, we expect at least one inspection to be skipped"
    assert (
        program.compliance_level_for_consignment(consignment) == 5
    ), "With the given the seeds, we should move up a level"

    # Now, we simulate a non-compliant consignment.
    inspect, program_name = program(consignment, consignment.date)
    program.add_inspection_result(consignment, inspect, result=False)
    # Compliance level should drop down by decreasing_levels.
    assert program.compliance_level_for_consignment(consignment) == 3

    # Now, we simulate a non-compliant consignment.
    inspect, program_name = program(consignment, consignment.date)
    program.add_inspection_result(consignment, inspect, result=False)
    # Compliance level should drop again.
    assert program.compliance_level_for_consignment(consignment) == 1

    # Now, we simulate a non-compliant consignment.
    inspect, program_name = program(consignment, consignment.date)
    program.add_inspection_result(consignment, inspect, result=False)
    # Compliance level should not drop more than minimum.
    assert program.compliance_level_for_consignment(consignment) == 1

    for seed in range(5):
        random_seed(seed)
        inspect, program_name = program(consignment, consignment.date)
        program.add_inspection_result(consignment, inspect, result=True)
    # Increased level.
    assert program.compliance_level_for_consignment(consignment) == 2

    # 2,100 gets us to level 10, but we test overreaching the max level.
    for seed in range(3_000):
        random_seed(seed)
        inspect, program_name = program(consignment, consignment.date)
        program.add_inspection_result(consignment, inspect, result=True)
    # Reaching maximum level.
    assert program.compliance_level_for_consignment(consignment) == 10


@pytest.mark.parametrize(["level", "fraction"], [(1, 1), (2, 0.5), (3, 0.25), (4, 0.1)])
def test_fraction(level, fraction):
    """Correct fraction is returned for a level"""
    program = DynamicComplianceLevelSkipLot(
        load_configuration_yaml_from_text(CONFIG)["release_programs"][
            "dynamic_skip_lot"
        ]
    )
    assert program.sampling_fraction_for_level(level) == fraction


@pytest.mark.parametrize(
    "consignment",
    [
        simple_consignment(flower="Hyacinthus", origin="Netherlands"),
        simple_consignment(flower="Gerbera", origin="Mexico"),
        simple_consignment(flower="Rosa", origin="Israel"),
    ],
)
def test_start_level(consignment):
    """All consignments start with the default compliance level"""
    program = DynamicComplianceLevelSkipLot(
        load_configuration_yaml_from_text(CONFIG)["release_programs"][
            "dynamic_skip_lot"
        ]
    )
    level = 1
    assert program.compliance_level_for_consignment(consignment) == level


def test_computed_key_comparisons():
    """All consignments start with the default compliance level"""
    program = DynamicComplianceLevelSkipLot(
        load_configuration_yaml_from_text(CONFIG)["release_programs"][
            "dynamic_skip_lot"
        ]
    )
    consignment_1 = simple_consignment(flower="Hyacinthus", origin="Netherlands")
    consignment_2 = simple_consignment(flower="Gerbera", origin="Mexico")
    consignment_3 = simple_consignment(flower="Rosa", origin="Israel")

    # Consignment keys should be different.
    assert program.compute_record_key_for_consignment(
        consignment_1
    ) != program.compute_record_key_for_consignment(consignment_2)
    assert program.compute_record_key_for_consignment(
        consignment_1
    ) != program.compute_record_key_for_consignment(consignment_3)
    assert program.compute_record_key_for_consignment(
        consignment_2
    ) != program.compute_record_key_for_consignment(consignment_3)

    # Consignment keys for different consignment with the same content
    # should be the same.
    consignment_1b = simple_consignment(flower="Hyacinthus", origin="Netherlands")
    consignment_2b = simple_consignment(flower="Gerbera", origin="Mexico")
    consignment_3b = simple_consignment(flower="Rosa", origin="Israel")
    assert program.compute_record_key_for_consignment(
        consignment_1
    ) == program.compute_record_key_for_consignment(consignment_1b)
    assert program.compute_record_key_for_consignment(
        consignment_2
    ) == program.compute_record_key_for_consignment(consignment_2b)
    assert program.compute_record_key_for_consignment(
        consignment_3
    ) == program.compute_record_key_for_consignment(consignment_3b)
