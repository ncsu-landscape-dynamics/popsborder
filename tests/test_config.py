from popsborder.simulation import load_configuration


def test_small_configs_are_same(datadir):
    """Check that configurations loaded from different sources are the same"""
    config_yml = load_configuration(datadir / "small_config.yml")
    config_csv = load_configuration(datadir / "small_config.csv")
    #config_ods = load_configuration(datadir / "small_config.ods")
    config_xlsx = load_configuration(datadir / "small_config.xlsx")
    assert config_csv == config_yml
    #assert config_ods == config_yml
    assert config_xlsx == config_yml


def test_number_indexing_columns(datadir):
    """Check that configurations loaded from different sources are the same"""
    config_yml = load_configuration(datadir / "small_config.yml")
    config_xlsx = load_configuration(
        datadir / "small_config.xlsx::key_column=1,value_column=2"
    )
    assert config_xlsx == config_yml


def test_letter_indexing_columns(datadir):
    """Check that configurations loaded from different sources are the same"""
    config_yml = load_configuration(datadir / "small_config.yml")
    config_xlsx = load_configuration(
        datadir / "small_config.xlsx::key_column=A,value_column=B"
    )
    assert config_xlsx == config_yml


def test_indexing_columns_in_parameters_overrides(datadir):
    """Check that configurations loaded from different sources are the same"""
    config_yml = load_configuration(datadir / "small_config.yml")
    config_xlsx = load_configuration(
        datadir / "small_config.xlsx::key_column=A,value_column=A",
        value_column="B"
    )
    assert config_xlsx == config_yml


def test_sheet_access(datadir):
    """Check that configurations loaded from different sources are the same"""
    config_yml = load_configuration(datadir / "small_config.yml")
    config_xlsx = load_configuration(
        datadir / "small_config.xlsx",
        sheet="Config Version 1",
        key_column="A",
        value_column="B"
    )
    assert config_xlsx == config_yml

def test_default_columns(datadir):
    """Check that configurations loaded from different sources are the same"""
    config_yml = load_configuration(datadir / "small_config.yml")
    config_xlsx = load_configuration(
        datadir / "small_config.xlsx"
    )
    assert config_xlsx == config_yml

def test_large_config_load(datadir):
    """Check that a larger (complete) configuration loads from a table"""
    load_configuration(datadir / "large_config.xlsx")
