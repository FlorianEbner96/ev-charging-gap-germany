"""The outlook tables built from the real raw files. Skipped if the files have not been downloaded."""

import pytest

from ev_gap import config, pipeline
from ev_gap.extract import ELECTION_PARTIES  # noqa: F401  (documents which parties are kept)
from ev_gap.outlook_data import LEAKING_COLUMNS, election_shares, load_cars_by_year, load_context, merge_counts, run

raw = config.RAW_DIR
needed = [raw / config.KBA_FZ1_FILE_TEMPLATE.format(year=year) for year in config.KBA_YEARS] + [
    raw / config.STRUCTURE_FILE, raw / config.ELECTION_FILE, raw / config.DESTATIS_KREISE_FILE, raw / config.KBA_FZ1_FILE]
available = all(path.exists() for path in needed) and any(raw.glob(config.BNETZA_GLOB))


@pytest.fixture(scope="module")
def tables(tmp_path_factory):
    folder = tmp_path_factory.mktemp("outlook")
    keys = pipeline.run(target=folder / "districts.csv")["key"].tolist()
    run(keys=keys, cars_file=folder / "cars.csv", context_file=folder / "context.csv")
    return load_cars_by_year(folder / "cars.csv"), load_context(folder / "context.csv")


pytestmark = pytest.mark.skipif(not available, reason="raw data not downloaded (python -m ev_gap.download)")


def test_every_district_has_every_year(tables):
    cars, _ = tables
    assert len(cars) == 399 * 6
    assert cars.groupby("key")["year"].count().eq(6).all()
    assert cars.isna().sum().sum() == 0


def test_the_national_totals_are_the_kba_totals(tables):
    cars, _ = tables
    bev = cars.groupby("year")["bev"].sum()
    assert bev[2021] == 308_745 and bev[2026] == 2_031_870
    assert bev.is_monotonic_increasing  # the stock of battery electric cars grew every year


def test_the_context_covers_all_districts_and_has_no_leaking_column(tables):
    _, context = tables
    assert len(context) == 399 and context["key"].is_unique
    assert not set(LEAKING_COLUMNS) & set(context.columns)
    assert context.shape[1] - 2 == 50  # key and name, then 50 variables


def test_the_election_results_match_the_published_national_result():
    """European election 2024: Gruene 11.9%, CDU and CSU 30.0%, SPD 13.9%, AfD 15.9%, turnout 64.7%."""
    from ev_gap.extract import read_election
    totals = merge_counts(read_election(raw / config.ELECTION_FILE)).sum().to_frame().T
    national = election_shares(totals).iloc[0]
    assert national["share_greens"] == pytest.approx(11.9, abs=0.1)
    assert national["share_cdu_csu"] == pytest.approx(30.0, abs=0.1)
    assert national["share_spd"] == pytest.approx(13.9, abs=0.1)
    assert national["share_afd"] == pytest.approx(15.9, abs=0.1)
    assert national["turnout_pct"] == pytest.approx(64.7, abs=0.1)
