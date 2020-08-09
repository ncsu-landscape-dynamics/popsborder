import os
import yaml
import math
import random
import shipments
import inspections
from simulation import random_seed
import numpy as np

# sys.path.append('C:\\Users\\Owner\\Documents\\GitHub\\pathways-simulation\\pathways')

parameters = dict(
    origins=[
        "Netherlands",
        "Mexico",
        "Israel",
        "Japan",
        "New Zealand",
        "India",
        "Tanzania",
    ],
    flowers=[
        "Hyacinthus",
        "Rosa",
        "Gerbera",
        "Agapanthus",
        "Aegilops",
        "Protea",
        "Liatris",
        "Mokara",
        "Anemone",
        "Actinidia",
    ],
    boxes=dict(min=1, max=2500),
)

ports = [
    "NY JFK CBP",
    "FL Miami Air CBP",
    "HI Honolulu CBP",
    "AZ Phoenix CBP",
    "VA Dulles CBP",
    "CA San Francisco CBP",
    "WA Seattle Air CBP",
    "TX Brownsville CBP",
    "WA Blaine CBP",
]

stems_per_box = dict(default=200)

start_date = "2014-01-01"

# random_seed(42)

shipmentClass = shipments.ParameterShipmentGenerator(
    parameters, ports, stems_per_box, start_date
)

shipment = shipments.ParameterShipmentGenerator.generate_shipment(shipmentClass)

num_stems = shipment["num_stems"]

config_str = """\
shipment:
  origins:
  - Netherlands
  - Mexico
  - Israel
  - Japan
  - New Zealand
  - India
  - Tanzania
  flowers:
  - Hyacinthus
  - Rosa
  - Gerbera
  - Agapanthus
  - Aegilops
  - Protea
  - Liatris
  - Mokara
  - Anemone
  - Actinidia
  boxes:
    min: 1
    max: 3000
#input_F280: F280_sample.csv
pest:
  infestation_rate:
    distribution: beta
    value: 0.05
    parameters:
    - 4
    - 60
  arrangement: clustered
  clustered:
    max_stems_per_cluster: 400
    distribution: random
    parameters:
    - 800
    - 20
  random_box:
    probability: 0.2
    ratio: 0.5
release_programs:
  naive_cfrp:
    flowers:
    - Hyacinthus
    - Gerbera
    - Rosa
    - Actinidia
    max_boxes: 10  # do not apply to shipments larger than
inspection:
  unit: stems
  within_box_pct: 1.0
  sample_strategy: percentage
  percentage:
    proportion: 0.02
    min_boxes: 1
  hypergeometric:
    detection_level: 0.02
    confidence_level: 0.95
    min_boxes: 1
  fixed_n: 10
  selection_strategy: random
ports:
  - NY JFK CBP
  - FL Miami Air CBP
  - HI Honolulu CBP
  - AZ Phoenix CBP
  - VA Dulles CBP
  - CA San Francisco CBP
  - WA Seattle Air CBP
  - TX Brownsville CBP
  - WA Blaine CBP
stems_per_box:
  default: 200
  air:
    default: 200
  maritime:
    default: 200
"""


def load_yaml_text(text):
    """Return configuration dictionary from YAML in a string"""
    if hasattr(yaml, "full_load"):
        return yaml.full_load(text)
    return yaml.load(text)


config = load_yaml_text(config_str)

# add_pest = shipments.get_pest_function(config)
# shipments.add_pest_uniform_random(config, shipment)

sample_func = inspections.get_sample_function(config)

print(shipment["num_stems"])

n_units_to_inspect = sample_func(shipment)
print(n_units_to_inspect)


results = inspections.inspect(config, shipment, n_units_to_inspect)
# print(results)

