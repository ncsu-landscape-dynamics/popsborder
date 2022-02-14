from popsborder.inputs import load_configuration, load_scenario_table
from popsborder.outputs import save_scenario_result_to_pandas
from popsborder.scenarios import run_scenarios


def test_scenarios(datadir, tmp_path):
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
