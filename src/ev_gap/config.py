"""Settings only: paths, source URLs and the district key rules."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
DISTRICTS_FILE = PROCESSED_DIR / "districts.csv"

# Bundesnetzagentur: the file name contains the update date, so the URL is looked up
# on the landing page (see download.find_bnetza_csv_url).
BNETZA_PAGE = (
    "https://www.bundesnetzagentur.de/DE/Fachthemen/ElektrizitaetundGas/E-Mobilitaet/start.html"
)
BNETZA_CSV_PATTERN = r'https://data\.bundesnetzagentur\.de/[^"\']*Ladesaeulenregister_BNetzA_[\d-]+\.csv'
BNETZA_GLOB = "Ladesaeulenregister_BNetzA_*.csv"

# KBA FZ 1: passenger cars per Zulassungsbezirk by fuel type, stock on 1 January 2026.
KBA_FZ1_URL = (
    "https://www.kba.de/SharedDocs/Downloads/DE/Statistik/Fahrzeuge/FZ1/"
    "fz1_2026.xlsx?__blob=publicationFile&v=2"
)
KBA_FZ1_FILE = "kba_fz1_2026-01-01.xlsx"

# Destatis: area and population (Zensus 2022 basis) per Kreis, 31 December 2024.
DESTATIS_KREISE_URL = (
    "https://www.destatis.de/DE/Themen/Laender-Regionen/Regionales/Gemeindeverzeichnis/"
    "Administrativ/04-kreise.xlsx?__blob=publicationFile&v=14"
)
DESTATIS_KREISE_FILE = "destatis_kreise_2024-12-31.xlsx"

# Some servers refuse the default python-requests agent.
HEADERS = {"User-Agent": "Mozilla/5.0 (ev-gap research project)"}

# District key rules (assumptions A1 and A2 in the README).
# The register names Hanau as a district. Destatis has no such Kreis.
REGISTER_NAME_TO_KEY = {"Kreisfreie Stadt Hanau": "06435"}
# Keys that are merged into another district.
# Hanau (KBA) -> Main-Kinzig-Kreis. Trier-Saarburg (Destatis) -> Trier, as in the KBA file.
KEY_MERGES = {"06415": "06435", "07235": "07211"}

# Model columns. The target is what the model predicts.
TARGET = "charging_points"
FEATURE_COLUMNS = ["bev", "population", "density"]
# Parts of the target. They stay in the table for analysis, but are never model input.
TARGET_PARTS = ["points_normal", "points_fast"]

# Sensitivity check with plug-in hybrids. "car_column" is the car count used by the baseline ratio.
FEATURE_SETS = {
    "BEV only": {"features": FEATURE_COLUMNS, "car_column": "bev"},
    "BEV and PHEV separate": {"features": ["bev", "phev", "population", "density"], "car_column": "bev"},
    "Plug-in cars combined": {"features": ["plugin_cars", "population", "density"], "car_column": "plugin_cars"},
}

# Federal states: the first two digits of a district key.
STATES = {"01": "Schleswig-Holstein", "02": "Hamburg", "03": "Niedersachsen", "04": "Bremen",
          "05": "Nordrhein-Westfalen", "06": "Hessen", "07": "Rheinland-Pfalz", "08": "Baden-Württemberg",
          "09": "Bayern", "10": "Saarland", "11": "Berlin", "12": "Brandenburg",
          "13": "Mecklenburg-Vorpommern", "14": "Sachsen", "15": "Sachsen-Anhalt", "16": "Thüringen"}

# Ranking. A district is "clearly below" if it has more than this percent fewer charging points
# than expected. The typical model error is about 21%, so smaller gaps are noise.
CLEARLY_BELOW_PCT = 30

# Value estimate. Every number below is an ASSUMPTION, even where a source is named.
# The README lists them as A8 to A14 with their sources.
# Investment per charging point in EUR, without VAT, without grid expansion or battery storage.
# Source: Oeko-Institut, EWI, FCN (22.07.2022), table 2-1, hardware plus planning and installation.
#   normal: public 22 kW, 4,000 to 7,500 EUR (low, high), base is the middle.
#   fast: public 50 kW, 23,000 to 32,000 EUR (base 27,500). The high case uses the lower bound of the
#   150 kW class (65,000 EUR) to show the effect of more powerful chargers.
COST_PER_POINT_EUR = {
    "normal": {"low": 4_000, "base": 5_750, "high": 7_500},
    "fast": {"low": 23_000, "base": 27_500, "high": 65_000},
}
# Charging sessions per point and day, national average 2025. Reported on a Statista page for 2025,
# seen only in a search summary and not opened. Treated as unverified.
SESSIONS_PER_DAY = {"normal": 0.63, "fast": 2.5}
# New points are assumed to be used less (or as much) as the national average. Pure assumption.
UTILIZATION_FACTOR = {"low": 0.5, "base": 0.75, "high": 1.0}
# Energy per session in kWh. Pure assumption, no source.
KWH_PER_SESSION = {"normal": {"low": 10, "base": 15, "high": 20}, "fast": {"low": 25, "base": 35, "high": 45}}
# Average ad hoc price in ct per kWh, July 2026 (ACE, Hocsy): AC 52.30, DC 70.49.
# The price factor lowers it, because many drivers pay less with a contract. The factors are assumptions.
AD_HOC_PRICE_CT_PER_KWH = {"normal": 52.3, "fast": 70.5}
PRICE_FACTOR = {"low": 0.7, "base": 0.85, "high": 1.0}
# Share of the gap that is closed. "to the band" brings a district to (100 - CLEARLY_BELOW_PCT)% of expected.
COVERAGES = {"to the edge of the band": 1 - CLEARLY_BELOW_PCT / 100, "to expected": 1.0}

# Charging stations with this status are counted. Others (for example "In Wartung") are dropped.
ACTIVE_STATUS = "In Betrieb"
