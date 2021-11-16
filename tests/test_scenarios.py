from popsborder.scenarios import run_scenarios, load_scenario_table
from popsborder.simulation import load_configuration
from popsborder.outputs import save_scenario_result_to_table


def test_scenarios(datadir, tmp_path):
    basic_config = load_configuration(datadir / "config.yml")
    scenario_table = load_scenario_table(datadir / "scenarios_config.csv")
    results = run_scenarios(
        config=basic_config,
        scenario_table=scenario_table,
        seed=42,
        num_simulations=2,
        num_consignments=50,
    )
    assert len(scenario_table) == len(results)
    save_scenario_result_to_table(
        tmp_path / "results.csv",
        results,
        config_columns=[
            "name",
            "consignment/parameter_based/boxes/min",
            "consignment/parameter_based/boxes/max",
            "consignment/items_per_box/default",
            "contamination/contamination_rate/parameters",
        ],
        result_columns=[
            "missing",
            "avg_boxes_opened_completion",
            "avg_boxes_opened_detection",
        ],
    )
