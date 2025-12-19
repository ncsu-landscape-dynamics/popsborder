"""Test functions which output to pandas"""

import pytest

from popsborder.inputs import load_configuration, load_scenario_table
from popsborder.outputs import (
    save_scenario_result_to_pandas,
    save_simulation_result_to_pandas,
)
from popsborder.scenarios import run_scenarios, run_simulation


NUM_ITEMS_IN_CONFIG = 33
NUM_ATTRIBUTES_IN_RESULT = 28


@pytest.fixture(name="config")
def fixture_config(datadir):
    """Get loaded configuration"""
    return load_configuration(datadir / "config.yml")


@pytest.fixture(name="result")
def fixture_executed_simulation_result(config):
    """Get result of a simulation after running it"""
    result = run_simulation(
        config=config, seed=42, num_simulations=2, num_consignments=10
    )
    return result


def test_simulation_to_pandas_default_columns(result, config):
    """Check that one result with config coverts with default column values"""
    df = save_simulation_result_to_pandas(result, config)
    print(df)
    shape = df.shape
    assert len(shape) == 2
    rows, cols = shape
    assert cols == NUM_ITEMS_IN_CONFIG + NUM_ATTRIBUTES_IN_RESULT
    assert rows == 1


def test_simulation_to_pandas_no_config(result):
    """Check that one result without config coverts"""
    df = save_simulation_result_to_pandas(result)
    shape = df.shape
    assert len(shape) == 2
    rows, cols = shape
    assert cols == NUM_ATTRIBUTES_IN_RESULT
    assert rows == 1


def test_simulation_to_pandas_no_config_columns(result, config):
    """Check that result coverts with no config column if columns is an empty list"""
    df = save_simulation_result_to_pandas(result, config, config_columns=[])
    shape = df.shape
    assert len(shape) == 2
    rows, cols = shape
    assert cols == NUM_ATTRIBUTES_IN_RESULT
    assert rows == 1


def test_simulation(result, config):
    """Result converts to data frame with specified columns"""
    config_columns = [
        "consignment/parameter_based/boxes/min",
        "consignment/parameter_based/boxes/max",
        "consignment/items_per_box/default",
        "contamination/contamination_rate/parameters",
    ]
    result_columns = [
        "missing",
        "avg_boxes_opened_completion",
        "avg_boxes_opened_detection",
    ]
    df = save_simulation_result_to_pandas(
        result, config, config_columns=config_columns, result_columns=result_columns
    )
    shape = df.shape
    assert len(shape) == 2
    rows, cols = shape
    assert cols == len(config_columns) + len(result_columns)
    assert rows == 1


def test_scenarios(datadir):
    """Scenario results convert to data frame with specified columns"""
    basic_config = load_configuration(datadir / "config.yml")
    scenario_table = load_scenario_table(datadir / "scenarios_config.csv")
    results = run_scenarios(
        config=basic_config,
        scenario_table=scenario_table,
        seed=42,
        num_simulations=2,
        num_consignments=10,
    )
    assert len(scenario_table) == len(results)
    config_columns = [
        "name",
        "consignment/parameter_based/boxes/min",
        "consignment/parameter_based/boxes/max",
        "consignment/items_per_box/default",
        "contamination/contamination_rate/parameters",
    ]
    result_columns = [
        "missing",
        "avg_boxes_opened_completion",
        "avg_boxes_opened_detection",
    ]

    df = save_scenario_result_to_pandas(
        results, config_columns=config_columns, result_columns=result_columns
    )
    shape = df.shape
    assert len(shape) == 2
    rows, cols = shape
    assert cols == len(config_columns) + len(result_columns)
    assert rows == len(scenario_table)
