import os
import sys
import subprocess
import yaml


def key_to_option(key):
    return "--{}".format(key.replace("_", "-"))


def dict_to_options(dictionary):
    options = []
    for key, value in dictionary.items():
        options.append(key_to_option(key))
        options.append("{}".format(value))
    return options


def run_pathways_cli(**kwargs):
    # Using unpacking into a list literal from Python 3.5
    return subprocess.check_output(
        [sys.executable, "-m", "pathways", *dict_to_options(kwargs)],
        universal_newlines=True,
    )


def test_gives_result():
    assert "slippage" in run_pathways_cli(num_shipments=10, config_file="config.yml")
