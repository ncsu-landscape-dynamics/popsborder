"""Test effectiveness"""

import pytest

from popsborder.inputs import get_validated_effectiveness
from popsborder.inputs import load_configuration_yaml_from_text
from popsborder.simulation import run_simulation
from popsborder.inspections import inspect_item

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


def test_set_effectiveness_no_key():
    """Test config has no effectiveness key"""
    effectiveness = get_validated_effectiveness({"inspection": {}})
    assert effectiveness == 1


@pytest.mark.parametrize("effectiveness", [-1, 1.1, 2.5])
def test_set_effectiveness_out_of_range(effectiveness):
    """Test effectiveness out of range"""
    config = {"inspection": {}}
    config["inspection"]["effectiveness"] = effectiveness
    with pytest.raises(ValueError) as info:
        get_validated_effectiveness(config)
    assert "must be between" in str(info.value)


@pytest.mark.parametrize("effectiveness", [0, 0.5, 1])
def test_set_effectiveness_in_range(effectiveness):
    """Test effectiveness in range"""
    config = {"inspection": {}}
    config["inspection"]["effectiveness"] = effectiveness
    effectiveness = get_validated_effectiveness(config)
    assert effectiveness == effectiveness


def test_item_inspection():
    """Test item inspection"""
    num_contaminated = 0
    for seed in range(10):
        num_contaminated += inspect_item(1, 0.7)
    # Expecting 60% of items to be contaminated with the given seeds.
    assert num_contaminated > 0.6


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

    num_consignments = 100

    @pytest.fixture(scope="class")
    def config(self):
        min_boxes = 30
        max_boxes = 150
        config = load_configuration_yaml_from_text(CONFIG)
        config["consignment"]["parameter_based"]["boxes"]["min"] = min_boxes
        config["consignment"]["parameter_based"]["boxes"]["max"] = max_boxes
        config["inspection"]["effectiveness"] = 0.9
        yield config

    def test_effectiveness_unit_box(self, config):
        """Test effectiveness with inspection method boxes."""
        for seed in range(10):
            result = run_simulation(
                config=config,
                num_simulations=3,
                num_consignments=self.num_consignments,
                seed=seed,
            )
        assert result.pct_contaminant_unreported_if_detection > 0

    def test_effectiveness_unit_items_random(self, config):
        """Test effectiveness with inspection method items with random selection
        strategy.
        """
        config["inspection"]["unit"] = "items"
        for seed in range(10):
            result = run_simulation(
                config=config,
                num_simulations=3,
                num_consignments=self.num_consignments,
                seed=seed,
            )
        assert result.pct_contaminant_unreported_if_detection > 0

    def test_effectiveness_unit_items_cluster(self, config):
        """Test effectiveness with inspection method items with cluster selection
        strategy.
        """
        config["inspection"]["unit"] = "items"
        config["inspection"]["selection_strategy"] = "cluster"
        for seed in range(10):
            result = run_simulation(
                config=config,
                num_simulations=3,
                num_consignments=self.num_consignments,
                seed=seed,
            )
        assert result.pct_contaminant_unreported_if_detection > 0

    def test_effectiveness_none(self, config):
        """Test effectiveness not set in the configuration file."""
        del config["inspection"]["effectiveness"]
        for seed in range(10):
            result = run_simulation(
                config=config,
                num_simulations=3,
                num_consignments=self.num_consignments,
                seed=seed,
            )
        assert result.pct_contaminant_unreported_if_detection > 0
