"""A small web service: the gap of one district, and an expected number of charging points for given inputs.

Start it with:  uv run uvicorn ev_gap.api:create_app --factory
Then open http://127.0.0.1:8000 (page with the map) or http://127.0.0.1:8000/docs (all endpoints).
"""

import json
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException, Path as PathParam, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ev_gap import config
from ev_gap.model import MODEL_FILE, load_model
from ev_gap.pipeline import DATA_INFO_FILE
from ev_gap.ranking import RANKING_FILE

WEB_DIR = Path(__file__).parent / "web"
MAP_FILE = config.REPORTS_DIR / "gap_map.html"
METHOD_NOTE = ("The expected number is what a typical district with the same cars, residents and density has. "
               "It is not the number of charging points that a district needs. Gaps between -30% and +30% are within the model's noise.")


class District(BaseModel):
    key: str
    name: str
    state: str | None


class DistrictGap(District):
    bev: int
    population: int
    actual: int
    expected: float
    gap_pct: float
    missing_points: float
    clearly_below: bool
    robust: bool
    rank_by_percent: int
    rank_by_points: int
    note: str = METHOD_NOTE


class Expected(BaseModel):
    bev: float
    population: float
    density: float
    expected_points: float
    typical_error_pct: float
    note: str = METHOD_NOTE


def create_app(model_path: Path = MODEL_FILE, ranking_path: Path = RANKING_FILE, map_path: Path = MAP_FILE,
               info_path: Path = DATA_INFO_FILE) -> FastAPI:
    package = load_model(model_path)
    if not ranking_path.exists():
        raise FileNotFoundError(f"{ranking_path} is missing. Run: python -m ev_gap.ranking")
    ranking = pd.read_csv(ranking_path, dtype={"key": str}).set_index("key", drop=False)
    # Reference dates of the data, written by the pipeline. Missing in older runs, then the answer says null.
    data_info = json.loads(info_path.read_text(encoding="utf-8")) if info_path.exists() else None

    app = FastAPI(
        title="EV charging gap in Germany",
        description="Gap between the actual and the expected number of public charging points per district. " + METHOD_NOTE,
        version="0.1.0",
    )

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "districts": int(len(ranking)), "typical_error_pct": package["typical_error_pct"],
                "data_dates": data_info}

    @app.get("/districts", response_model=list[District])
    def districts() -> list[District]:
        """All districts, sorted by name, for a drop-down menu."""
        table = ranking.sort_values("name")
        return [District(key=row.key, name=row.name, state=row.state) for row in table.itertuples()]

    @app.get("/districts/{key}", response_model=DistrictGap)
    def district(key: str = PathParam(pattern=r"^\d{5}$", description="five digit district key, for example 07335")) -> DistrictGap:
        """Actual and expected charging points of one district. The expected value comes from a model that did not see the district."""
        if key not in ranking.index:
            raise HTTPException(status_code=404, detail=f"No district with key {key}")
        row = ranking.loc[key]
        return DistrictGap(
            key=key, name=row["name"], state=row["state"], bev=int(row["bev"]), population=int(row["population"]),
            actual=int(row["actual"]), expected=round(float(row["expected"]), 1), gap_pct=round(float(row["gap_pct"]), 1),
            missing_points=round(float(row["missing_points"]), 1), clearly_below=bool(row["clearly_below"]),
            robust=bool(row["robust"]), rank_by_percent=int(row["rank_pct"]), rank_by_points=int(row["rank_points"]),
        )

    @app.get("/expected", response_model=Expected)
    def expected(
        bev: float = Query(gt=0, le=200_000, description="battery electric cars"),
        population: float = Query(ge=1_000, le=5_000_000, description="residents"),
        density: float = Query(gt=0, le=20_000, description="residents per square kilometre"),
    ) -> Expected:
        """What-if: how many public charging points does a typical district with these numbers have?"""
        inputs = pd.DataFrame([{"bev": bev, "population": population, "density": density}])[package["features"]]
        points = float(package["model"].predict(inputs)[0])
        return Expected(bev=bev, population=population, density=density, expected_points=round(points, 1),
                        typical_error_pct=package["typical_error_pct"])

    @app.get("/map", include_in_schema=False)
    def map_page():
        if not map_path.exists():
            raise HTTPException(status_code=404, detail="The map is missing. Run: python -m ev_gap.mapping")
        return FileResponse(map_path, media_type="text/html")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(WEB_DIR / "index.html", media_type="text/html")

    return app
