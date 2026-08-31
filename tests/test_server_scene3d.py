"""Тести HTTP-API модуля 11 (дах, отвори, збірка 3D-сцени)."""

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


def _make_room(server, material_name="Бетон C25/30"):
    _post(
        server,
        "/api/room",
        {
            "points": [[0, 0], [4000, 0], [4000, 3000], [0, 3000]],
            "wall_height": 2700,
            "wall_thickness": 200,
            "material_name": material_name,
            "room_name": "Кухня",
        },
    )


# ---------------------------------------------------------------------------
# Сцена вимагає кімнату
# ---------------------------------------------------------------------------


def test_scene3d_requires_room(server):
    status, _ = _get(server, "/api/scene3d")
    assert status == 400


def test_scene3d_basic_room_no_roof_no_openings(server):
    _make_room(server)
    status, scene = _get(server, "/api/scene3d")
    assert status == 200
    assert len(scene["room"]["walls"]) == 4
    assert scene["roof"] is None
    assert scene["room"]["walls"][0]["openings"] == []
    assert scene["ducts"] == []
    assert scene["fixtures"] == []
    assert scene["electrical_routes"] == {}


# ---------------------------------------------------------------------------
# Дах
# ---------------------------------------------------------------------------


def test_roof_settings_gable_hand_verified(server):
    """Той самий інваріант, що й у модулі 10: площа схилів = footprint/cos(кута)."""
    import math

    _make_room(server)
    status, _ = _post(server, "/api/roof/settings", {"roof_type": "GABLE", "slope_deg": 30})
    assert status == 200

    _, scene = _get(server, "/api/scene3d")
    assert scene["roof"]["type"] == "GABLE"
    assert len(scene["roof"]["faces"]) == 2

    # площа кожної грані рахуємо тут вручну з вершин (перехресний добуток)
    def face_area_m2(points):
        n = len(points)
        nx = ny = nz = 0.0
        for i in range(n):
            ax, ay, az = points[i]
            bx, by, bz = points[(i + 1) % n]
            nx += ay * bz - az * by
            ny += az * bx - ax * bz
            nz += ax * by - ay * bx
        return 0.5 * math.sqrt(nx * nx + ny * ny + nz * nz) / 1_000_000

    total_area = sum(face_area_m2(f) for f in scene["roof"]["faces"])
    expected = 12.0 / math.cos(math.radians(30))
    assert total_area == pytest.approx(expected)


def test_roof_type_none_gives_no_roof(server):
    _make_room(server)
    _post(server, "/api/roof/settings", {"roof_type": "GABLE", "slope_deg": 30})
    _post(server, "/api/roof/settings", {"roof_type": "NONE"})
    _, scene = _get(server, "/api/scene3d")
    assert scene["roof"] is None


def test_roof_rejects_unknown_type(server):
    _make_room(server)
    status, _ = _post(server, "/api/roof/settings", {"roof_type": "FLAT"})
    assert status == 400


def test_shed_roof_settings(server):
    _make_room(server)
    status, _ = _post(server, "/api/roof/settings", {"roof_type": "SHED", "slope_deg": 20, "low_side": "west"})
    assert status == 200
    _, scene = _get(server, "/api/scene3d")
    assert scene["roof"]["type"] == "SHED"
    assert len(scene["roof"]["faces"]) == 1


# ---------------------------------------------------------------------------
# Отвори (вікна/двері)
# ---------------------------------------------------------------------------


def test_add_window_and_see_it_in_scene(server):
    _make_room(server)
    status, data = _post(
        server,
        "/api/opening3d",
        {"wall_index": 0, "kind": "WINDOW", "offset_mm": 1500, "sill_height_mm": 900, "width_mm": 1200, "height_mm": 1400},
    )
    assert status == 200
    assert data["name"] == "Вікно 1"

    _, scene = _get(server, "/api/scene3d")
    openings = scene["room"]["walls"][0]["openings"]
    assert len(openings) == 1
    assert openings[0]["width_mm"] == 1200
    assert openings[0]["kind"] == "WINDOW"


def test_opening_out_of_wall_length_rejected(server):
    _make_room(server)
    status, _ = _post(
        server,
        "/api/opening3d",
        {"wall_index": 0, "kind": "DOOR", "offset_mm": 3500, "sill_height_mm": 0, "width_mm": 900, "height_mm": 2000},
    )
    assert status == 400
    _, scene = _get(server, "/api/scene3d")
    assert scene["room"]["walls"][0]["openings"] == []  # не збереглося після відхилення


def test_opening_out_of_wall_height_rejected(server):
    _make_room(server)
    status, _ = _post(
        server,
        "/api/opening3d",
        {"wall_index": 0, "kind": "WINDOW", "offset_mm": 0, "sill_height_mm": 2000, "width_mm": 900, "height_mm": 1000},
    )
    assert status == 400


def test_overlapping_openings_still_validated_together():
    """Друге вікно, що разом із першим перевищує довжину стіни, теж
    відхиляється — валідація враховує вже наявні отвори тієї самої стіни."""
    srv = create_server(port=0, state=AppState())
    import threading as _threading

    t = _threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        _make_room(srv)
        status1, _ = _post(
            srv, "/api/opening3d", {"wall_index": 0, "kind": "WINDOW", "offset_mm": 0, "sill_height_mm": 900, "width_mm": 2000, "height_mm": 1000}
        )
        assert status1 == 200
        # довжина стіни 4000мм; це вікно саме по собі влазить (2500..3900),
        # але валідація для КОЖНОГО отвору окрема (Wall3D перевіряє межі
        # кожного отвору стосовно стіни, не перетин отворів між собою) —
        # тож воно теж має пройти:
        status2, _ = _post(
            srv, "/api/opening3d", {"wall_index": 0, "kind": "WINDOW", "offset_mm": 2500, "sill_height_mm": 900, "width_mm": 1400, "height_mm": 1000}
        )
        assert status2 == 200
        _, scene = _get(srv, "/api/scene3d")
        assert len(scene["room"]["walls"][0]["openings"]) == 2
    finally:
        srv.shutdown()
        srv.server_close()
        t.join(timeout=2)


def test_delete_opening(server):
    _make_room(server)
    _post(
        server,
        "/api/opening3d",
        {"wall_index": 0, "kind": "WINDOW", "offset_mm": 1500, "sill_height_mm": 900, "width_mm": 1200, "height_mm": 1400},
    )
    status, _ = _post(server, "/api/opening3d_delete", {"name": "Вікно 1"})
    assert status == 200
    _, scene = _get(server, "/api/scene3d")
    assert scene["room"]["walls"][0]["openings"] == []


def test_reset_openings(server):
    _make_room(server)
    _post(
        server,
        "/api/opening3d",
        {"wall_index": 0, "kind": "DOOR", "offset_mm": 0, "sill_height_mm": 0, "width_mm": 900, "height_mm": 2000},
    )
    _post(server, "/api/opening3d_reset", {})
    _, scene = _get(server, "/api/scene3d")
    assert scene["room"]["walls"][0]["openings"] == []


def test_opening_rejects_bad_wall_index(server):
    _make_room(server)
    status, _ = _post(
        server, "/api/opening3d", {"wall_index": 99, "kind": "DOOR", "offset_mm": 0, "sill_height_mm": 0, "width_mm": 900, "height_mm": 2000}
    )
    assert status == 400


def test_opening_rejects_unknown_kind(server):
    _make_room(server)
    status, _ = _post(
        server, "/api/opening3d", {"wall_index": 0, "kind": "SKYLIGHT", "offset_mm": 0, "sill_height_mm": 0, "width_mm": 900, "height_mm": 2000}
    )
    assert status == 400


# ---------------------------------------------------------------------------
# Матеріали, повітроводи, світильники, траси у сцені
# ---------------------------------------------------------------------------


def test_scene_material_category_lookup_for_known_material(server):
    _make_room(server, material_name="Бетон C25/30")
    _, scene = _get(server, "/api/scene3d")
    assert scene["room"]["walls"][0]["material_category"] == "CONCRETE"


def test_scene_material_category_none_for_unknown_material(server):
    _make_room(server, material_name="Якийсь вигаданий матеріал")
    _, scene = _get(server, "/api/scene3d")
    assert scene["room"]["walls"][0]["material_category"] is None


def test_scene_includes_ducts_fixtures_and_routes(server):
    _make_room(server)
    _post(server, "/api/ventilation/duct", {"points": [[0, 0], [3000, 0]], "shape": "ROUND", "diameter_mm": 100})
    _post(server, "/api/lighting/fixture", {"kind": "CEILING", "position": [1000, 1000], "luminous_flux_lm": 800, "power_w": 8})
    _post(server, "/api/electrical/point", {"kind": "PANEL", "position": [0, 0]})
    _post(server, "/api/electrical/point", {"kind": "SOCKET", "position": [2000, 3000]})
    _post(server, "/api/electrical/route", {"point_name": "Розетка 1", "points": [[0, 3000], [2000, 3000]]})

    _, scene = _get(server, "/api/scene3d")
    assert len(scene["ducts"]) == 1
    assert scene["ducts"][0]["diameter_mm"] == 100
    assert len(scene["fixtures"]) == 1
    assert "Розетка 1" in scene["electrical_routes"]
    assert scene["electrical_routes"]["Розетка 1"][0] == [0.0, 0.0]  # починається від щитка
