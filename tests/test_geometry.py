import json

import pytest

from ev_gap.geometry import build_geojson, decode_arcs, merge_shapes, polygons, read_shapes, ring_coordinates


@pytest.fixture
def topology() -> dict:
    """Two squares side by side, A on the left and B on the right. The border between them is arc 1.

    Before the transform the corners are whole numbers: A is (0,0) to (2,2) and B is (2,0) to (4,2).
    A walks the border backwards (arc ~1), B walks it forwards (arc 1), as neighbours do.
    """
    return {
        "type": "Topology",
        "transform": {"scale": [0.5, 0.5], "translate": [10.0, 50.0]},
        "arcs": [
            [[2, 2], [-2, 0], [0, -2], [2, 0]],  # arc 0: (2,2) -> (0,2) -> (0,0) -> (2,0)
            [[2, 2], [0, -2]],                   # arc 1: (2,2) -> (2,0), the shared border
            [[2, 0], [2, 0], [0, 2], [-2, 0]],   # arc 2: (2,0) -> (4,0) -> (4,2) -> (2,2)
        ],
        "objects": {"counties": {"type": "GeometryCollection", "geometries": [
            {"type": "Polygon", "id": "01001", "properties": {"name": "A"}, "arcs": [[~1, 0]]},
            {"type": "Polygon", "id": 1002, "properties": {"name": "B"}, "arcs": [[2, 1]]},
        ]}},
    }


def test_arcs_are_decoded_with_the_transform(topology):
    arcs = decode_arcs(topology)
    assert arcs[0] == [[11.0, 51.0], [10.0, 51.0], [10.0, 50.0], [11.0, 50.0]]
    assert arcs[1] == [[11.0, 51.0], [11.0, 50.0]]


def test_a_ring_is_closed_and_shared_points_are_not_repeated(topology):
    arcs = decode_arcs(topology)
    ring = ring_coordinates([2, 1], arcs)  # square B
    assert ring == [[11.0, 50.0], [12.0, 50.0], [12.0, 51.0], [11.0, 51.0], [11.0, 50.0]]
    assert ring[0] == ring[-1]


def test_a_negative_index_uses_the_arc_in_reverse(topology):
    arcs = decode_arcs(topology)
    ring = ring_coordinates([~1, 0], arcs)  # square A starts with the border walked backwards
    assert ring == [[11.0, 50.0], [11.0, 51.0], [10.0, 51.0], [10.0, 50.0], [11.0, 50.0]]


def test_polygon_and_multipolygon_are_both_read(topology):
    arcs = decode_arcs(topology)
    single = polygons({"type": "Polygon", "arcs": [[~1, 0]]}, arcs)
    multi = polygons({"type": "MultiPolygon", "arcs": [[[~1, 0]], [[2, 1]]]}, arcs)
    assert len(single) == 1 and len(multi) == 2
    assert single[0][0][0] == single[0][0][-1]


def test_ids_are_padded_to_five_digits(topology, tmp_path):
    path = tmp_path / "topo.json"
    path.write_text(json.dumps(topology), encoding="utf-8")
    shapes = read_shapes(path)
    assert set(shapes) == {"01001", "01002"}
    assert shapes["01002"]["name"] == "B"


def test_old_districts_are_added_to_the_district_they_were_merged_into(topology, tmp_path):
    path = tmp_path / "topo.json"
    path.write_text(json.dumps(topology), encoding="utf-8")
    merged = merge_shapes(read_shapes(path), merges={"01002": "01001"})
    assert set(merged) == {"01001"}
    assert len(merged["01001"]["polygons"]) == 2


def test_geojson_has_one_feature_per_requested_key(topology, tmp_path):
    path = tmp_path / "topo.json"
    path.write_text(json.dumps(topology), encoding="utf-8")
    geojson = build_geojson(read_shapes(path), ["01002", "01001"])
    assert [f["id"] for f in geojson["features"]] == ["01002", "01001"]
    assert all(f["geometry"]["type"] == "MultiPolygon" for f in geojson["features"])


def test_a_district_without_shape_raises(topology, tmp_path):
    path = tmp_path / "topo.json"
    path.write_text(json.dumps(topology), encoding="utf-8")
    with pytest.raises(ValueError, match="99999"):
        build_geojson(read_shapes(path), ["01001", "99999"])
