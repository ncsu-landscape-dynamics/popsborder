from pathways.scenarios import run_scenarios, load_scenario_table
from pathways.simulation import load_configuration


def test_scenarios(datadir):
    basic_config = load_configuration(datadir / "config.yml")
    scenario_table = load_scenario_table(datadir / "scenarios_config.csv")
    results = run_scenarios(
        config=basic_config,
        scenario_table=scenario_table,
        seed=42,
        num_simulations=2,
        num_shipments=50,
    )
    assert len(scenario_table) == len(results)
