"""Test functions for skipping inspections directly"""

import datetime

from popsborder.consignments import Consignment, get_consignment_generator
from popsborder.inputs import load_cfrp_schedule, load_configuration_yaml_from_text
from popsborder.simulation import random_seed
from popsborder.skipping import (
    CutFlowerReleaseProgram,
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

CFRP_CONFIG = """\
release_programs:
  cfrp:
    name: CFRP
    schedule:
      file_name: {schedule_file}
      date_format: "%Y_%m_%d"
"""

SCHEDULE_CSV_TEXT = """\
"","DATE","COMBO","COMMODITY","ORIGIN_NM"
"1","2014_10_01","Liatris_Ecuador","Liatris","Ecuador"
"8","2014_10_01","Sedum_Netherlands","Sedum","Netherlands"
"9","2014_10_02","Bouquet, Rose_Colombia","Bouquet, Rose","Colombia"
"25","2014_10_02","Bouquet, Rose_Ecuador","Bouquet, Rose","Ecuador"
"26","2014_10_02","Bouquet, Rose_Ecuador","Bouquet, Rose","Ecuador"
"185","2014_10_15","Liatris_Ecuador","Liatris","Ecuador"
"""

SCHEDULE = {
    ("Liatris", "Dominican Republic"): [datetime.date(2017, 1, 1)],
    ("Liatris", "Ecuador"): [datetime.date(2017, 1, 1)],
    ("Rosa", "Colombia"): [datetime.date(2017, 1, 2)],
    ("Lilium", "Colombia"): [datetime.date(2017, 1, 3)],
    ("Lilium", "Costa Rica"): [datetime.date(2017, 1, 3)],
}


def simple_consignment(flower, origin, date):
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


def test_cfrp(tmp_path):
    """Check that CFRP program is accepted and gives expected results"""
    schedule_file = tmp_path / "schedule_file.csv"
    schedule_file.write_text(SCHEDULE_CSV_TEXT)
    consignment_generator = get_consignment_generator(
        load_configuration_yaml_from_text(BASE_CONSIGNMENT_CONFIG)
    )
    is_needed_function = get_inspection_needed_function(
        load_configuration_yaml_from_text(
            CFRP_CONFIG.format(schedule_file=schedule_file)
        )
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
        # Testing custom name
        assert program == "CFRP" or program is None


def test_load_cfrp_schedule(tmp_path):
    """Check that schedule loads from a CSV file with custom date format"""
    schedule_file = tmp_path / "schedule_file.csv"
    schedule_file.write_text(SCHEDULE_CSV_TEXT)
    schedule = load_cfrp_schedule(schedule_file, date_format="%Y_%m_%d")

    # Keys were loaded.
    assert ("Liatris", "Ecuador") in schedule
    assert ("Sedum", "Netherlands") in schedule

    # Right number values was loaded.
    assert len(schedule[("Liatris", "Ecuador")]) == 2
    assert len(schedule[("Bouquet, Rose", "Ecuador")]) == 1

    # Values were loaded.
    assert schedule[("Liatris", "Ecuador")] == {
        datetime.date(2014, 10, 1),
        datetime.date(2014, 10, 15),
    }


def test_cfrp_inspect_in_program():
    """Check inspection is requested for flower of the day"""
    cfrp = CutFlowerReleaseProgram({}, schedule=SCHEDULE)
    consignment = simple_consignment(
        flower="Liatris", origin="Ecuador", date=datetime.date(2017, 1, 1)
    )
    inspect, program_name = cfrp(consignment, consignment.date)
    assert inspect
    assert program_name == "cfrp"


def test_cfrp_not_inspect_in_program():
    """Check inspection is not requested for flower-country combo on another day"""
    cfrp = CutFlowerReleaseProgram({}, schedule=SCHEDULE)
    consignment = simple_consignment(
        flower="Liatris", origin="Ecuador", date=datetime.date(2017, 1, 2)
    )
    inspect, program_name = cfrp(consignment, consignment.date)
    assert not inspect
    assert program_name == "cfrp"


def test_cfrp_inspect_flower_not_in_program():
    """Check inspection is requested for flower which is not in the program"""
    cfrp = CutFlowerReleaseProgram({}, schedule=SCHEDULE)
    consignment = simple_consignment(
        flower="Zantedeschia", origin="Ecuador", date=datetime.date(2017, 1, 1)
    )
    inspect, program_name = cfrp(consignment, consignment.date)
    assert inspect
    assert program_name is None


def test_cfrp_inspect_country_not_in_program():
    """Check inspection is requested for country which is not in the program"""
    cfrp = CutFlowerReleaseProgram({}, schedule=SCHEDULE)
    consignment = simple_consignment(
        flower="Liatris", origin="Mexico", date=datetime.date(2017, 1, 1)
    )
    inspect, program_name = cfrp(consignment, consignment.date)
    assert inspect
    assert program_name is None


def test_cfrp_inspect_flower_and_country_not_in_program():
    """Check inspection is requested for out-of-program flower-country combo"""
    cfrp = CutFlowerReleaseProgram({}, schedule=SCHEDULE)
    consignment = simple_consignment(
        flower="Zantedeschia", origin="Mexico", date=datetime.date(2017, 1, 1)
    )
    inspect, program_name = cfrp(consignment, consignment.date)
    assert inspect
    assert program_name is None
