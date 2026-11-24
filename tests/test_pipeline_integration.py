"""End to end test on the real raw files. Skipped if the files have not been downloaded."""

import pytest

from ev_gap import config
from ev_gap.pipeline import load_districts, run

raw_available = (
    any(config.RAW_DIR.glob(config.BNETZA_GLOB))
    and (config.RAW_DIR / config.KBA_FZ1_FILE).exists()
    and (config.RAW_DIR / config.DESTATIS_KREISE_FILE).exists()
)


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
