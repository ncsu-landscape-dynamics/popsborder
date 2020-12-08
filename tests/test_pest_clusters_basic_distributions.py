import numpy as np
from datetime import date

from pathways.simulation import random_seed, load_configuration_yaml_from_text
from pathways.shipments import add_pest_clusters, Box

CONTINUOUS_CONFIG = """\
pest:
  infestation_unit: stems
  infestation_rate:
    distribution: fixed_value
    value: 0.08
  arrangement: clustered
  clustered:
    max_infested_stems_per_cluster: 1000
    max_cluster_width: 600
    distribution: continuous
"""


RANDOM_CONFIG = """\
pest:
  infestation_unit: stems
  infestation_rate:
    distribution: fixed_value
    value: 0.12
  arrangement: clustered
  clustered:
    max_infested_stems_per_cluster: 200
    max_cluster_width: 600
    distribution: random
"""


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
    random_seed(42)
    config = load_configuration_yaml_from_text(CONTINUOUS_CONFIG)["pest"]
    num_stems = 100
    shipment = get_shipment(num_stems)
    add_pest_clusters(config, shipment)
    infestation_rate = 0.08
    infested_stems = int(num_stems * infestation_rate)
    assert np.count_nonzero(shipment["stems"]) == infested_stems


def test_random_clusters():
    """Test infestation rate of clustered arrangement with random distribution"""
    random_seed(42)
    config = load_configuration_yaml_from_text(RANDOM_CONFIG)["pest"]
    num_stems = 550
    shipment = get_shipment(num_stems)
    add_pest_clusters(config, shipment)
    infestation_rate = 0.12
    infested_stems = int(num_stems * infestation_rate)
    assert np.count_nonzero(shipment["stems"]) == infested_stems
