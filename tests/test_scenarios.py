
from pathways.scenarios import run_scenarios
from pathways.simulation import load_configuration


def test_scenarios(datadir):
    basic_config = load_configuration(datadir / "config.yml")
    scenario_table = [
      dict(name="Scenario 1", infestation_rate=0.5),
    ]
    results = run_scenarios(basic_config, scenario_table, 42, 2, 100)
    assert len(scenario_table) == len(results)
