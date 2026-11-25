"""Ranking of the districts by their gap, and a rough value estimate for closing the gaps.

The value estimate is built from assumptions (see config.py). It is an order of magnitude,
not a business case: it ignores the cost of electricity, operation, site rent and tax.
"""

import pandas as pd

from ev_gap import config
from ev_gap.model import GAPS_FILE
from ev_gap.pipeline import load_districts

RANKING_FILE = config.PROCESSED_DIR / "ranking.csv"
VALUE_FILE = config.PROCESSED_DIR / "value_scenarios.csv"
CASES = ("low", "base", "high")


def load_gaps(path=GAPS_FILE) -> pd.DataFrame:
    return pd.read_csv(path, dtype={"key": str})


def rank_districts(gaps: pd.DataFrame, clearly_below_pct: float = config.CLEARLY_BELOW_PCT) -> pd.DataFrame:
    """One row per district, sorted by the percent gap of the linear model (most below expected first).

    - clearly_below: the gap is below -clearly_below_pct
    - robust: gradient boosting says the same, so the result does not depend on one model
    - rank_pct: 1 is the largest gap in percent. rank_points: 1 is the largest number of missing points
    - missing_to_band, missing_to_expected: charging points needed to reach the edge of the band or the expected number
    """
    limit = -clearly_below_pct
    expected = gaps["expected_linear"]
    ranking = pd.DataFrame({
        "key": gaps["key"],
        "name": gaps["name"],
        "state": gaps["key"].str[:2].map(config.STATES),
        "bev": gaps["bev"],
        "population": gaps["population"],
        "actual": gaps[config.TARGET],
        "expected": expected,
        "gap_pct": gaps["gap_pct_linear"],
        "gap_pct_boosting": gaps["gap_pct_boosting"],
        "missing_points": expected - gaps[config.TARGET],
        "clearly_below": gaps["gap_pct_linear"] < limit,
        "robust": (gaps["gap_pct_linear"] < limit) & (gaps["gap_pct_boosting"] < limit),
    })
    band = 1 - clearly_below_pct / 100
    ranking["missing_to_band"] = (band * expected - gaps[config.TARGET]).clip(lower=0)
    ranking["missing_to_expected"] = (expected - gaps[config.TARGET]).clip(lower=0)
    ranking = ranking.sort_values("gap_pct").reset_index(drop=True)
    ranking["rank_pct"] = ranking.index + 1
    ranking["rank_points"] = ranking["missing_points"].rank(ascending=False, method="first").astype(int)
    return ranking


def cost_per_point(case: str, fast_share: float) -> float:
    """Investment per charging point in EUR for a mix of normal and fast points."""
    costs = config.COST_PER_POINT_EUR
    return (1 - fast_share) * costs["normal"][case] + fast_share * costs["fast"][case]


def revenue_per_point_and_year(case: str, fast_share: float) -> float:
    """Gross revenue per charging point and year in EUR (price times energy, nothing subtracted)."""
    def one(kind: str) -> float:
        kwh_per_year = (config.SESSIONS_PER_DAY[kind] * config.UTILIZATION_FACTOR[case]
                        * config.KWH_PER_SESSION[kind][case] * 365)
        price_eur = config.AD_HOC_PRICE_CT_PER_KWH[kind] * config.PRICE_FACTOR[case] / 100
        return kwh_per_year * price_eur

    return (1 - fast_share) * one("normal") + fast_share * one("fast")


def estimate_value(ranking: pd.DataFrame, fast_share: float) -> pd.DataFrame:
    """Missing points, investment and gross revenue per year for the clearly below districts.

    One row per coverage (how much of the gap is closed) and case (low, base, high).
    The low case uses the low values of all assumptions, the high case the high values.
    """
    below = ranking[ranking["clearly_below"]]
    missing = {"to the edge of the band": below["missing_to_band"].sum(), "to expected": below["missing_to_expected"].sum()}
    rows = []
    for coverage in config.COVERAGES:
        for case in CASES:
            points = missing[coverage]
            rows.append({
                "coverage": coverage,
                "case": case,
                "districts": len(below),
                "missing_points": points,
                "investment_eur": points * cost_per_point(case, fast_share),
                "gross_revenue_eur_per_year": points * revenue_per_point_and_year(case, fast_share),
            })
    return pd.DataFrame(rows)


def run(ranking_file=RANKING_FILE, value_file=VALUE_FILE):
    districts = load_districts()
    fast_share = districts["points_fast"].sum() / districts["charging_points"].sum()  # observed in the register
    ranking = rank_districts(load_gaps())
    value = estimate_value(ranking, fast_share)
    ranking_file.parent.mkdir(parents=True, exist_ok=True)
    ranking.to_csv(ranking_file, index=False)
    value.to_csv(value_file, index=False)
    print(f"{int(ranking['clearly_below'].sum())} districts clearly below, {int(ranking['robust'].sum())} of them robust")
    print(value.round(0).to_string(index=False))
    return ranking, value


if __name__ == "__main__":
    run()
