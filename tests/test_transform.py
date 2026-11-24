import pytest

from ev_gap import config
from ev_gap.transform import build_districts, check_totals, clean_register, count_points


def row(df, key):
    return df.set_index("key").loc[key]


def test_clean_register_drops_stations_not_in_operation_and_without_points(register):
    register.loc[0, "n_points"] = 0
    cleaned = clean_register(register)
    assert (cleaned["status"] == "In Betrieb").all()
    assert (cleaned["n_points"] > 0).all()
    assert len(cleaned) == len(register) - 2  # the Wartung row and the zero-point row


def test_count_points_splits_normal_and_fast(register, destatis):
    counts = count_points(clean_register(register), destatis)
    flensburg = row(counts, "01001")
    assert (flensburg["points_normal"], flensburg["points_fast"], flensburg["charging_points"]) == (2, 4, 6)


def test_count_points_does_not_mix_up_city_and_landkreis(register, destatis):
    counts = count_points(clean_register(register), destatis)
    assert row(counts, "09262")["charging_points"] == 1   # Passau, city
    assert row(counts, "09263")["charging_points"] == 8   # Passau, Landkreis
    assert row(counts, "03403")["charging_points"] == 2   # Oldenburg, city
    assert row(counts, "03458")["charging_points"] == 3   # Oldenburg, Landkreis


def test_hanau_is_added_to_main_kinzig_kreis(register, kba, destatis):
    districts = build_districts(register, kba, destatis)
    assert "06415" not in set(districts["key"])
    main_kinzig = row(districts, "06435")
    assert main_kinzig["charging_points"] == 5 + 7
    # KBA rows for Hanau (4th row, bev 400) and Main-Kinzig-Kreis (5th row, bev 500)
    assert main_kinzig["bev"] == 400 + 500


def test_trier_and_trier_saarburg_are_one_district(register, kba, destatis):
    districts = build_districts(register, kba, destatis)
    assert "07235" not in set(districts["key"])
    trier = row(districts, "07211")
    assert trier["charging_points"] == 4 + 6
    assert trier["population"] == 100_000 + 150_000
    assert trier["area_km2"] == pytest.approx(1200.0)


def test_stations_in_maintenance_are_not_counted(register, kba, destatis):
    districts = build_districts(register, kba, destatis)
    assert row(districts, "09183")["charging_points"] == 2


def test_district_without_charging_points_has_zero(register, kba, destatis):
    districts = build_districts(register[register["kreis_name"] != "Landkreis Passau"], kba, destatis)
    assert row(districts, "09263")["charging_points"] == 0


def test_build_districts_has_one_row_per_merged_district(register, kba, destatis):
    districts = build_districts(register, kba, destatis)
    assert len(districts) == len(kba) - 1  # Hanau is merged away
    assert districts["key"].is_unique


def test_density_is_population_per_square_kilometre(register, kba, destatis):
    flensburg = row(build_districts(register, kba, destatis), "01001")
    assert flensburg["density"] == pytest.approx(100_000 / 50.0)


def test_plugin_cars_is_bev_plus_plugin_hybrids(register, kba, destatis):
    districts = build_districts(register, kba, destatis)
    assert (districts["plugin_cars"] == districts["bev"] + districts["phev"]).all()


def test_no_column_is_built_from_the_target(register, kba, destatis):
    """Cars per point and similar columns would contain the target. They must not be in the table."""
    districts = build_districts(register, kba, destatis)
    assert "bev_per_point" not in districts.columns


def test_model_features_exist_and_do_not_contain_the_target(register, kba, destatis):
    districts = build_districts(register, kba, destatis)
    assert set(config.FEATURE_COLUMNS) <= set(districts.columns)
    assert config.TARGET in districts.columns
    assert config.TARGET not in config.FEATURE_COLUMNS
    assert not set(config.TARGET_PARTS) & set(config.FEATURE_COLUMNS)


def test_check_totals_catches_lost_charging_points(register, kba, destatis):
    districts = build_districts(register, kba, destatis)
    broken = districts.copy()
    broken.loc[0, "charging_points"] += 1
    with pytest.raises(ValueError, match="charging_points"):
        check_totals(broken, clean_register(register), kba, destatis)
