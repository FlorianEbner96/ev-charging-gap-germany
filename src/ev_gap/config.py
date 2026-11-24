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

# Charging stations with this status are counted. Others (for example "In Wartung") are dropped.
ACTIVE_STATUS = "In Betrieb"
