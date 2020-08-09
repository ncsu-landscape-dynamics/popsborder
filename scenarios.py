from pathways.scenarios import run_scenarios, load_scenario_table
from pathways.simulation import load_configuration
from pathways.outputs import save_scenario_result_to_table


def main():
    basic_config = load_configuration("tests/test_scenarios/config.yml")
    scenario_table = load_scenario_table("tests/test_scenarios/scenarios_config_5.csv")
    results = run_scenarios(
        config=basic_config,
        scenario_table=scenario_table,
        seed=42,
        num_simulations=10,
        num_shipments=1000,
    )
    assert len(scenario_table) == len(results)
    save_scenario_result_to_table(
        "results_5.csv",
        results,
        config_columns=[
            "name",
            "shipment/boxes/min",
            "shipment/boxes/max",
            "stems_per_box/default",
            "pest/infestation_rate/parameters",
            "pest/arrangement",
            "inspection/unit",
            "inspection/sample_strategy",
            "inspection/percentage/proportion",
            "inspection/hypergeometric/detection_level",
            "inspection/selection_strategy",
            "inspection/within_box_pct",
            "inspection/hierarchical/outer",
        ],
        result_columns=[
            "missing",
            "true_infestation_rate",
            "max_missed_infestation_rate",
            "avg_missed_infestation_rate",
            "max_intercepted_infestation_rate",
            "avg_intercepted_infestation_rate",
            "avg_boxes_opened_completion",
            "avg_boxes_opened_detection",
            "avg_stems_inspected_completion",
            "avg_stems_inspected_detection",
            "pct_sample_if_to_detection",
            "pct_pest_unreported_if_detection",
        ],
    )


if __name__ == "__main__":
    main()
