"""Тести HTTP-API розльоту шарів стіни (POST /api/motion/state), режим
«Будівництво» — прив'язаний до кімнати. Демо-стенд руху (режим
«Механізми», незалежний від кімнати) — окремо, tests/test_server_mechanism.py."""

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


def _get(server, path: str):
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(_url(server, path), timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _make_room(server):
    _post(
        server,
        "/api/room",
        {
            "points": [[0, 0], [4000, 0], [4000, 3000], [0, 3000]],
            "wall_height": 2700,
            "wall_thickness": 200,
            "material_name": "Бетон C25/30",
            "room_name": "Кухня",
        },
    )


def test_motion_state_requires_room(server):
    status, data = _post(server, "/api/motion/state", {"ts": [0.0]})
    assert status == 400
    assert "error" in data


def test_motion_state_rejects_empty_ts(server):
    _make_room(server)
    status, _ = _post(server, "/api/motion/state", {"ts": []})
    assert status == 400


def test_motion_state_rejects_missing_ts(server):
    _make_room(server)
    status, _ = _post(server, "/api/motion/state", {})
    assert status == 400


def test_motion_state_rejects_too_many_frames(server):
    _make_room(server)
    status, _ = _post(server, "/api/motion/state", {"ts": list(range(2001))})
    assert status == 400


def test_motion_state_returns_one_frame_per_requested_t(server):
    _make_room(server)
    status, data = _post(server, "/api/motion/state", {"ts": [0.0, 1.0, 2.5]})
    assert status == 200
    frames = data["frames"]
    assert [f["t"] for f in frames] == [0.0, 1.0, 2.5]


def test_motion_state_has_no_parts_when_no_wall_selected(server):
    """Без обраної стіни план порожній — нема шестерень (вони в
    окремому режимі «Механізми»), нема й стіни (нічого не обрано)."""
    _make_room(server)
    _, data = _post(server, "/api/motion/state", {"ts": [1.0]})
    assert data["frames"][0]["parts"] == {}


# --------------------------------------------------- розліт шарів стіни

def _set_wall_layers(server, wall_index=0):
    return _post(
        server,
        "/api/heat/wall_layers",
        {
            "wall_index": wall_index,
            "layers": [
                {"material_name": "Штукатурка гіпсова", "thickness_mm": 15},
                {"material_name": "Бетон C25/30", "thickness_mm": 200},
                {"material_name": "Мінеральна вата (кам'яна)", "thickness_mm": 100},
            ],
        },
    )


def test_scene3d_has_layers_flag_reflects_heat_state(server):
    _make_room(server)
    _, scene = _get(server, "/api/scene3d")
    assert scene["room"]["walls"][0]["has_layers"] is False

    _set_wall_layers(server, 0)
    _, scene = _get(server, "/api/scene3d")
    assert scene["room"]["walls"][0]["has_layers"] is True
    assert scene["room"]["walls"][1]["has_layers"] is False


def test_select_wall_requires_layers_defined(server):
    _make_room(server)
    status, data = _post(server, "/api/motion/select_wall", {"wall_index": 0})
    assert status == 400
    assert "error" in data


def test_select_wall_rejects_bad_index(server):
    _make_room(server)
    _set_wall_layers(server, 0)
    status, _ = _post(server, "/api/motion/select_wall", {"wall_index": 99})
    assert status == 400


def test_select_wall_then_scene3d_exposes_exploded_wall(server):
    _make_room(server)
    _set_wall_layers(server, 0)
    status, data = _post(server, "/api/motion/select_wall", {"wall_index": 0})
    assert status == 200
    assert data["wall_index"] == 0

    _, scene = _get(server, "/api/scene3d")
    exploded = scene["motion_exploded_wall"]
    assert exploded is not None
    assert exploded["wall_index"] == 0
    names = [layer["name"] for layer in exploded["layers"]]
    assert names == ["Штукатурка гіпсова", "Бетон C25/30", "Мінеральна вата (кам'яна)"]
    for layer in exploded["layers"]:
        assert "motion_name" in layer and "thickness_mm" in layer


def test_select_wall_null_clears_selection(server):
    _make_room(server)
    _set_wall_layers(server, 0)
    _post(server, "/api/motion/select_wall", {"wall_index": 0})
    status, data = _post(server, "/api/motion/select_wall", {"wall_index": None})
    assert status == 200
    assert data["wall_index"] is None
    _, scene = _get(server, "/api/scene3d")
    assert scene["motion_exploded_wall"] is None


def test_motion_state_includes_wall_layers_once_selected(server):
    _make_room(server)
    _set_wall_layers(server, 0)
    _post(server, "/api/motion/select_wall", {"wall_index": 0})

    _, data = _post(server, "/api/motion/state", {"ts": [0.0, 2.0]})
    parts_at_2s = data["frames"][1]["parts"]
    assert set(parts_at_2s.keys()) == {"0:Штукатурка гіпсова", "1:Бетон C25/30", "2:Мінеральна вата (кам'яна)"}

    # перший шар нерухомий: матриця в t=2с — одинична
    first_layer_matrix = parts_at_2s["0:Штукатурка гіпсова"]["matrix"]
    assert first_layer_matrix == pytest.approx([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1], abs=1e-9)


def test_removing_wall_layers_clears_explosion_selection(server):
    _make_room(server)
    _set_wall_layers(server, 0)
    _post(server, "/api/motion/select_wall", {"wall_index": 0})

    _post(server, "/api/heat/wall_layers", {"wall_index": 0, "layers": []})

    _, scene = _get(server, "/api/scene3d")
    assert scene["motion_exploded_wall"] is None


def test_heat_reset_clears_explosion_selection(server):
    _make_room(server)
    _set_wall_layers(server, 0)
    _post(server, "/api/motion/select_wall", {"wall_index": 0})

    _post(server, "/api/heat/reset", {})

    _, scene = _get(server, "/api/scene3d")
    assert scene["motion_exploded_wall"] is None
