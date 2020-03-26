import numpy as np
from datetime import date
import yaml

from pathways.simulation import load_configuration
from pathways.shipments import add_pest_clusters, Box

CONTINUOUS_CONFIG = """\
pest:
  infestation_rate:
    distribution: fixed_value
    value: 0.08
  arrangement: clustered
  clustered:
    max_stems_per_cluster: 10
    distribution: continuous
"""


RANDOM_CONFIG = """\
pest:
  infestation_rate:
    distribution: fixed_value
    value: 0.12
  arrangement: clustered
  clustered:
    max_stems_per_cluster: 10
    distribution: random
    parameters:
    - 10
"""


def load_yaml_text(text):
    """Return configuration dictionary from YAML in a string"""
    if hasattr(yaml, "full_load"):
            return yaml.full_load(text)
    return yaml.load(text)


def get_shipment(num_stems):
    """Get basic shipment with given number of stems all in one box"""
    stems = np.zeros(num_stems, dtype=np.int)
    return dict(
            flower="Rosa",
            arrival_time=date(2018, 2, 15),
            origin="Mexico",
            port="FL Miami Air CBP",
            num_stems=num_stems,
            stems=stems,
            num_boxes=1,
            boxes=[Box(stems)],
        )


def test_continuous_clusters():
    """Test infestation rate of clustered arrangement with continuous distribution"""
    config = load_yaml_text(CONTINUOUS_CONFIG)["pest"]
    num_stems = 100
    shipment = get_shipment(num_stems)
    add_pest_clusters(config, shipment)
    infestation_rate = 0.08
    infested_stems = int(num_stems * infestation_rate)
    assert np.count_nonzero(shipment["stems"]) == infested_stems


def test_random_clusters():
    """Test infestation rate of clustered arrangement with random distribution"""
    config = load_yaml_text(RANDOM_CONFIG)["pest"]
    num_stems = 550
    shipment = get_shipment(num_stems)
    add_pest_clusters(config, shipment)
    infestation_rate = 0.12
    infested_stems = int(num_stems * infestation_rate)
    assert np.count_nonzero(shipment["stems"]) == infested_stems
