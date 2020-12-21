import numpy as np
import datetime

from pathways.simulation import random_seed, load_configuration_yaml_from_text
from pathways.consignments import add_contaminant_clusters, Consignment, Box

CONTINUOUS_CONFIG = """\
contamination:
  contamination_unit: items
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
  contamination_unit: items
  contamination_rate:
    distribution: fixed_value
    value: 0.12
  arrangement: clustered
  clustered:
    max_contaminated_units_per_cluster: 200
    distribution: random
    random:
      max_cluster_item_width: 600
"""


def get_consignment(num_items):
    """Get basic consignment with given number of items all in one box"""
    items = np.zeros(num_items, dtype=np.int)
    return Consignment(
        flower="Rosa",
        date=datetime.date(2018, 2, 15),
        origin="Mexico",
        port="FL Miami Air CBP",
        num_items=num_items,
        items=items,
        num_boxes=1,
        boxes=[Box(items)],
        items_per_box=num_items,
        pathway="air",
    )


def test_continuous_clusters():
    """Test contamination rate of clustered arrangement with continuous distribution"""
    random_seed(42)
    config = load_configuration_yaml_from_text(CONTINUOUS_CONFIG)["contamination"]
    num_items = 100
    consignment = get_consignment(num_items)
    add_contaminant_clusters(config, consignment)
    contamination_rate = 0.08
    contaminated_items = int(num_items * contamination_rate)
    assert np.count_nonzero(consignment.items) == contaminated_items


def test_random_clusters():
    """Test contamination rate of clustered arrangement with random distribution"""
    random_seed(42)
    config = load_configuration_yaml_from_text(RANDOM_CONFIG)["contamination"]
    num_items = 550
    consignment = get_consignment(num_items)
    add_contaminant_clusters(config, consignment)
    contamination_rate = 0.12
    contaminated_items = int(num_items * contamination_rate)
    assert np.count_nonzero(consignment.items) == contaminated_items
