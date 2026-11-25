"""District shapes for the map: decode a TopoJSON file and merge shapes to match our districts.

TopoJSON stores each border line once (an "arc") and lets the shapes point to arcs. To draw a
shape the arcs have to be decoded back into coordinates.
"""

import json
from pathlib import Path

from ev_gap import config


def decode_arcs(topology: dict) -> list[list[list[float]]]:
    """Turn the stored arcs into lists of [longitude, latitude] points."""
    transform = topology.get("transform")
    decoded = []
    for arc in topology["arcs"]:
        x = y = 0
        points = []
        for dx, dy in arc:
            x, y = x + dx, y + dy  # arcs store the difference to the previous point
            if transform:
                points.append([x * transform["scale"][0] + transform["translate"][0],
                               y * transform["scale"][1] + transform["translate"][1]])
            else:
                points.append([x, y])
        decoded.append(points)
    return decoded


def ring_coordinates(arc_indices: list[int], arcs: list) -> list[list[float]]:
    """Join the arcs of one ring. A negative index means the arc is used in reverse (index ~i)."""
    ring: list[list[float]] = []
    for index in arc_indices:
        points = arcs[index] if index >= 0 else arcs[~index][::-1]
        ring.extend(points if not ring else points[1:])  # neighbouring arcs share their end point
    return ring


def polygons(geometry: dict, arcs: list) -> list[list[list[list[float]]]]:
    """All polygons of a geometry, each as a list of rings (the first ring is the outline)."""
    if geometry["type"] == "Polygon":
        return [[ring_coordinates(ring, arcs) for ring in geometry["arcs"]]]
    if geometry["type"] == "MultiPolygon":
        return [[ring_coordinates(ring, arcs) for ring in polygon] for polygon in geometry["arcs"]]
    raise ValueError(f"Unsupported geometry type: {geometry['type']}")


def read_shapes(path: Path, object_name: str = "counties") -> dict[str, dict]:
    """Read the file: {district key: {"name": ..., "polygons": [...]}}."""
    topology = json.loads(Path(path).read_text(encoding="utf-8"))
    arcs = decode_arcs(topology)
    shapes = {}
    for geometry in topology["objects"][object_name]["geometries"]:
        key = str(geometry["id"]).zfill(5)
        shapes[key] = {"name": geometry.get("properties", {}).get("name", key), "polygons": polygons(geometry, arcs)}
    return shapes


def merge_shapes(shapes: dict[str, dict], merges: dict[str, str] | None = None) -> dict[str, dict]:
    """Add the shapes of old districts to the district they were merged into.

    The polygons are collected side by side. They are not fused into one outline.
    """
    merges = config.SHAPE_MERGES if merges is None else merges
    merged: dict[str, dict] = {}
    for key, shape in shapes.items():
        target = merges.get(key, key)
        if target in merged:
            merged[target]["polygons"] = merged[target]["polygons"] + shape["polygons"]
        else:
            merged[target] = {"name": shape["name"], "polygons": list(shape["polygons"])}
    return merged


def build_geojson(shapes: dict[str, dict], keys: list[str]) -> dict:
    """GeoJSON for the given district keys. Raises ValueError if a district has no shape."""
    missing = sorted(set(keys) - set(shapes))
    if missing:
        raise ValueError(f"No shape for districts: {missing}")
    features = [
        {"type": "Feature", "id": key, "properties": {"name": shapes[key]["name"]},
         "geometry": {"type": "MultiPolygon", "coordinates": shapes[key]["polygons"]}}
        for key in keys
    ]
    return {"type": "FeatureCollection", "features": features}


def load_geojson(keys: list[str], path: Path | None = None) -> dict:
    path = path or config.RAW_DIR / config.BOUNDARIES_FILE
    if not Path(path).exists():
        raise FileNotFoundError(f"{path} is missing. Run: python -m ev_gap.download")
    return build_geojson(merge_shapes(read_shapes(path)), keys)
