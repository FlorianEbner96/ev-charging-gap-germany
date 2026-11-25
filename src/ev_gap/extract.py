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
    for column, name in ((4, "pkw_total"), (10, "bev")):  # all cars, and battery electric cars
        expected = raw.loc[labels == "DEUTSCHLAND INSGESAMT", column].iloc[0]
        without_district = raw.loc[labels == "SONSTIGE", column].iloc[0]
        if districts[name].sum() + without_district != expected:
            raise ValueError(f"KBA district rows do not add up to the national total ({name}).")
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


# ---------------------------------------------------------------- context data for the outlook model

# The columns of the structure file of the Bundeswahlleiterin, by position (column 3 onwards).
# Values are from 2021 to 2023. The comment says what the German column is about.
STRUCTURE_COLUMNS = [
    "municipalities",                                # Gemeinden, Anzahl
    "area_km2",                                      # Fläche
    "population_thousand",                           # Bevölkerung 31.12.2022
    "german_population_thousand",
    "foreign_pct",                                   # Ausländeranteil
    "density_per_km2",
    "birth_balance_per_1000",                        # Geburtensaldo 2022
    "migration_balance_per_1000",                    # Wanderungssaldo 2022
    "age_under_16_pct", "age_16_17_pct", "age_18_24_pct", "age_25_34_pct", "age_35_59_pct", "age_60_74_pct", "age_75_plus_pct",
    "settlement_traffic_land_pct",                   # Siedlungs- und Verkehrsfläche
    "vegetation_water_land_pct",
    "completed_dwellings_per_1000",                  # Fertiggestellte Wohnungen 2021
    "dwellings_per_1000",
    "living_space_per_dwelling_m2",
    "living_space_per_resident_m2",
    "cars_per_1000",                                 # PKW-Bestand 01.01.2023
    "electric_or_hybrid_cars_pct",                   # PKW mit Elektro- oder Hybridantrieb 01.01.2023
    "businesses_per_1000",
    "craft_businesses_per_1000",
    "vocational_school_leavers_per_1000",
    "general_school_leavers_per_1000",
    "school_leavers_no_degree_pct", "school_leavers_lower_secondary_pct", "school_leavers_intermediate_pct",
    "school_leavers_university_entrance_pct",
    "childcare_under_3_pct", "childcare_3_to_5_pct",
    "disposable_income_per_resident_eur",            # 2021
    "gdp_per_resident_eur",                          # 2021
    "employees_per_1000",                            # sozialversicherungspflichtig Beschäftigte 30.06.2023
    "employees_agriculture_pct", "employees_industry_pct", "employees_trade_hospitality_transport_pct",
    "employees_public_private_services_pct", "employees_other_services_pct",
    "benefit_recipients_per_1000",                   # SGB II, August 2023
    "benefit_recipients_not_employable_pct",
    "benefit_recipients_foreign_pct",
    "unemployment_rate",                             # Oktober 2023
    "unemployment_rate_men",
]
# A check that the file still has the layout this list is written for: position -> a word in the German header.
STRUCTURE_HEADER_CHECKS = {4: "Fläche", 5: "Bevölkerung", 8: "dichte", 24: "PKW", 25: "Elektro", 36: "Verfügbares Einkommen",
                           37: "Bruttoinlandsprodukt", 47: "Arbeitslosenquote"}
MISSING_MARKS = {"", ".", "-", "–", "x", "/"}


def parse_german_number(values: pd.Series) -> pd.Series:
    """'1.428,2' -> 1428.2. A dot is the thousands separator, a comma the decimal mark. '.' and a dash mean missing."""
    text = values.astype("string").str.strip()
    text = text.where(~text.isin(MISSING_MARKS))
    numbers = pd.to_numeric(text.str.replace(".", "", regex=False).str.replace(",", ".", regex=False), errors="raise")
    return numbers.astype("float64")  # a plain float column, missing values are NaN


def parse_structure(raw: pd.DataFrame) -> pd.DataFrame:
    """One row per Kreis: key and the numeric columns with short names. `raw` is read as text with its header row."""
    width = 3 + len(STRUCTURE_COLUMNS)
    if raw.shape[1] < width:
        raise ValueError(f"Structure file has {raw.shape[1]} columns, expected at least {width}.")
    for position, word in STRUCTURE_HEADER_CHECKS.items():
        if word not in str(raw.columns[position]):
            raise ValueError(f"Structure file layout changed: column {position} is '{raw.columns[position]}', expected '{word}'.")
    table = raw.iloc[:, :width].copy()
    table.columns = ["state", "key", "name"] + STRUCTURE_COLUMNS
    is_kreis = table["key"].astype("string").str.fullmatch(r"\d{5}").fillna(False).astype(bool)
    table = table[is_kreis].reset_index(drop=True)
    for column in STRUCTURE_COLUMNS:
        table[column] = parse_german_number(table[column])
    return table.drop(columns="state")


def read_structure(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path, sep=";", skiprows=8, encoding="utf-8-sig", dtype=str)
    return parse_structure(raw)


# Parties of the European election 2024 that are kept. CDU and CSU run in different states and are added up later.
ELECTION_PARTIES = {"GRÜNE": "greens", "CDU": "cdu", "CSU": "csu", "SPD": "spd", "AfD": "afd", "FDP": "fdp",
                    "DIE LINKE": "left", "BSW": "bsw", "FREIE WÄHLER": "free_voters"}
ELECTION_SYSTEM_GROUPS = {"Wahlberechtigte": "eligible", "Wählende": "voters", "Gültige": "valid"}


def parse_election(raw: pd.DataFrame) -> pd.DataFrame:
    """Vote counts per Kreis: eligible, voters, valid votes and the parties above (0 if a party did not run).

    `raw` is the long file (one row per Kreis and group), read as text.
    """
    kreise = raw[raw["Gebietsart"] == "Kreis"]
    system = kreise[kreise["Gruppenart"] == "System-Gruppe"]
    parties = kreise[(kreise["Gruppenart"] == "Partei") & (kreise["Stimme"] == "1")]
    system = system[system["Gruppenname"].isin(ELECTION_SYSTEM_GROUPS)].assign(group=lambda d: d["Gruppenname"].map(ELECTION_SYSTEM_GROUPS))
    parties = parties[parties["Gruppenname"].isin(ELECTION_PARTIES)].assign(group=lambda d: d["Gruppenname"].map(ELECTION_PARTIES))

    counts = (
        pd.concat([system, parties])
        .assign(count=lambda d: pd.to_numeric(d["Anzahl"], errors="raise"))
        .pivot_table(index="Gebietsnummer", columns="group", values="count", aggfunc="sum")
    )
    for group in list(ELECTION_SYSTEM_GROUPS.values()):
        if group not in counts or counts[group].isna().any():
            raise ValueError(f"Election file: '{group}' is missing for some districts.")
    counts = counts.reindex(columns=list(ELECTION_SYSTEM_GROUPS.values()) + list(ELECTION_PARTIES.values())).fillna(0)
    counts.index = counts.index.astype(str)
    counts.index.name = "key"
    return counts


def read_election(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path, sep=";", skiprows=9, encoding="utf-8-sig", dtype=str)
    return parse_election(raw)
