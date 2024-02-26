"""Test effectiveness"""
from popsborder.inputs import load_configuration_yaml_from_text
from popsborder.consignments import get_consignment_generator
from popsborder.contamination import get_contaminant_function
from popsborder.inspections import (
    get_sample_function,
    inspect,
    is_consignment_contaminated,
)
from popsborder.skipping import get_inspection_needed_function
from popsborder.outputs import (
    PrintReporter,
    SuccessRates,
)

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
      max: 50
  items_per_box:
    default: 10
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
  effectiveness: 0.1  # This is the effectiveness of the inspection
"""
config = load_configuration_yaml_from_text(CONFIG)
consignment_generator = get_consignment_generator(config)
add_contaminant = get_contaminant_function(config)
is_inspection_needed = get_inspection_needed_function(config)
sample = get_sample_function(config)
num_consignments = 100
detailed = False
success_rates = SuccessRates(PrintReporter())


def test_add_effectiveness(capsys):
    num_inspections = 0

    for unused_i in range(num_consignments):
        consignment = consignment_generator.generate_consignment()
        add_contaminant(consignment)

        must_inspect, applied_program = is_inspection_needed(
            consignment, consignment.date
        )
        if must_inspect:
            n_units_to_inspect = sample(consignment)
            ret = inspect(config, consignment, n_units_to_inspect, detailed)
            consignment_checked_ok = ret.consignment_checked_ok
            num_inspections += 1
        else:
            consignment_checked_ok = True  # assuming or hoping it's ok

        consignment_actually_ok = not is_consignment_contaminated(consignment)
        success_rates.record_and_add_effectiveness(
            consignment_checked_ok, consignment_actually_ok, consignment,
            config["inspection"]["effectiveness"], num_inspections)

        capture = capsys.readouterr()
        make_error, cur_effectiveness = success_rates.make_an_error(
            num_inspections, config["inspection"]["effectiveness"])

        if not consignment_actually_ok and not consignment_checked_ok:
            message = (f"---> Making an error: {cur_effectiveness:.2f} > "
                       f"{config['inspection']['effectiveness']:.2f}")
            print_out = capture.out.split("[FN] ")[1].replace("\n", "")
            assert message in print_out
