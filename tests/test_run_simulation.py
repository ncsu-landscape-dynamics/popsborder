import yaml
from pathways.simulation import run_simulation, load_configuration


CONFIG = """\
shipment:
  origins:
  - Netherlands
  - Mexico
  flowers:
  - Hyacinthus
  - Rosa
  - Gerbera
  boxes:
    min: 1
    max: 50
pest:
  infestation_rate:
    distribution: beta
    parameters:
    - 4
    - 60
  arrangement: random_box
  random_box:
    probability: 0.2
    ratio: 0.5
inspection:
  unit: stems
  within_box_pct: 1.0
  sample_strategy: percentage
  percentage:
    proportion: 0.02
    min_boxes: 1
  hypergeometric:
    detection_level: 0.05
    confidence_level: 0.95
    min_boxes: 1
  fixed_n: 10
  selection_strategy: random
  end_strategy: to_completion
ports:
  - NY JFK CBP
  - FL Miami Air CBP
stems_per_box:
  default: 10
"""


def load_yaml_text(text):
    """Return configuration dictionary from YAML in a string"""
    if hasattr(yaml, "full_load"):
        return yaml.full_load(text)
    return yaml.load(text)


def test_simulation_runs():
    for seed in range(10):
        run_simulation(
            config=load_yaml_text(CONFIG),
            num_simulations=1,
            num_shipments=10,
            seed=seed,
        )


def test_gives_result():
    for seed in range(10):
        result = run_simulation(
            config=load_yaml_text(CONFIG),
            num_simulations=1,
            num_shipments=100,
            seed=seed,
        )
        assert 1 * 100 <= result.num_boxes <= 50 * 100
        assert 0 <= result.pct_boxes_opened_completion <= 100
        assert 0 <= result.pct_boxes_opened_detection <= 100
        assert 0 <= result.pct_stems_inspected_completion <= 100
        assert 0 <= result.pct_stems_inspected_detection <= 100
        assert 0 <= result.pct_sample_if_to_detection <= 100
        assert 0 <= result.pct_pest_unreported_if_detection <= 100
