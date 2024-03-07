"""Test effectiveness"""

import types

import pytest

from popsborder.effectiveness import validate_effectiveness, Inspector
from popsborder.inputs import load_configuration_yaml_from_text
from popsborder.simulation import run_simulation

CONFIG = """\
consignment:
  generation_method: parameter_based
  parameter_based:
    origins:
    - Netherlands
    - Mexico
    flowers:
    - Hyacinthus
    - Rosa
    - Gerbera
    ports:
    - NY JFK CBP
    - FL Miami Air CBP
    boxes:
      min: 1
      max: 100
  items_per_box:
    default: 100
contamination:
  contamination_unit: items
  contamination_rate:
    distribution: beta
    parameters:
    - 4
    - 60
  arrangement: random_box
  random_box:
    probability: 0.2
    ratio: 0.5
inspection:
  unit: boxes
  within_box_proportion: 1
  sample_strategy: proportion
  tolerance_level: 0
  min_boxes: 0
  proportion:
    value: 0.02
  hypergeometric:
    detection_level: 0.05
    confidence_level: 0.95
  fixed_n: 10
  selection_strategy: random
  cluster:
    cluster_selection: random
    interval: 3
"""

ret = types.SimpleNamespace(
    inspected_item_indexes=[],
    boxes_opened_completion=0,
    boxes_opened_detection=0,
    items_inspected_completion=0,
    items_inspected_detection=0,
    contaminated_items_completion=0,
    contaminated_items_detection=0,
    contaminated_items_missed=0
)

config = load_configuration_yaml_from_text(CONFIG)
num_consignments = 100
detailed = False


def test_set_effectiveness_no_key():
    """Test config has no effectiveness key"""
    effectiveness = validate_effectiveness(config)
    assert effectiveness is None


def test_set_effectiveness_out_of_range():
    """Test effectiveness out of range"""
    for val in [-1, 1.1, 2.5]:
        config["inspection"]["effectiveness"] = val
        effectiveness = validate_effectiveness(config)
        assert effectiveness is None


def test_set_effectiveness_in_range():
    """Test effectiveness in range"""
    for val in [0, 0.5, 1]:
        config["inspection"]["effectiveness"] = val
        effectiveness = validate_effectiveness(config)
        assert effectiveness == val


class TestInspector:
    """Test Inspector class"""

    @pytest.fixture()
    def setup(self):
        effectiveness = 0.9
        inspector = Inspector(effectiveness)
        yield inspector

    def test_generate_false_negative_item(self, setup):
        """Test generate_false_negative_item method"""
        item = setup.generate_false_negative_item()
        assert item in [0, 1]

    def test_possibly_good_work(self, setup):
        """Test effectiveness of inspector's work. 90% of the time, the inspector
        detects the contaminated item. The inspector misses the contaminated item
        """
        count = 0
        for _ in range(10):
            inspection = setup.possibly_good_work()
            assert inspection in [True, False]
            if not inspection:
                count += 1
        print(f"Missed inspection: {count}")
        assert count <= 1


class TestEffectiveness:
    """There are two types of inspection methodologies:
    1) counting contaminated items in the first contaminated box
        * the unit is a boxes or items with a "cluster" selection strategy
        * inspection_effectiveness is calculated. It should be close enough to
        effectiveness in the configuration file.
    2) counting the first contaminated item.
        * the unit is item with other than "cluster" selection strategy
        * inspection_effectiveness is 0 since only count first contaminated item. For
        this, the number of items missed before detection is calculated. Simulation
        result is average of how many missed contaminated items before first
        contaminated item is detected.
    """

    @pytest.fixture()
    def setup(self):
        min_boxes = 30
        max_boxes = 150
        # config = load_configuration_yaml_from_text(CONFIG)
        config["consignment"]["parameter_based"]["boxes"]["min"] = min_boxes
        config["consignment"]["parameter_based"]["boxes"]["max"] = max_boxes
        config["inspection"]["effectiveness"] = 0.9
        yield config

    def test_effectiveness_unit_box(self, setup):
        """Test effectiveness with inspection method boxes."""
        for seed in range(10):
            result = run_simulation(
                config=config, num_simulations=3, num_consignments=100, seed=seed
            )
            print(result.inspection_effectiveness)
            pct_effectiveness = (result.inspection_effectiveness + 0.5) / 100
            assert 0 <= result.inspection_effectiveness <= 100
            assert 0.88 <= pct_effectiveness <= 0.92

    def test_effectiveness_unit_items_random(self, setup):
        """Test effectiveness with inspection method items with random selection
        strategy.
        """
        config["inspection"]["unit"] = "items"
        for seed in range(10):
            result = run_simulation(
                config=config, num_simulations=3, num_consignments=100, seed=seed
            )
            print(result.avg_items_missed_bf_detection)
            assert result.inspection_effectiveness == 0
            assert result.avg_items_missed_bf_detection >= 0

    def test_effectiveness_unit_items_cluster(self, setup):
        """Test effectiveness with inspection method items with cluster selection
        strategy.
        """
        config["inspection"]["unit"] = "items"
        config["inspection"]["selection_strategy"] = "cluster"
        for seed in range(10):
            result = run_simulation(
                config=config, num_simulations=3, num_consignments=100, seed=seed
            )
            pct_effectiveness = (result.inspection_effectiveness + 0.5) / 100
            assert 0 <= result.inspection_effectiveness <= 100
            assert 0.88 <= pct_effectiveness <= 0.92

    def test_effectiveness_none(self, setup):
        """Test effectiveness not set in the configuration file."""
        del config["inspection"]["effectiveness"]
        for seed in range(10):
            result = run_simulation(
                config=config, num_simulations=3, num_consignments=100, seed=seed
            )
            assert result.inspection_effectiveness == 100
            assert result.avg_items_missed_bf_detection == 0
