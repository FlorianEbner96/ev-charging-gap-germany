"""Tests for the layout parsing of the KBA and Destatis sheets, on small made-up sheets."""

import numpy as np
import pandas as pd
import pytest

from ev_gap.extract import parse_destatis_sheet, parse_kba_sheet


def kba_sheet(national_total: int, national_bev: int = 15) -> pd.DataFrame:
    """12 columns like the real sheet: state in column 1, key and name in column 3, counts after that."""
    nan = np.nan
    return pd.DataFrame([
        [nan, "BADEN-WUERTTEMBERG", "RB STUTTGART", "08111 STUTTGART,STADT", 100, 40, 30, 1, 20, 8, 5, 4],
        [nan, nan, nan, "08115 BOEBLINGEN", 200, 80, 60, 2, 40, 16, 10, 8],
        [nan, nan, "RB ZUSAMMEN", nan, 300, 120, 90, 3, 60, 24, 15, 12],
        [nan, "BADEN-WUERTTEMBERG INSGESAMT", nan, nan, 300, 120, 90, 3, 60, 24, 15, 12],
        [nan, "SONSTIGE", nan, nan, 7, 0, 0, 0, 0, 0, 0, 0],
        [nan, "DEUTSCHLAND INSGESAMT", nan, nan, national_total, 120, 90, 3, 60, 24, national_bev, 12],
    ])


def test_parse_kba_sheet_keeps_only_district_rows():
    districts = parse_kba_sheet(kba_sheet(national_total=307))
    assert districts["key"].tolist() == ["08111", "08115"]
    assert districts["zb_name"].tolist() == ["STUTTGART,STADT", "BOEBLINGEN"]
    assert districts["bev"].tolist() == [5, 10]
    assert districts["phev"].tolist() == [8, 16]


def test_parse_kba_sheet_raises_if_districts_do_not_add_up():
    with pytest.raises(ValueError, match="national total"):
        parse_kba_sheet(kba_sheet(national_total=999))


def test_parse_kba_sheet_raises_if_the_battery_electric_cars_do_not_add_up():
    with pytest.raises(ValueError, match="national total.*bev"):
        parse_kba_sheet(kba_sheet(national_total=307, national_bev=999))


def test_parse_destatis_sheet_drops_state_rows():
    raw = pd.DataFrame([
        ["01", "Schleswig-Holstein", None, None, None, None, None, None, None],
        ["01001", "Kreisfreie Stadt", "Flensburg, Stadt", "DEF01", 56.73, 96326, 47651, 48675, 1698],
        ["01051", "Kreis", "Dithmarschen", "DEF05", 1428.17, 133460, 65838, 67622, 93],
        ["072", "früher: Reg.-Bez. Trier", None, None, None, None, None, None, None],
    ])
    kreise = parse_destatis_sheet(raw)
    assert kreise["key"].tolist() == ["01001", "01051"]
    assert kreise["population"].tolist() == [96326.0, 133460.0]
    assert list(kreise.columns) == ["key", "kind", "name", "area_km2", "population"]
