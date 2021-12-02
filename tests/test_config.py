from popsborder.simulation import load_configuration


def test_small_configs_are_same(datadir):
    """Check that configurations loaded from different sources are the same"""
    config_yml = load_configuration(datadir / "small_config.yml")
    config_csv = load_configuration(datadir / "small_config.csv")
    # config_ods = load_configuration(datadir / "small_config.ods")
    # config_xlsx = load_configuration(datadir / "small_config.xlsx")

    assert config_csv == config_yml


def test_large_config_load(datadir):
    """Check that a larger (complete) configuration loads from a table"""
    load_configuration(datadir / "large_config.xlsx")
