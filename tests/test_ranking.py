import pandas as pd
import pytest

from ev_gap import config
from ev_gap.ranking import (
    CASES, cost_per_point, estimate_value, rank_districts, revenue_per_point_and_year,
)


@pytest.fixture
def gaps() -> pd.DataFrame:
    """Four districts: far below, just below the band, near expected, above."""
    expected = [200.0, 100.0, 100.0, 100.0]
    actual = [60, 69, 95, 150]
    return pd.DataFrame({
        "key": ["07335", "10041", "03159", "08111"],
        "name": ["Far below", "Just below", "Near expected", "Above"],
        "bev": [1000, 2000, 3000, 4000],
        "population": [50_000, 60_000, 70_000, 80_000],
        "charging_points": actual,
        "expected_linear": expected,
        "gap_pct_linear": [(a - e) / e * 100 for a, e in zip(actual, expected)],
        "gap_pct_boosting": [-60.0, -20.0, -3.0, 40.0],  # boosting does not see "Just below" as clearly below
    })


def test_districts_are_sorted_from_most_below_to_most_above(gaps):
    ranking = rank_districts(gaps)
    assert ranking["name"].tolist() == ["Far below", "Just below", "Near expected", "Above"]
    assert ranking["rank_pct"].tolist() == [1, 2, 3, 4]


def test_clearly_below_means_more_than_30_percent_below_expected(gaps):
    ranking = rank_districts(gaps).set_index("name")
    assert ranking["clearly_below"].to_dict() == {
        "Far below": True, "Just below": True, "Near expected": False, "Above": False}


def test_robust_needs_both_models_to_agree(gaps):
    ranking = rank_districts(gaps).set_index("name")
    assert ranking["robust"].to_dict() == {
        "Far below": True, "Just below": False, "Near expected": False, "Above": False}


def test_state_comes_from_the_first_two_digits_of_the_key(gaps):
    ranking = rank_districts(gaps).set_index("name")
    assert ranking.loc["Far below", "state"] == "Rheinland-Pfalz"
    assert ranking.loc["Just below", "state"] == "Saarland"
    assert ranking.loc["Above", "state"] == "Baden-Württemberg"


def test_missing_points_to_the_band_and_to_expected(gaps):
    ranking = rank_districts(gaps).set_index("name")
    # band = 70% of expected
    assert ranking.loc["Far below", "missing_to_band"] == pytest.approx(0.7 * 200 - 60)
    assert ranking.loc["Far below", "missing_to_expected"] == pytest.approx(140)
    assert ranking.loc["Just below", "missing_to_band"] == pytest.approx(1.0)
    # districts above the band or above expected need nothing
    assert ranking.loc["Near expected", "missing_to_band"] == 0
    assert ranking.loc["Above", "missing_to_expected"] == 0
    assert ranking.loc["Above", "missing_points"] == pytest.approx(-50)


def test_rank_by_missing_points_differs_from_rank_by_percent():
    gaps = pd.DataFrame({
        "key": ["01001", "01002"], "name": ["Small", "Large"], "bev": [1, 1], "population": [1, 1],
        "charging_points": [40, 600], "expected_linear": [100.0, 1000.0],
        "gap_pct_linear": [-60.0, -40.0], "gap_pct_boosting": [-60.0, -40.0],
    })
    ranking = rank_districts(gaps).set_index("name")
    assert ranking.loc["Small", "rank_pct"] == 1 and ranking.loc["Small", "rank_points"] == 2
    assert ranking.loc["Large", "rank_pct"] == 2 and ranking.loc["Large", "rank_points"] == 1


def test_value_estimate_only_counts_the_clearly_below_districts(gaps):
    value = estimate_value(rank_districts(gaps), fast_share=0.25)
    base = value[(value["case"] == "base") & (value["coverage"] == "to expected")].iloc[0]
    assert base["districts"] == 2
    assert base["missing_points"] == pytest.approx(140 + 31)
    assert base["investment_eur"] == pytest.approx(171 * cost_per_point("base", 0.25))


def test_cost_and_revenue_per_point_for_a_mix_of_normal_and_fast_points():
    costs = config.COST_PER_POINT_EUR
    assert cost_per_point("base", 0.0) == costs["normal"]["base"]
    assert cost_per_point("base", 1.0) == costs["fast"]["base"]
    assert cost_per_point("base", 0.25) == pytest.approx(0.75 * costs["normal"]["base"] + 0.25 * costs["fast"]["base"])
    normal = config.SESSIONS_PER_DAY["normal"] * config.UTILIZATION_FACTOR["base"] * config.KWH_PER_SESSION["normal"]["base"] * 365 \
        * config.AD_HOC_PRICE_CT_PER_KWH["normal"] * config.PRICE_FACTOR["base"] / 100
    assert revenue_per_point_and_year("base", 0.0) == pytest.approx(normal)


def test_estimates_grow_from_the_low_to_the_high_case(gaps):
    value = estimate_value(rank_districts(gaps), fast_share=0.285)
    for coverage, part in value.groupby("coverage"):
        part = part.set_index("case").loc[list(CASES)]
        assert part["investment_eur"].is_monotonic_increasing, coverage
        assert part["gross_revenue_eur_per_year"].is_monotonic_increasing, coverage


def test_closing_the_gap_to_expected_costs_more_than_to_the_edge_of_the_band(gaps):
    value = estimate_value(rank_districts(gaps), fast_share=0.285)
    base = value[value["case"] == "base"].set_index("coverage")
    assert base.loc["to expected", "investment_eur"] > base.loc["to the edge of the band", "investment_eur"]


def test_assumptions_are_ordered_low_base_high():
    for kind in ("normal", "fast"):
        costs = config.COST_PER_POINT_EUR[kind]
        assert costs["low"] <= costs["base"] <= costs["high"]
        kwh = config.KWH_PER_SESSION[kind]
        assert kwh["low"] <= kwh["base"] <= kwh["high"]
    assert config.UTILIZATION_FACTOR["low"] <= config.UTILIZATION_FACTOR["base"] <= config.UTILIZATION_FACTOR["high"]
    assert config.PRICE_FACTOR["low"] <= config.PRICE_FACTOR["base"] <= config.PRICE_FACTOR["high"]
