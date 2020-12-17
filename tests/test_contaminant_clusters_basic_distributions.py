import numpy as np
from datetime import date

from pathways.simulation import random_seed, load_configuration_yaml_from_text
from pathways.consignments import add_contaminant_clusters, Box

CONTINUOUS_CONFIG = """\
contamination:
  contamination_unit: stems
  contamination_rate:
    distribution: fixed_value
    value: 0.08
  arrangement: clustered
  clustered:
    max_contaminated_units_per_cluster: 1000
    distribution: continuous
"""


RANDOM_CONFIG = """\
contamination:
  contamination_unit: stems
  contamination_rate:
    distribution: fixed_value
    value: 0.12
  arrangement: clustered
  clustered:
    max_contaminated_units_per_cluster: 200
    distribution: random
    random:
      max_cluster_stem_width: 600
"""


def get_consignment(num_stems):
    """Get basic consignment with given number of stems all in one box"""
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
    """Test contamination rate of clustered arrangement with continuous distribution"""
    random_seed(42)
    config = load_configuration_yaml_from_text(CONTINUOUS_CONFIG)["contamination"]
    num_stems = 100
    consignment = get_consignment(num_stems)
    add_contaminant_clusters(config, consignment)
    contamination_rate = 0.08
    contaminated_stems = int(num_stems * contamination_rate)
    assert np.count_nonzero(consignment["stems"]) == contaminated_stems


def test_random_clusters():
    """Test contamination rate of clustered arrangement with random distribution"""
    random_seed(42)
    config = load_configuration_yaml_from_text(RANDOM_CONFIG)["contamination"]
    num_stems = 550
    consignment = get_consignment(num_stems)
    add_contaminant_clusters(config, consignment)
    contamination_rate = 0.12
    contaminated_stems = int(num_stems * contamination_rate)
    assert np.count_nonzero(consignment["stems"]) == contaminated_stems
