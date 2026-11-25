"""Data for the outlook model: the car stock per district and year, and context variables per district.

- cars_by_year.csv: one row per district and year (1 January 2021 to 2026): all cars, and cars by fuel type.
- context.csv: one row per district: structure data (income, age, education, housing, ...) and the
  result of the European election 2024. These are treated as fixed characteristics of a district.

The district keys of the KBA change between years (Eisenach exists only in 2021, Hanau only in 2026).
The merge rules in config.KEY_MERGES bring every year to the same 399 districts.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ev_gap import config
from ev_gap.extract import (
    ELECTION_PARTIES, STRUCTURE_COLUMNS, read_election, read_kba, read_structure,
)
from ev_gap.keys import apply_merges
from ev_gap.pipeline import load_districts

CARS_COLUMNS = ["pkw_total", "petrol", "diesel", "gas", "hybrid", "phev", "bev", "other_fuel"]

# Dropped from the context. The first group is already in the main table, in a better version.
DUPLICATE_COLUMNS = ["municipalities", "area_km2", "population_thousand", "german_population_thousand", "density_per_km2"]
# This is a car stock figure for 1 January 2023. It contains the result of the growth step 2022 to 2023,
# so it would give the model the answer. The car mix comes from the KBA tables instead.
LEAKING_COLUMNS = ["electric_or_hybrid_cars_pct"]

SUM_COLUMNS = ["municipalities", "area_km2", "population_thousand", "german_population_thousand"]
AREA_WEIGHTED_COLUMNS = ["settlement_traffic_land_pct", "vegetation_water_land_pct"]


def build_cars_by_year(kba_by_year: dict[int, pd.DataFrame], keys: list[str]) -> pd.DataFrame:
    """Car stock per district and year, with the key merges applied to every year.

    Raises ValueError if a year does not have exactly the districts in `keys` or if a merge changes a total.
    """
    frames = []
    for year, kba in sorted(kba_by_year.items()):
        merged = kba.assign(key=apply_merges(kba["key"])).groupby("key")[CARS_COLUMNS].sum()
        missing, unexpected = sorted(set(keys) - set(merged.index)), sorted(set(merged.index) - set(keys))
        if missing or unexpected:
            raise ValueError(f"District keys differ in {year}: missing {missing}, unexpected {unexpected}")
        for column in ("bev", "phev", "pkw_total"):
            if merged[column].sum() != kba[column].sum():
                raise ValueError(f"The total of '{column}' changed by the merges in {year}.")
        frames.append(merged.reset_index().assign(year=year))
    cars = pd.concat(frames, ignore_index=True)
    return cars[["key", "year"] + CARS_COLUMNS].sort_values(["key", "year"]).reset_index(drop=True)


def merge_counts(counts: pd.DataFrame) -> pd.DataFrame:
    """Add the vote counts of merged districts."""
    merged_keys = apply_merges(pd.Series(counts.index, index=counts.index)).to_numpy()
    return counts.groupby(merged_keys).sum().rename_axis("key")


def election_shares(counts: pd.DataFrame) -> pd.DataFrame:
    """Party shares in percent of the valid votes, and the turnout. CDU and CSU are added up."""
    valid = counts["valid"]
    shares = pd.DataFrame({
        "share_greens": counts["greens"], "share_cdu_csu": counts["cdu"] + counts["csu"], "share_spd": counts["spd"],
        "share_afd": counts["afd"], "share_fdp": counts["fdp"], "share_left": counts["left"], "share_bsw": counts["bsw"],
        "share_free_voters": counts["free_voters"],
    }).div(valid, axis=0) * 100
    shares["share_other"] = 100 - shares.sum(axis=1)  # all other parties
    shares["turnout_pct"] = counts["voters"] / counts["eligible"] * 100
    return shares


def _weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    known = values.notna()
    return float((values[known] * weights[known]).sum() / weights[known].sum()) if known.any() else np.nan


def merge_structure(structure: pd.DataFrame) -> pd.DataFrame:
    """Combine the rows of merged districts. Counts and areas are added, rates are averaged.

    Rates are weighted by the population (land use shares by the area). This is an approximation for the
    one pair that is merged (Trier and Trier-Saarburg), because the true base of each rate is not in the file.
    """
    table = structure.assign(merged_key=apply_merges(structure["key"]))
    rows = []
    for key, group in table.groupby("merged_key", sort=True):
        if len(group) == 1:
            rows.append(group.drop(columns="merged_key").iloc[0].to_dict() | {"key": key})
            continue
        own = group[group["key"] == key]
        row = {"key": key, "name": (own if len(own) else group).iloc[0]["name"]}
        for column in STRUCTURE_COLUMNS:
            if column in SUM_COLUMNS:
                row[column] = group[column].sum(min_count=1)
            elif column == "density_per_km2":
                row[column] = np.nan  # set below
            elif column in AREA_WEIGHTED_COLUMNS:
                row[column] = _weighted_mean(group[column], group["area_km2"])
            else:
                row[column] = _weighted_mean(group[column], group["population_thousand"])
        row["density_per_km2"] = row["population_thousand"] * 1000 / row["area_km2"]
        rows.append(row)
    return pd.DataFrame(rows)[["key", "name"] + STRUCTURE_COLUMNS]


def build_context(structure: pd.DataFrame, election_counts: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """One row per district: structure data and election shares. Raises ValueError if the districts do not match `keys`."""
    shares = election_shares(merge_counts(election_counts)).reset_index()
    context = merge_structure(structure).drop(columns=DUPLICATE_COLUMNS + LEAKING_COLUMNS)
    context = context.merge(shares, on="key", how="outer", validate="one_to_one", indicator=True)
    problems = context[context["_merge"] != "both"]["key"].tolist()
    if problems:
        raise ValueError(f"Structure data and election results do not cover the same districts: {sorted(problems)}")
    context = context.drop(columns="_merge")
    missing, unexpected = sorted(set(keys) - set(context["key"])), sorted(set(context["key"]) - set(keys))
    if missing or unexpected:
        raise ValueError(f"Context districts differ from the main table: missing {missing}, unexpected {unexpected}")
    return context.sort_values("key").reset_index(drop=True)


def read_kba_years(raw_dir: Path = config.RAW_DIR) -> dict[int, pd.DataFrame]:
    return {year: read_kba(raw_dir / config.KBA_FZ1_FILE_TEMPLATE.format(year=year)) for year in config.KBA_YEARS}


def run(raw_dir: Path = config.RAW_DIR, cars_file: Path = config.CARS_BY_YEAR_FILE, context_file: Path = config.CONTEXT_FILE,
        keys: list[str] | None = None):
    if keys is None:
        keys = load_districts()["key"].tolist()  # the 399 districts of the main table (run the pipeline first)
    cars = build_cars_by_year(read_kba_years(raw_dir), keys)
    context = build_context(read_structure(raw_dir / config.STRUCTURE_FILE), read_election(raw_dir / config.ELECTION_FILE), keys)
    cars_file.parent.mkdir(parents=True, exist_ok=True)
    cars.to_csv(cars_file, index=False)
    context.to_csv(context_file, index=False)
    return cars, context


def load_cars_by_year(path: Path = config.CARS_BY_YEAR_FILE) -> pd.DataFrame:
    return pd.read_csv(path, dtype={"key": str})


def load_context(path: Path = config.CONTEXT_FILE) -> pd.DataFrame:
    return pd.read_csv(path, dtype={"key": str})


if __name__ == "__main__":
    cars, context = run()
    per_year = cars.groupby("year")[["bev", "phev", "pkw_total"]].sum()
    print(f"cars_by_year: {len(cars)} rows ({cars['key'].nunique()} districts, {cars['year'].nunique()} years) -> {config.CARS_BY_YEAR_FILE}")
    print(per_year.to_string())
    print(f"context: {len(context)} districts, {context.shape[1] - 2} variables -> {config.CONTEXT_FILE}")
    missing = context.isna().sum()
    print("variables with missing values:", missing[missing > 0].to_dict() or "none")
