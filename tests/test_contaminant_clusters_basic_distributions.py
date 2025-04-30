import datetime

import numpy as np
import pytest

from popsborder.consignments import Box, Consignment
from popsborder.contamination import add_contaminant_clusters, num_items_to_contaminate
from popsborder.inputs import load_configuration_yaml_from_text
from popsborder.simulation import random_seed

CONTINUOUS_CONFIG = """\
contamination:
  contamination_unit: items
  contamination_rate:
    distribution: fixed_value
    value: 0.08
  arrangement: clustered
  clustered:
    contaminated_units_per_cluster: 1000
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
    contaminated_units_per_cluster: 200
    distribution: random
    random:
      cluster_item_width: 600
"""


def get_consignment(num_items):
    """Get basic consignment with given number of items all in one box"""
    items = np.zeros(num_items, dtype=int)
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


@pytest.mark.parametrize("num_items", range(95, 105))
@pytest.mark.parametrize("contamination_rate", [0.0, 0.1, 0.2, 0.5, 0.8, 1.0])
@pytest.mark.parametrize("clustering", [0.0, 0.2, 0.5, 0.8, 1.0])
def test_add_contaminant_clusters_to_items_with_subset_clustering(
    num_items, contamination_rate, clustering
):
    """Test contaminant clusters with single-parameter subset clustering"""
    config_yaml = f"""
    contamination:
      contamination_rate:
        distribution: fixed_value
        value: {contamination_rate}
      contamination_unit: item
      arrangement: clustered
      clustered:
        distribution: single
        value: {clustering}
    """
    config = load_configuration_yaml_from_text(config_yaml)["contamination"]
    consignment = get_consignment(num_items)
    add_contaminant_clusters(config, consignment)
    # contaminated_items = int(num_items * contamination_rate)
    contaminated_items = num_items_to_contaminate(
        config["contamination_rate"], consignment.num_items
    )
    assert np.count_nonzero(consignment.items) == contaminated_items
