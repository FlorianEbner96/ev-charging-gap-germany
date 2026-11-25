import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from ev_gap import config
from ev_gap.api import create_app
from ev_gap.model import save_model
from ev_gap.ranking import rank_districts


@pytest.fixture
def client(tmp_path):
    """The service with a small model and a small ranking table, made on the fly."""
    rng = np.random.default_rng(1)
    n = 40
    bev = rng.integers(500, 20_000, n).astype(float)
    population = rng.integers(40_000, 600_000, n).astype(float)
    density = rng.integers(30, 3000, n).astype(float)
    points = (0.4 * bev**0.5 * population**0.5 / 30 * np.exp(rng.normal(0, 0.1, n))).round().clip(min=1)
    districts = pd.DataFrame({"bev": bev, "population": population, "density": density, config.TARGET: points})
    save_model(districts, typical_error_pct=21.1, path=tmp_path / "model.joblib")

    gaps = pd.DataFrame({
        "key": ["07335", "10041", "03159"], "name": ["Kusel", "Regionalverband Saarbrücken", "Göttingen"],
        "bev": [1262, 5000, 6000], "population": [69_334, 330_000, 330_000], "charging_points": [60, 400, 520],
        "expected_linear": [150.0, 410.0, 500.0], "gap_pct_linear": [-60.0, -2.4, 4.0], "gap_pct_boosting": [-58.0, -3.0, 5.0],
    })
    rank_districts(gaps).to_csv(tmp_path / "ranking.csv", index=False)
    (tmp_path / "map.html").write_text("<html>map</html>", encoding="utf-8")
    app = create_app(tmp_path / "model.joblib", tmp_path / "ranking.csv", tmp_path / "map.html")
    return TestClient(app)


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok" and body["districts"] == 3 and body["typical_error_pct"] == 21.1


def test_districts_are_listed_by_name(client):
    names = [d["name"] for d in client.get("/districts").json()]
    assert names == sorted(names) and "Kusel" in names


def test_one_district(client):
    body = client.get("/districts/07335").json()
    assert body["name"] == "Kusel" and body["state"] == "Rheinland-Pfalz"
    assert body["actual"] == 60 and body["expected"] == 150.0 and body["gap_pct"] == -60.0
    assert body["clearly_below"] is True and body["robust"] is True
    assert body["missing_points"] == 90.0 and body["rank_by_percent"] == 1
    assert "not the number of charging points that a district needs" in body["note"]


def test_a_district_that_is_not_clearly_below(client):
    body = client.get("/districts/10041").json()
    assert body["clearly_below"] is False and body["robust"] is False


def test_unknown_district_is_404(client):
    assert client.get("/districts/99999").status_code == 404


def test_a_key_that_is_not_five_digits_is_rejected(client):
    assert client.get("/districts/abc").status_code == 422
    assert client.get("/districts/123456").status_code == 422


def test_expected_points_for_given_inputs(client):
    body = client.get("/expected", params={"bev": 3000, "population": 150_000, "density": 300}).json()
    assert body["expected_points"] > 0
    assert body["typical_error_pct"] == 21.1


def test_more_electric_cars_give_more_expected_points(client):
    def points(bev):
        return client.get("/expected", params={"bev": bev, "population": 150_000, "density": 300}).json()["expected_points"]
    assert points(1000) < points(3000) < points(9000)


@pytest.mark.parametrize("params", [
    {"bev": 0, "population": 150_000, "density": 300},          # no cars
    {"bev": -5, "population": 150_000, "density": 300},         # negative
    {"bev": 3000, "population": 10, "density": 300},            # too few residents
    {"bev": 3000, "population": 150_000, "density": 999_999},   # impossible density
    {"bev": 3000, "population": 150_000},                       # density missing
])
def test_invalid_inputs_are_rejected(client, params):
    assert client.get("/expected", params=params).status_code == 422


def test_map_and_page_are_served(client):
    assert client.get("/map").text == "<html>map</html>"
    page = client.get("/")
    assert page.status_code == 200 and "EV charging gap in Germany" in page.text


def test_missing_map_is_a_clear_404(client, tmp_path):
    app = create_app(tmp_path / "model.joblib", tmp_path / "ranking.csv", tmp_path / "does_not_exist.html")
    response = TestClient(app).get("/map")
    assert response.status_code == 404 and "ev_gap.mapping" in response.json()["detail"]


def test_startup_without_a_model_gives_a_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="ev_gap.model"):
        create_app(tmp_path / "nope.joblib", tmp_path / "ranking.csv", tmp_path / "map.html")
