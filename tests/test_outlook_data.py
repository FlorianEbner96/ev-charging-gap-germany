import numpy as np
import pandas as pd
import pytest

from ev_gap import config
from ev_gap.extract import (
    ELECTION_PARTIES, STRUCTURE_COLUMNS, STRUCTURE_HEADER_CHECKS, parse_election, parse_german_number, parse_structure,
)
from ev_gap.outlook_data import (
    CARS_COLUMNS, DUPLICATE_COLUMNS, LEAKING_COLUMNS, build_cars_by_year, build_context, election_shares, merge_counts, merge_structure,
)


# ------------------------------------------------------------------ numbers and the structure file

def test_german_numbers_use_a_dot_for_thousands_and_a_comma_for_decimals():
    values = pd.Series(["1.428,2", "56,7", "3.755,3", "12", "–", ".", "", " 7,5 "])
    parsed = parse_german_number(values)
    assert parsed.iloc[:4].tolist() == [1428.2, 56.7, 3755.3, 12.0]
    assert parsed.iloc[4:7].isna().all()  # a dash, a dot and nothing mean missing
    assert parsed.iloc[7] == 7.5


def structure_raw(rows: list[list[str]], header_words: dict[int, str] | None = None) -> pd.DataFrame:
    """A raw structure table (all text) with the layout the reader expects."""
    width = 3 + len(STRUCTURE_COLUMNS)
    header = ["Land", "Kreis", "Name"] + [f"column {i}" for i in range(3, width)]
    for position, word in (STRUCTURE_HEADER_CHECKS if header_words is None else header_words).items():
        header[position] = word
    return pd.DataFrame(rows, columns=header)


def structure_row(key: str, name: str, **values) -> list[str]:
    row = {column: "1,5" for column in STRUCTURE_COLUMNS} | {k: str(v) for k, v in values.items()}
    return ["Land", key, name] + [row[column] for column in STRUCTURE_COLUMNS]


def test_structure_keeps_only_district_rows_and_parses_the_numbers():
    raw = structure_raw([
        ["Schleswig-Holstein", "01", "Schleswig-Holstein"] + ["1,0"] * len(STRUCTURE_COLUMNS),  # a state row
        structure_row("01001", "Flensburg", area_km2="56,7", population_thousand="1.092,6", unemployment_rate="–"),
    ])
    table = parse_structure(raw)
    assert table["key"].tolist() == ["01001"]
    assert table.loc[0, "area_km2"] == 56.7
    assert table.loc[0, "population_thousand"] == 1092.6
    assert np.isnan(table.loc[0, "unemployment_rate"])
    assert "state" not in table.columns and list(table.columns[2:]) == STRUCTURE_COLUMNS


def test_a_changed_structure_layout_is_noticed():
    wrong = structure_raw([structure_row("01001", "Flensburg")], header_words={4: "Something else"})
    with pytest.raises(ValueError, match="layout changed"):
        parse_structure(wrong)
    with pytest.raises(ValueError, match="columns"):
        parse_structure(structure_raw([structure_row("01001", "Flensburg")]).iloc[:, :20])


# ------------------------------------------------------------------ election

def election_raw() -> pd.DataFrame:
    def row(area, number, kind, group, count, vote="1"):
        return {"Gebietsart": area, "Gebietsnummer": number, "Gruppenart": kind, "Gruppenname": group, "Stimme": vote, "Anzahl": str(count)}
    rows = []
    for number, eligible, voters, valid, greens, cdu, csu, afd in (("01001", 1000, 650, 640, 100, 200, 0, 90), ("09162", 2000, 1300, 1280, 300, 0, 400, 100)):
        rows += [row("Kreis", number, "System-Gruppe", "Wahlberechtigte", eligible, None), row("Kreis", number, "System-Gruppe", "Wählende", voters, None),
                 row("Kreis", number, "System-Gruppe", "Gültige", valid), row("Kreis", number, "System-Gruppe", "Ungültige", 10),
                 row("Kreis", number, "Partei", "GRÜNE", greens), row("Kreis", number, "Partei", "CDU", cdu) if cdu else None,
                 row("Kreis", number, "Partei", "CSU", csu) if csu else None, row("Kreis", number, "Partei", "AfD", afd),
                 row("Kreis", number, "Partei", "Tierschutzpartei", 5)]
    rows = [r for r in rows if r] + [row("Land", "01", "Partei", "GRÜNE", 99999), row("Bund", "99", "Partei", "GRÜNE", 99999)]
    return pd.DataFrame(rows)


def test_election_counts_use_only_district_rows_and_the_parties_that_are_kept():
    counts = parse_election(election_raw())
    assert counts.index.tolist() == ["01001", "09162"]
    assert counts.loc["01001", ["eligible", "voters", "valid", "greens"]].tolist() == [1000, 650, 640, 100]
    assert counts.loc["01001", "csu"] == 0 and counts.loc["09162", "cdu"] == 0  # a party that did not run has 0 votes
    assert "Tierschutzpartei" not in counts.columns and set(ELECTION_PARTIES.values()) <= set(counts.columns)


def test_election_shares_are_percent_of_valid_votes_and_add_up_to_100():
    shares = election_shares(parse_election(election_raw()))
    assert shares.loc["01001", "share_greens"] == pytest.approx(100 / 640 * 100)
    assert shares.loc["09162", "share_cdu_csu"] == pytest.approx(400 / 1280 * 100)  # the CSU counts as CDU and CSU
    assert shares.loc["01001", "turnout_pct"] == pytest.approx(65.0)
    parties = [c for c in shares.columns if c.startswith("share_")]
    assert shares[parties].sum(axis=1).tolist() == pytest.approx([100.0, 100.0])


def test_merged_districts_add_up_the_votes_and_the_shares_are_computed_afterwards():
    counts = pd.DataFrame({"eligible": [1000, 3000], "voters": [600, 1800], "valid": [100, 900], "greens": [50, 90], "cdu": 0, "csu": 0,
                           "spd": 0, "afd": 0, "fdp": 0, "left": 0, "bsw": 0, "free_voters": 0},
                          index=pd.Index(["07211", "07235"], name="key"))
    merged = merge_counts(counts)
    assert merged.index.tolist() == ["07211"] and merged.loc["07211", "valid"] == 1000
    # 140 of 1000 votes. The average of the two shares (50% and 10%) would give 30%.
    assert election_shares(merged).loc["07211", "share_greens"] == pytest.approx(14.0)


# ------------------------------------------------------------------ merged structure rows

def test_merging_two_structure_rows_adds_counts_and_weights_rates():
    table = parse_structure(structure_raw([
        structure_row("07211", "Trier", area_km2="100", population_thousand="100", german_population_thousand="90",
                      unemployment_rate="4,0", settlement_traffic_land_pct="50", municipalities="1", density_per_km2="1.000"),
        structure_row("07235", "Trier-Saarburg", area_km2="900", population_thousand="300", german_population_thousand="280",
                      unemployment_rate="2,0", settlement_traffic_land_pct="10", municipalities="100", density_per_km2="333"),
        structure_row("01001", "Flensburg", unemployment_rate="9,0"),
    ]))
    merged = merge_structure(table).set_index("key")
    assert merged.index.tolist() == ["01001", "07211"]
    trier = merged.loc["07211"]
    assert trier["name"] == "Trier"
    assert trier["area_km2"] == 1000 and trier["population_thousand"] == 400 and trier["municipalities"] == 101
    assert trier["unemployment_rate"] == pytest.approx((4 * 100 + 2 * 300) / 400)           # weighted by population
    assert trier["settlement_traffic_land_pct"] == pytest.approx((50 * 100 + 10 * 900) / 1000)  # land use weighted by area
    assert trier["density_per_km2"] == pytest.approx(400 * 1000 / 1000)                      # recomputed
    assert merged.loc["01001", "unemployment_rate"] == 9.0                                    # other rows unchanged


def test_a_rate_that_is_missing_for_one_part_uses_the_other_part():
    table = parse_structure(structure_raw([
        structure_row("07211", "Trier", population_thousand="100", employees_agriculture_pct="–"),
        structure_row("07235", "Trier-Saarburg", population_thousand="300", employees_agriculture_pct="2,0"),
    ]))
    assert merge_structure(table).set_index("key").loc["07211", "employees_agriculture_pct"] == 2.0


def test_the_context_has_no_duplicate_or_leaking_columns_and_checks_the_districts():
    structure = parse_structure(structure_raw([structure_row("01001", "Flensburg"), structure_row("09162", "München")]))
    context = build_context(structure, parse_election(election_raw()), ["01001", "09162"])
    assert context["key"].tolist() == ["01001", "09162"]
    for column in DUPLICATE_COLUMNS + LEAKING_COLUMNS:
        assert column not in context.columns
    assert "share_greens" in context.columns and "disposable_income_per_resident_eur" in context.columns
    with pytest.raises(ValueError, match="differ from the main table"):
        build_context(structure, parse_election(election_raw()), ["01001", "09162", "99999"])


def test_the_leaking_column_is_the_car_stock_of_january_2023():
    """It is a car figure for 1 January 2023, which contains the outcome of the growth step 2022 to 2023."""
    assert LEAKING_COLUMNS == ["electric_or_hybrid_cars_pct"]
    assert LEAKING_COLUMNS[0] in STRUCTURE_COLUMNS


# ------------------------------------------------------------------ cars by year

def kba_table(keys_and_bev: dict[str, int]) -> pd.DataFrame:
    rows = [{"key": key, "zb_name": key, **{c: bev * 10 for c in CARS_COLUMNS}, "bev": bev} for key, bev in keys_and_bev.items()]
    return pd.DataFrame(rows)


KEYS = ["06435", "16063", "01001"]


def test_every_year_is_brought_to_the_same_districts():
    kba_by_year = {
        2021: kba_table({"06435": 5, "16063": 2, "16056": 1, "01001": 7}),   # Eisenach is separate in 2021
        2022: kba_table({"06435": 6, "16063": 3, "01001": 8}),
        2026: kba_table({"06435": 7, "06415": 2, "16063": 4, "01001": 9}),   # Hanau is separate in 2026
    }
    cars = build_cars_by_year(kba_by_year, KEYS)
    assert len(cars) == 3 * 3 and set(cars["year"]) == {2021, 2022, 2026}
    bev = cars.set_index(["key", "year"])["bev"]
    assert bev[("16063", 2021)] == 3          # Wartburgkreis 2 plus Eisenach 1
    assert bev[("06435", 2026)] == 9          # Main-Kinzig 7 plus Hanau 2
    assert bev[("01001", 2022)] == 8


def test_merging_districts_does_not_change_the_total_of_any_year():
    kba_by_year = {2021: kba_table({"06435": 5, "16063": 2, "16056": 1, "01001": 7}), 2026: kba_table({"06435": 7, "06415": 2, "16063": 4, "01001": 9})}
    cars = build_cars_by_year(kba_by_year, KEYS)
    for year, kba in kba_by_year.items():
        assert cars[cars["year"] == year]["bev"].sum() == kba["bev"].sum()


def test_a_year_with_a_missing_or_unknown_district_raises():
    with pytest.raises(ValueError, match="2022.*missing"):
        build_cars_by_year({2022: kba_table({"06435": 6, "01001": 8})}, KEYS)
    with pytest.raises(ValueError, match="2022.*unexpected.*99999"):
        build_cars_by_year({2022: kba_table({"06435": 6, "16063": 3, "01001": 8, "99999": 1})}, KEYS)


def test_the_kba_url_and_file_templates_match_the_settings_of_the_main_pipeline():
    assert config.KBA_FZ1_FILE_TEMPLATE.format(year=2026) == config.KBA_FZ1_FILE
    assert config.KBA_FZ1_URL_TEMPLATE.format(year=2026) == config.KBA_FZ1_URL
    assert config.KBA_YEARS == [2021, 2022, 2023, 2024, 2025, 2026]
