"""District keys: map the district names of the register to official 5 digit keys."""

import re
from collections.abc import Iterable

import pandas as pd

from ev_gap import config

CITY_PREFIXES = ("Kreisfreie Stadt ", "Stadtkreis ")
CITY_KINDS = ("Kreisfreie Stadt", "Stadtkreis")


def is_city_name(register_name: str) -> bool:
    return register_name.startswith(CITY_PREFIXES)


def normalise_name(name: str) -> str:
    """Reduce a district name to a comparable form, for example 'Landkreis Mühldorf a. Inn' -> 'mühldorfa.inn'."""
    s = re.sub(r"^(Landkreis|Kreisfreie Stadt|Stadtkreis|Kreis) ", "", name)  # register prefixes
    s = s.split(",")[0]                                                       # 'Flensburg, Stadt'
    s = re.sub(r"\(.*?\)", "", s)                                             # '(Oldb)', '(Saale)'
    s = re.sub(r"^(Region|Städteregion|Regionalverband) ", "", s)             # 'Region Hannover'
    return re.sub(r"\s+", "", s).lower()                                      # 'a. Inn' and 'a.Inn'


def map_register_names(names: Iterable[str], destatis: pd.DataFrame) -> pd.DataFrame:
    """Return a table kreis_name -> key.

    A city and its surrounding Landkreis often share a name (Passau, Hof, ...), so the
    match uses the type (city or rural district) together with the normalised name.
    Raises ValueError if a name has no key or if the Destatis side is ambiguous.
    """
    official = pd.DataFrame({
        "key": destatis["key"],
        "is_city": destatis["kind"].isin(CITY_KINDS),
        "norm": destatis["name"].map(normalise_name),
    })
    if official.duplicated(["is_city", "norm"]).any():
        raise ValueError("Destatis names are not unique after normalisation.")

    registered = pd.DataFrame({"kreis_name": pd.unique(pd.Series(list(names)))})
    registered["is_city"] = registered["kreis_name"].map(is_city_name)
    registered["norm"] = registered["kreis_name"].map(normalise_name)

    mapping = registered.merge(official, on=["is_city", "norm"], how="left")
    manual = mapping["kreis_name"].map(config.REGISTER_NAME_TO_KEY)
    mapping["key"] = mapping["key"].fillna(manual)

    missing = mapping.loc[mapping["key"].isna(), "kreis_name"].tolist()
    if missing:
        raise ValueError(f"No district key for register names: {missing}")
    return mapping[["kreis_name", "key"]]


def apply_merges(keys: pd.Series) -> pd.Series:
    """Replace keys of districts that are merged into another one (assumptions A1 and A2)."""
    return keys.replace(config.KEY_MERGES)
