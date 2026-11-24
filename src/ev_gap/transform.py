"""Transform: clean the register and join the three sources to one table per district.

All functions take and return DataFrames. No file paths here, so they are easy to test.
"""

import pandas as pd

from ev_gap import config
from ev_gap.keys import apply_merges, map_register_names

POINT_COLUMNS = {"Normalladeeinrichtung": "points_normal", "Schnellladeeinrichtung": "points_fast"}


def clean_register(register: pd.DataFrame) -> pd.DataFrame:
    """Keep stations that are in operation and have at least one charging point."""
    keep = (register["status"] == config.ACTIVE_STATUS) & (register["n_points"] > 0)
    return register[keep].copy()


def count_points(register: pd.DataFrame, destatis: pd.DataFrame) -> pd.DataFrame:
    """Charging points per district key, split into normal and fast chargers."""
    mapping = map_register_names(register["kreis_name"].unique(), destatis)
    stations = register.merge(mapping, on="kreis_name", validate="many_to_one")
    stations["key"] = apply_merges(stations["key"])

    counts = (
        stations.pivot_table(index="key", columns="kind", values="n_points", aggfunc="sum", fill_value=0)
        .rename(columns=POINT_COLUMNS)
        .reindex(columns=list(POINT_COLUMNS.values()), fill_value=0)
    )
    counts["charging_points"] = counts.sum(axis=1)
    return counts.reset_index()


def count_cars(kba: pd.DataFrame) -> pd.DataFrame:
    """Passenger cars per district key. Districts that are merged are summed."""
    cars = kba.assign(key=apply_merges(kba["key"]))
    return cars.groupby("key", as_index=False)[["pkw_total", "bev", "phev"]].sum()


def district_size(destatis: pd.DataFrame) -> pd.DataFrame:
    """Area and population per district key. Districts that are merged are summed."""
    sized = destatis.assign(key=apply_merges(destatis["key"]))
    return sized.groupby("key", as_index=False).agg(
        name=("name", "first"), area_km2=("area_km2", "sum"), population=("population", "sum")
    )


def build_districts(register: pd.DataFrame, kba: pd.DataFrame, destatis: pd.DataFrame) -> pd.DataFrame:
    """One row per district with cars, charging points, population and area.

    Raises ValueError if the join loses or duplicates cars, people or charging points.
    """
    active = clean_register(register)
    districts = (
        count_cars(kba)
        .merge(district_size(destatis), on="key", how="inner", validate="one_to_one")
        .merge(count_points(active, destatis), on="key", how="left", validate="one_to_one")
    )
    point_columns = ["points_normal", "points_fast", "charging_points"]
    districts[point_columns] = districts[point_columns].fillna(0).astype(int)
    districts["density"] = districts["population"] / districts["area_km2"]
    districts["bev_per_point"] = districts["bev"] / districts["charging_points"].where(districts["charging_points"] > 0)

    check_totals(districts, active, kba, destatis)
    return districts.sort_values("key").reset_index(drop=True)


def check_totals(districts: pd.DataFrame, active: pd.DataFrame, kba: pd.DataFrame, destatis: pd.DataFrame) -> None:
    """The joined table must contain every car, person and charging point of its sources."""
    expected = {
        "bev": kba["bev"].sum(),
        "phev": kba["phev"].sum(),
        "population": destatis["population"].sum(),
        "charging_points": active["n_points"].sum(),
    }
    for column, total in expected.items():
        if round(districts[column].sum()) != round(total):
            raise ValueError(f"Total of '{column}' changed in the join: {districts[column].sum()} vs {total}")
    if districts["key"].duplicated().any():
        raise ValueError("District keys are not unique.")
