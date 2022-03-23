"""Test configuration loading functions"""

import pytest

from popsborder.inputs import (
    dict_config_to_table,
    load_configuration,
    print_table_config,
)


@pytest.mark.parametrize("file_format", ["csv", "xlsx", "ods"])
def test_small_configs_are_same(datadir, file_format):
    """Check that configurations loaded from tables are the same as YAML"""
    config_yml = load_configuration(datadir / "small_config.yml")
    config_csv = load_configuration(datadir / f"small_config.{file_format}")
    assert config_csv == config_yml


@pytest.mark.parametrize("file_format", ["csv", "xlsx", "ods"])
def test_number_indexing_columns_xlsx(datadir, file_format):
    """Check that columns can be indexed using 1-based numerical indices"""
    config_yml = load_configuration(datadir / "small_config.yml")
    config_xlsx = load_configuration(
        datadir / f"small_config.{file_format}::key_column=1,value_column=2"
    )
    assert config_xlsx == config_yml


@pytest.mark.parametrize("file_format", ["csv", "xlsx", "ods"])
def test_letter_indexing_columns_xlsx(datadir, file_format):
    """Check that columns can be indexed using letter indices"""
    config_yml = load_configuration(datadir / "small_config.yml")
    config_xlsx = load_configuration(
        datadir / f"small_config.{file_format}::key_column=A,value_column=B"
    )
    assert config_xlsx == config_yml


@pytest.mark.parametrize("file_format", ["csv", "xlsx", "ods"])
def test_indexing_columns_in_parameters_overrides(datadir, file_format):
    """Check that columns indices from parameters override those from filename suffix"""
    config_yml = load_configuration(datadir / "small_config.yml")
    config_xlsx = load_configuration(
        datadir / f"small_config.{file_format}::key_column=A,value_column=A",
        value_column="B",
    )
    assert config_xlsx == config_yml


@pytest.mark.parametrize("file_format", ["xlsx", "ods"])
def test_sheet_access(datadir, file_format):
    """Check that a sheet can be access by name"""
    config_yml = load_configuration(datadir / "small_config.yml")
    config_xlsx = load_configuration(
        datadir / f"small_config.{file_format}",
        sheet="Config Version 1",
        key_column="A",
        value_column="B",
    )
    assert config_xlsx == config_yml


@pytest.mark.parametrize("file_format", ["csv", "xlsx", "ods"])
def test_default_columns(datadir, file_format):
    """Check that default columns are correctly used"""
    config_yml = load_configuration(datadir / "small_config.yml")
    config_xlsx = load_configuration(datadir / f"small_config.{file_format}")
    assert config_xlsx == config_yml


@pytest.mark.parametrize("column", ["D", "E", 6])
def test_large_config_load(datadir, column):
    """Check that a larger, somewhat complete, configuration loads from a table"""
    load_configuration(datadir / f"large_config.xlsx::value_column={column}")


@pytest.mark.parametrize("file_format", ["xlsx", "ods"])
def test_user_friendly_config_load(datadir, file_format):
    """Check that a full user-friendly configuration loads from a table"""
    config_csv = load_configuration(
        datadir / "user_friendly_config.csv", key_column="D", value_column="B"
    )
    config_other = load_configuration(
        datadir / f"user_friendly_config.{file_format}",
        key_column="D",
        value_column="B",
    )
    num_top_level_keys = 3
    assert len(config_csv) == num_top_level_keys
    assert len(config_other) == num_top_level_keys
    assert config_other == config_csv


def test_dict_config_to_table(datadir):
    """Check that we can convert to table with dict rows and back"""
    config_yml = load_configuration(datadir / "small_config.yml")
    table = dict_config_to_table(config_yml)
    print_table_config(table)
    config_table = load_configuration(table)
    assert config_table == config_yml


def test_include_files(datadir):
    """Included YAML file with a list loads"""
    config = load_configuration(datadir / "small_config_with_includes.yml")
    consignments = config["contamination"]["consignments"]
    assert isinstance(consignments, list)
    assert len(consignments) == 8


def test_include_files_list(datadir):
    """Included CSV file formatted as a list of items loads"""
    config = load_configuration(datadir / "small_config_with_list_includes.yml")
    consignments = config["contamination"]["consignments"]
    assert isinstance(consignments, list)
    assert len(consignments) == 7
    assert consignments[0] == {
        "commodity": "Liatris",
        "origin": "Netherlands",
        "contamination": {"arrangement": "random_box"},
    }
    assert consignments[-1] == {
        "commodity": "Sedum",
        "origin": "Colombia",
        "contamination": {"arrangement": "random"},
    }
