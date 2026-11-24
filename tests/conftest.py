"""Small hand-made tables where each district tests one rule."""

import pandas as pd
import pytest


@pytest.fixture
def destatis() -> pd.DataFrame:
    rows = [
        ("01001", "Kreisfreie Stadt", "Flensburg, Stadt", 50.0, 100_000),
        ("03403", "Kreisfreie Stadt", "Oldenburg (Oldenburg), Stadt", 100.0, 170_000),
        ("03458", "Landkreis", "Oldenburg", 1000.0, 130_000),
        ("06435", "Landkreis", "Main-Kinzig-Kreis", 1000.0, 420_000),
        ("07211", "Kreisfreie Stadt", "Trier, kreisfreie Stadt", 100.0, 100_000),
        ("07235", "Landkreis", "Trier-Saarburg", 1100.0, 150_000),
        ("09183", "Landkreis", "Mühldorf a.Inn", 800.0, 115_000),
        ("09262", "Kreisfreie Stadt", "Passau, Stadt", 70.0, 53_000),
        ("09263", "Landkreis", "Passau", 1500.0, 190_000),
    ]
    return pd.DataFrame(rows, columns=["key", "kind", "name", "area_km2", "population"])


@pytest.fixture
def kba() -> pd.DataFrame:
    """KBA has Hanau as its own district and one district for Trier and Trier-Saarburg."""
    keys = ["01001", "03403", "03458", "06415", "06435", "07211", "09183", "09262", "09263"]
    return pd.DataFrame({
        "key": keys,
        "zb_name": keys,
        "pkw_total": [1000 * (i + 1) for i in range(len(keys))],
        "bev": [100 * (i + 1) for i in range(len(keys))],
        "phev": [50 * (i + 1) for i in range(len(keys))],
    })


@pytest.fixture
def register() -> pd.DataFrame:
    rows = [
        # name, kind, points, status
        ("Kreisfreie Stadt Flensburg", "Normalladeeinrichtung", 2, "In Betrieb"),
        ("Kreisfreie Stadt Flensburg", "Schnellladeeinrichtung", 4, "In Betrieb"),
        ("Kreisfreie Stadt Oldenburg (Oldb)", "Normalladeeinrichtung", 2, "In Betrieb"),
        ("Landkreis Oldenburg", "Normalladeeinrichtung", 3, "In Betrieb"),
        ("Kreisfreie Stadt Hanau", "Normalladeeinrichtung", 5, "In Betrieb"),
        ("Landkreis Main-Kinzig-Kreis", "Normalladeeinrichtung", 7, "In Betrieb"),
        ("Kreisfreie Stadt Trier", "Normalladeeinrichtung", 4, "In Betrieb"),
        ("Landkreis Trier-Saarburg", "Normalladeeinrichtung", 6, "In Betrieb"),
        ("Landkreis Mühldorf a. Inn", "Normalladeeinrichtung", 2, "In Betrieb"),
        ("Landkreis Mühldorf a. Inn", "Normalladeeinrichtung", 9, "In Wartung"),
        ("Kreisfreie Stadt Passau", "Normalladeeinrichtung", 1, "In Betrieb"),
        ("Landkreis Passau", "Schnellladeeinrichtung", 8, "In Betrieb"),
    ]
    return pd.DataFrame(rows, columns=["kreis_name", "kind", "n_points", "status"])
