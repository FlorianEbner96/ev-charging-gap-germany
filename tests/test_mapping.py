import pandas as pd
import pytest

from ev_gap.mapping import build_interactive_map, plot_static_map, save_interactive_map, status_codes
from ev_gap.ranking import rank_districts


@pytest.fixture
def ranking() -> pd.DataFrame:
    gaps = pd.DataFrame({
        "key": ["07336", "10041", "03159", "08111"],
        "name": ["Far below", "Just below", "Near expected", "Above"],
        "bev": [1000, 2000, 3000, 4000], "population": [50_000, 60_000, 70_000, 80_000],
        "charging_points": [60, 69, 95, 150], "expected_linear": [200.0, 100.0, 100.0, 100.0],
        "gap_pct_linear": [-70.0, -31.0, -5.0, 50.0], "gap_pct_boosting": [-60.0, -20.0, -3.0, 40.0],
    })
    return rank_districts(gaps)


@pytest.fixture
def geojson(ranking) -> dict:
    def square(i):
        return [[[i, 0], [i + 1, 0], [i + 1, 1], [i, 1], [i, 0]]]
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "id": key, "properties": {"name": key}, "geometry": {"type": "MultiPolygon", "coordinates": [square(i)]}}
        for i, key in enumerate(ranking["key"])]}


def test_status_codes_separate_not_clearly_below_clearly_below_and_robust(ranking):
    codes = dict(zip(ranking["name"], status_codes(ranking)))
    assert codes == {"Far below": 2, "Just below": 1, "Near expected": 0, "Above": 0}


def test_the_interactive_map_has_one_trace_with_a_shape_for_every_district(ranking, geojson):
    figure = build_interactive_map(ranking, geojson)
    assert len(figure.data) == 1
    assert sorted(figure.data[0].locations) == sorted(ranking["key"])
    assert len(figure.data[0].customdata) == len(ranking)


def test_the_drop_down_has_three_views_and_each_view_has_a_value_for_every_district(ranking, geojson):
    figure = build_interactive_map(ranking, geojson)
    buttons = figure.layout.updatemenus[0].buttons
    assert len(buttons) == 3
    for button in buttons:
        z = button.args[0]["z"][0]
        assert len(z) == len(ranking)


def test_the_percent_view_is_capped_so_that_one_district_does_not_set_the_scale(ranking, geojson):
    z = build_interactive_map(ranking, geojson).data[0].z
    assert min(z) >= -60 and max(z) <= 60


def test_the_points_view_only_colours_clearly_below_districts(ranking, geojson):
    figure = build_interactive_map(ranking, geojson)
    z = figure.layout.updatemenus[0].buttons[1].args[0]["z"][0]
    by_name = dict(zip(ranking["name"], z))
    assert by_name["Near expected"] == 0 and by_name["Above"] == 0
    assert by_name["Far below"] > 0 and by_name["Just below"] > 0


def test_the_map_says_that_the_colour_is_not_a_measure_of_need(ranking, geojson):
    figure = build_interactive_map(ranking, geojson)
    assert "not a measure of need" in figure.layout.annotations[0].text


def test_the_html_file_works_offline(ranking, geojson, tmp_path):
    """No background tiles and no script that is loaded from the internet."""
    figure = build_interactive_map(ranking, geojson)
    assert figure.layout.map.style == "white-bg"
    html = save_interactive_map(figure, tmp_path / "map.html").read_text(encoding="utf-8")
    assert "plotly" in html.lower()
    assert "<script src=" not in html and "<script type=\"text/javascript\" src=" not in html


def test_the_static_map_is_written_as_a_picture(ranking, geojson, tmp_path):
    path = tmp_path / "map.png"
    plot_static_map(ranking, geojson, "gap_pct", "title", "label", 60, path=path)
    assert path.exists() and path.stat().st_size > 1000
