from popsborder.scenarios import run_scenarios, load_scenario_table
from popsborder.simulation import load_configuration
from popsborder.outputs import save_scenario_result_to_table


def test_scenarios(datadir, tmp_path):
    """Check that scenarios run from CSV and generate results"""
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


def test_scenarios_with_xlsx(datadir):
    """Check that scenarios can load XLSX and run from it"""
    basic_config = load_configuration(datadir / "config.yml")
    scenario_table = load_scenario_table(datadir / "scenarios_config.xlsx")
    assert scenario_table[0] == {
        "name": "clustered_10",
        "consignment_name": "clustered",
        "inspection_name": "boxes 0.01 hypergeometric random",
        "consignment/parameter_based/boxes/min": 5,
        "consignment/parameter_based/boxes/max": 25,
        "consignment/items_per_box/default": 200,
        "contamination/contamination_rate/parameters": [1, 80],
        "contamination/arrangement": "clustered",
        "inspection/unit": "box",
        "inspection/sample_strategy": "hypergeometric",
        "inspection/proportion/proportion": None,
        "inspection/hypergeometric/detection_level": 0.01,
        "inspection/selection_strategy": "random",
        "inspection/within_box_pct": 1,
        "inspection/cluster/cluster_selection": None,
    }
    assert scenario_table[8] == {
        "name": "clustered_02",
        "consignment_name": "clustered",
        "inspection_name": "boxes 2% random",
        "consignment/parameter_based/boxes/min": 5,
        "consignment/parameter_based/boxes/max": 25,
        "consignment/items_per_box/default": 200,
        "contamination/contamination_rate/parameters": [1, 80],
        "contamination/arrangement": "clustered",
        "inspection/unit": "box",
        "inspection/sample_strategy": "proportion",
        "inspection/proportion/proportion": 0.02,
        "inspection/hypergeometric/detection_level": None,
        "inspection/selection_strategy": "random",
        "inspection/within_box_pct": 1,
        "inspection/cluster/cluster_selection": None,
    }
    results = run_scenarios(
        config=basic_config,
        scenario_table=scenario_table,
        seed=42,
        num_simulations=1,
        num_consignments=5,
    )
    assert len(scenario_table) == len(results)
