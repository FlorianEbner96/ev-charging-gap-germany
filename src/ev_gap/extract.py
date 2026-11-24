"""Extract: read the three raw files into plain tables with clean column names.

No joins and no business rules here. Only the file quirks are handled
(header lines, encoding, decimal comma, Excel layout).
"""

from pathlib import Path

import pandas as pd

REGISTER_COLUMNS = {
    "Ladeeinrichtungs-ID": "id",
    "Status": "status",
    "Art der Ladeeinrichtung": "kind",
    "Anzahl Ladepunkte": "n_points",
    "Nennleistung Ladeeinrichtung [kW]": "power_kw",
    "Inbetriebnahmedatum": "commissioned",
    "Kreis/kreisfreie Stadt": "kreis_name",
    "Bundesland": "state",
    "Breitengrad": "lat",
    "Längengrad": "lon",
}

# Column positions in sheet FZ1.2 of the KBA file (counted from the first column).
KBA_COLUMNS = {3: "label", 4: "pkw_total", 5: "petrol", 6: "diesel", 7: "gas",
               8: "hybrid", 9: "phev", 10: "bev", 11: "other_fuel"}
KBA_COUNT_COLUMNS = [name for name in KBA_COLUMNS.values() if name != "label"]


def read_register(path: Path) -> pd.DataFrame:
    """Charging stations. One row is a station with 1 or more charging points."""
    df = pd.read_csv(
        path,
        sep=";",
        skiprows=10,  # notes before the header
        encoding="cp1252",
        decimal=",",
        usecols=list(REGISTER_COLUMNS),
    ).rename(columns=REGISTER_COLUMNS)
    df["commissioned"] = pd.to_datetime(df["commissioned"], format="%d.%m.%Y", errors="coerce")
    return df


def parse_kba_sheet(raw: pd.DataFrame) -> pd.DataFrame:
    """Turn the raw KBA sheet (read with header=None, skiprows=9) into one row per Zulassungsbezirk.

    Raises ValueError if the district rows do not add up to the national total in the file.
    """
    table = raw[list(KBA_COLUMNS)].rename(columns=KBA_COLUMNS)
    # District rows start with a 5 digit key. Everything else is a header, subtotal or footnote.
    is_district = table["label"].astype("string").str.match(r"^\d{5} ").fillna(False).astype(bool)
    districts = table[is_district].copy()
    districts["key"] = districts["label"].str[:5]
    districts["zb_name"] = districts["label"].str[6:].str.strip()
    districts[KBA_COUNT_COLUMNS] = districts[KBA_COUNT_COLUMNS].astype(int)
    districts = districts.drop(columns="label").reset_index(drop=True)

    # The total row and the row for vehicles without district sit in the state column.
    labels = raw[1].astype("string").str.strip()
    expected = raw.loc[labels == "DEUTSCHLAND INSGESAMT", 4].iloc[0]
    without_district = raw.loc[labels == "SONSTIGE", 4].iloc[0]
    if districts["pkw_total"].sum() + without_district != expected:
        raise ValueError("KBA district rows do not add up to the national total.")
    return districts


def read_kba(path: Path) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name="FZ1.2", header=None, skiprows=9)
    return parse_kba_sheet(raw)


def parse_destatis_sheet(raw: pd.DataFrame) -> pd.DataFrame:
    """Turn the raw Destatis sheet (read with header=None, skiprows=2) into one row per Kreis."""
    table = raw.iloc[:, [0, 1, 2, 4, 5]]
    table.columns = ["key", "kind", "name", "area_km2", "population"]
    # Kreis rows have a 5 digit key. Rows for states and regions have shorter keys.
    is_kreis = table["key"].astype("string").str.fullmatch(r"\d{5}").fillna(False).astype(bool)
    return table[is_kreis].astype({"key": str, "area_km2": float, "population": float}).reset_index(drop=True)


def read_destatis(path: Path) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name=1, header=None, skiprows=2, dtype={0: "string"})
    return parse_destatis_sheet(raw)
