"""Тести HTTP-API модуля 14: /api/project/export, /api/project/import."""

import json
import threading

import pytest

from web.project_io import PROJECT_FORMAT
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
    return f"http://127.0.0.1:{server.server_address[1]}{path}"


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


def _make_room(server):
    _post(
        server, "/api/room",
        {"points": [[0, 0], [4000, 0], [4000, 3000], [0, 3000]], "wall_height": 2700, "wall_thickness": 200,
         "material_name": "Бетон C25/30", "room_name": "Кухня"},
    )


def test_export_empty(server):
    status, data = _get(server, "/api/project/export")
    assert status == 200
    assert data["format"] == PROJECT_FORMAT
    assert data["room"] is None


def test_export_after_room_and_roof(server):
    _make_room(server)
    _post(server, "/api/roof/settings", {"roof_type": "GABLE", "slope_deg": 30})
    status, data = _get(server, "/api/project/export")
    assert status == 200
    assert data["room"]["room_name"] == "Кухня"
    assert data["roof"]["roof_type"] == "GABLE"


def test_import_restores_state(server):
    _make_room(server)
    _post(server, "/api/lighting/fixture", {"kind": "CEILING", "position": [1000, 1000], "luminous_flux_lm": 800, "power_w": 8})
    _, exported = _get(server, "/api/project/export")

    # інший сервер (інший AppState) — "нова інсталяція застосунку"
    srv2 = create_server(port=0, state=AppState())
    import threading as _threading

    t2 = _threading.Thread(target=srv2.serve_forever, daemon=True)
    t2.start()
    try:
        status, _ = _post(srv2, "/api/project/import", exported)
        assert status == 200
        status, room = _get(srv2, "/api/room")
        assert status == 200
        assert room["name"] == "Кухня"
        _, reexported = _get(srv2, "/api/project/export")
        assert reexported == exported
    finally:
        srv2.shutdown()
        srv2.server_close()
        t2.join(timeout=2)


def test_import_rejects_bad_format(server):
    status, data = _post(server, "/api/project/import", {"format": "щось інше"})
    assert status == 400
    assert "error" in data


def test_import_rejects_malformed_openings(server):
    _make_room(server)
    _, exported = _get(server, "/api/project/export")
    exported["openings3d"] = [
        {"name": "Вікно 1", "wall_index": 0, "kind": "WINDOW", "offset_mm": 3900, "sill_height_mm": 900, "width_mm": 1200, "height_mm": 1400}
    ]
    status, data = _post(server, "/api/project/import", exported)
    assert status == 400
    assert "error" in data
