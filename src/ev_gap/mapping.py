"""Maps of the gaps: an interactive HTML map (works offline) and static pictures for slides.

The colour shows the distance from the number of charging points that a typical district of the
same size has. It does not show how many charging points a district needs.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # no window needed, the maps are written to files
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
from matplotlib.collections import PolyCollection  # noqa: E402
from matplotlib.colors import TwoSlopeNorm  # noqa: E402

from ev_gap import config  # noqa: E402
from ev_gap.geometry import load_geojson  # noqa: E402
from ev_gap.ranking import load_gaps, rank_districts  # noqa: E402

GAP_LIMIT = 60  # the colour scale of the gap stops at -60% and +60%
POINTS_LIMIT = 600  # and at 600 missing charging points
GREY = "#d9d9d9"
LIGHT_RED, DARK_RED = "#f4a582", "#b2182b"
DIVERGING = [[0, "#b2182b"], [0.25, "#f4a582"], [0.5, "#f7f7f7"], [0.75, "#92c5de"], [1, "#2166ac"]]
MISSING_SCALE = [[0, GREY], [0.0001, "#fee0d2"], [0.5, "#fb6a4a"], [1, "#a50f15"]]
STATUS_SCALE = [[0, GREY], [0.25, GREY], [0.25, LIGHT_RED], [0.75, LIGHT_RED], [0.75, DARK_RED], [1, DARK_RED]]
NOTE = ("Colour = distance from what a typical district of this size has, not a measure of need. "
        "The typical model error is about 21%, so only gaps beyond -30% count. Sources: Bundesnetzagentur, KBA, Destatis.")


def status_codes(ranking: pd.DataFrame) -> pd.Series:
    """0: not clearly below, 1: clearly below, 2: clearly below and robust (both models agree)."""
    return ranking["clearly_below"].astype(int) + ranking["robust"].astype(int)


def hover_table(ranking: pd.DataFrame) -> np.ndarray:
    status = status_codes(ranking).map({0: "not clearly below", 1: "clearly below", 2: "clearly below (robust)"})
    return np.column_stack([
        ranking["name"], ranking["state"], ranking["actual"].round(0).astype(int), ranking["expected"].round(0).astype(int),
        ranking["gap_pct"].round(0).astype(int), ranking["missing_points"].round(0).astype(int),
        ranking["rank_pct"], ranking["rank_points"], status,
    ])


def build_interactive_map(ranking: pd.DataFrame, geojson: dict) -> go.Figure:
    """One map with three views, chosen in a drop-down menu."""
    views = {
        "Gap in percent": dict(
            z=ranking["gap_pct"].clip(-GAP_LIMIT, GAP_LIMIT), colorscale=DIVERGING, zmin=-GAP_LIMIT, zmax=GAP_LIMIT,
            title="Gap, %<br>(red: fewer points<br>than expected)", tickvals=[-60, -30, 0, 30, 60], ticktext=["-60", "-30", "0", "+30", "+60"]),
        "Missing charging points (clearly below districts)": dict(
            z=ranking["missing_to_expected"].where(ranking["clearly_below"], 0).clip(upper=POINTS_LIMIT), colorscale=MISSING_SCALE,
            zmin=0, zmax=POINTS_LIMIT, title="Missing points<br>(grey: not clearly<br>below)", tickvals=[0, 200, 400, 600], ticktext=["0", "200", "400", "600+"]),
        "Clearly below: robust or not": dict(
            z=status_codes(ranking), colorscale=STATUS_SCALE, zmin=0, zmax=2,
            title="", tickvals=[0.25, 1, 1.75], ticktext=["not clearly below", "clearly below", "robust (both<br>models agree)"]),
    }
    first = next(iter(views.values()))
    figure = go.Figure(go.Choroplethmap(
        geojson=geojson, locations=ranking["key"], z=first["z"], colorscale=first["colorscale"], zmin=first["zmin"], zmax=first["zmax"],
        marker=dict(line=dict(width=0.3, color="white"), opacity=1),
        customdata=hover_table(ranking),
        hovertemplate=("<b>%{customdata[0]}</b> (%{customdata[1]})<br>actual %{customdata[2]} charging points, expected %{customdata[3]}<br>"
                       "gap %{customdata[4]}%, missing points %{customdata[5]}<br>rank by percent %{customdata[6]}, by points %{customdata[7]}<br>"
                       "%{customdata[8]}<extra></extra>"),
        colorbar=dict(title=dict(text=first["title"]), tickvals=first["tickvals"], ticktext=first["ticktext"], len=0.6, thickness=14),
    ))
    buttons = [dict(
        label=label, method="restyle",
        args=[{"z": [list(view["z"])], "colorscale": [view["colorscale"]], "zmin": [view["zmin"]], "zmax": [view["zmax"]],
               "colorbar.title.text": [view["title"]], "colorbar.tickvals": [view["tickvals"]], "colorbar.ticktext": [view["ticktext"]]}],
    ) for label, view in views.items()]
    figure.update_layout(
        title=dict(text="Public charging points compared with the expected number, per district", x=0.02),
        # "white-bg" is a map without background tiles, so nothing is downloaded and it works offline
        map=dict(style="white-bg", center=dict(lat=51.1, lon=10.4), zoom=5.1),
        updatemenus=[dict(type="dropdown", buttons=buttons, x=0.02, y=0.93, xanchor="left", yanchor="top", showactive=True)],
        annotations=[dict(text=NOTE, x=0.02, y=0.0, xref="paper", yref="paper", showarrow=False, xanchor="left", yanchor="top", font=dict(size=11, color="#555"))],
        margin=dict(l=10, r=10, t=60, b=50), height=760, paper_bgcolor="white",
    )
    return figure


def save_interactive_map(figure: go.Figure, path: Path) -> Path:
    """One HTML file with the plotly library inside, so it opens without internet."""
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.write_html(path, include_plotlyjs=True, full_html=True, config={"displaylogo": False})
    return path


def outlines(geojson: dict) -> dict[str, list[np.ndarray]]:
    """The outer ring of every polygon of every district."""
    return {f["id"]: [np.array(polygon[0]) for polygon in f["geometry"]["coordinates"]] for f in geojson["features"]}


def plot_static_map(ranking: pd.DataFrame, geojson: dict, column: str, title: str, label: str, limit: float,
                    cmap: str = "RdBu", centre: float | None = 0.0, mask: pd.Series | None = None, path: Path | None = None):
    """Draw the districts coloured by `column`. Districts where `mask` is False are grey."""
    shapes = outlines(geojson)
    values = ranking.set_index("key")[column]
    shown = mask.set_axis(ranking["key"]) if mask is not None else pd.Series(True, index=ranking["key"])
    norm = TwoSlopeNorm(vmin=-limit, vcenter=centre, vmax=limit) if centre is not None else plt.Normalize(0, limit)
    colormap = plt.get_cmap(cmap)

    polygons, colours = [], []
    for key, rings in shapes.items():
        colour = colormap(norm(values[key])) if shown[key] else GREY
        for ring in rings:
            polygons.append(ring)
            colours.append(colour)

    fig, ax = plt.subplots(figsize=(6.5, 8.5))
    ax.add_collection(PolyCollection(polygons, facecolors=colours, edgecolors="white", linewidths=0.25))
    ax.autoscale_view()
    ax.set_aspect(1 / np.cos(np.radians(51)))  # at this latitude a degree of longitude is shorter
    ax.axis("off")
    ax.set_title(title, fontsize=12)
    scalar = plt.cm.ScalarMappable(norm=norm, cmap=colormap)
    colourbar = fig.colorbar(scalar, ax=ax, shrink=0.55, pad=0.01)
    colourbar.set_label(label)
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=200, bbox_inches="tight")
    return fig


def run(reports_dir: Path = config.REPORTS_DIR) -> None:
    ranking = rank_districts(load_gaps())
    geojson = load_geojson(ranking["key"].tolist())
    html = save_interactive_map(build_interactive_map(ranking, geojson), reports_dir / "gap_map.html")
    plot_static_map(ranking, geojson, "gap_pct", "Gap: actual compared with expected charging points", "Gap, %", GAP_LIMIT,
                    path=reports_dir / "gap_map_percent.png")
    plot_static_map(ranking.assign(missing=ranking["missing_to_expected"].clip(upper=POINTS_LIMIT)), geojson, "missing",
                    "Missing charging points in the clearly below districts", "Missing points (capped at 600)", POINTS_LIMIT,
                    cmap="Reds", centre=None, mask=ranking["clearly_below"], path=reports_dir / "gap_map_points.png")
    print(f"written: {html} ({html.stat().st_size / 1e6:.1f} MB) and two PNG maps in {reports_dir}")


if __name__ == "__main__":
    run()
