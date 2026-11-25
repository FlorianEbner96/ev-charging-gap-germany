"""End to end test on the real raw files. Skipped if the files have not been downloaded."""

import json
from pathlib import Path

import pytest

from ev_gap import config
from ev_gap.pipeline import data_dates, file_date, load_districts, run

raw_available = (
    any(config.RAW_DIR.glob(config.BNETZA_GLOB))
    and (config.RAW_DIR / config.KBA_FZ1_FILE).exists()
    and (config.RAW_DIR / config.DESTATIS_KREISE_FILE).exists()
)


def test_the_reference_date_is_read_from_the_file_name():
    assert file_date(Path("Ladesaeulenregister_BNetzA_2026-11-12.csv")) == "2026-11-12"
    assert file_date(Path("kba_fz1_2026-01-01.xlsx")) == "2026-01-01"
    with pytest.raises(ValueError):
        file_date(Path("no_date_here.csv"))


def test_data_dates_name_the_three_sources():
    dates = data_dates(Path("Ladesaeulenregister_BNetzA_2026-11-12.csv"), Path("kba_fz1_2026-01-01.xlsx"),
                       Path("destatis_kreise_2024-12-31.xlsx"))
    assert dates["charging_register"] == "2026-11-12"
    assert dates["kba_car_stock"] == "2026-01-01"
    assert dates["destatis_population"] == "2024-12-31"
    assert dates["pipeline_run_utc"].endswith("+00:00")


@pytest.mark.skipif(not raw_available, reason="raw data not downloaded (python -m ev_gap.download)")
def test_pipeline_on_real_data(tmp_path):
    target = tmp_path / "districts.csv"
    districts = run(target=target)

    assert len(districts) == 399
    assert districts["key"].is_unique
    assert districts["charging_points"].min() > 0
    assert districts[["bev", "population", "area_km2"]].gt(0).all().all()
    assert districts["bev"].sum() == 2_031_870  # KBA, 01.01.2026

    # the written file keeps the leading zeros of the keys
    assert load_districts(target)["key"].str.len().eq(5).all()

    # the reference dates are written next to the table
    info = json.loads((tmp_path / "data_info.json").read_text(encoding="utf-8"))
    assert info["kba_car_stock"] == "2026-01-01" and info["destatis_population"] == "2024-12-31"
