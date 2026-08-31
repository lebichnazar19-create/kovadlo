"""Тести HTTP-API модуля 3 — через справжні запити до сервера (стандартна
бібліотека: http.client), без сторонніх залежностей."""

import json
import threading

import pytest

from web.server import AppState, create_server


@pytest.fixture()
def server():
    srv = create_server(port=0, state=AppState())
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        yield srv
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join(timeout=2)


def _url(server, path: str) -> str:
    port = server.server_address[1]
    return f"http://127.0.0.1:{port}{path}"


def _get(server, path: str):
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(_url(server, path), timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _post(server, path: str, payload: dict):
    import urllib.error
    import urllib.request

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        _url(server, path), data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _get_raw(server, path: str):
    import urllib.request

    with urllib.request.urlopen(_url(server, path), timeout=5) as resp:
        return resp.status, resp.headers.get("Content-Type", ""), resp.read()


def test_index_page_is_served(server):
    status, content_type, body = _get_raw(server, "/")
    assert status == 200
    assert "text/html" in content_type
    assert b"<html" in body.lower() or b"<!doctype" in body.lower()


def test_unknown_path_returns_404(server):
    status, data = _get(server, "/nope")
    assert status == 404
    assert "error" in data


def test_room_not_found_before_drawing(server):
    status, data = _get(server, "/api/room")
    assert status == 404


def test_snap_endpoint_matches_core(server):
    from kovadlo import Point, snap_point

    status, data = _post(server, "/api/snap", {"origin": [0, 0], "target": [1000, 80], "step": 15})
    assert status == 200
    expected = snap_point(Point(0, 0), Point(1000, 80), 15)
    assert data["x"] == pytest.approx(expected.x)
    assert data["z"] == pytest.approx(expected.z)


def test_create_room_rectangle(server):
    payload = {
        "points": [[0, 0], [4000, 0], [4000, 3000], [0, 3000]],
        "wall_height": 2700,
        "wall_thickness": 200,
        "material_name": "цегла",
        "room_name": "Спальня",
    }
    status, data = _post(server, "/api/room", payload)
    assert status == 200
    assert data["name"] == "Спальня"
    assert len(data["walls"]) == 4
    assert data["floor_area_m2"] == pytest.approx(12.0)
    assert data["walls"][0]["length_mm"] == pytest.approx(4000.0)
    assert data["walls"][0]["thickness_mm"] == pytest.approx(200.0)
    assert data["walls"][0]["material"] == "цегла"

    # тепер кімната має бути доступна через GET
    status2, data2 = _get(server, "/api/room")
    assert status2 == 200
    assert data2["name"] == "Спальня"


def test_create_room_rejects_too_few_points(server):
    status, data = _post(server, "/api/room", {"points": [[0, 0], [1000, 0]]})
    assert status == 400
    assert "error" in data


def test_tiling_requires_room_first(server):
    status, data = _post(
        server,
        "/api/tiling",
        {
            "surface": "floor",
            "tile": {"width": 600, "height": 600},
            "grout": {"width_mm": 2},
        },
    )
    assert status == 400
    assert "error" in data


def test_tiling_floor(server):
    _post(server, "/api/room", {"points": [[0, 0], [1200, 0], [1200, 1200], [0, 1200]]})
    payload = {
        "surface": "floor",
        "tile": {"width": 600, "height": 600, "name": "Тест", "color": "#ffffff"},
        "grout": {"width_mm": 0, "color": "#000000"},
        "layout": {"start": [0, 0], "row_offset": "NONE", "angle": 0},
        "tiles_per_package": 2,
    }
    status, data = _post(server, "/api/tiling", payload)
    assert status == 200
    assert data["whole_tiles_count"] == 4
    assert data["cuts_count"] == 0
    assert data["total_tiles_needed"] == 4
    assert data["packages_needed"] == 2
    assert len(data["placements"]) == 4
    assert all(p["kind"] == "whole" for p in data["placements"])
    assert "Цілих плиток" in data["report_text"]


def test_tiling_wall(server):
    _post(server, "/api/room", {"points": [[0, 0], [1000, 0], [1000, 600], [0, 600]]})
    payload = {
        "surface": {"wall_index": 0},
        "tile": {"width": 600, "height": 600},
        "grout": {"width_mm": 0},
    }
    status, data = _post(server, "/api/tiling", payload)
    assert status == 200
    # стіна 0: довжина 1000 мм, висота = висота стіни (за замовчуванням 2700 мм)
    assert data["whole_tiles_count"] + data["cuts_count"] == len(data["placements"])
    assert data["cuts_count"] > 0


def test_tiling_rejects_unknown_row_offset(server):
    _post(server, "/api/room", {"points": [[0, 0], [1000, 0], [1000, 1000], [0, 1000]]})
    payload = {
        "surface": "floor",
        "tile": {"width": 600, "height": 600},
        "grout": {"width_mm": 2},
        "layout": {"row_offset": "WRONG"},
    }
    status, data = _post(server, "/api/tiling", payload)
    assert status == 400
