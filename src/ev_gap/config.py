"""Settings only: paths and source URLs."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"

# Bundesnetzagentur: the file name contains the update date, so the URL is looked up
# on the landing page (see download.find_bnetza_csv_url).
BNETZA_PAGE = (
    "https://www.bundesnetzagentur.de/DE/Fachthemen/ElektrizitaetundGas/E-Mobilitaet/start.html"
)
BNETZA_CSV_PATTERN = r'https://data\.bundesnetzagentur\.de/[^"\']*Ladesaeulenregister_BNetzA_[\d-]+\.csv'

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
