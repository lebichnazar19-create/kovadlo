"""Тести HTTP-API режиму «Механізми» (/api/mechanism/*) — незалежного
від кімнати демо-стенду руху (дві зчеплені шестерні + деталь, що
відлітає). На відміну від /api/motion/state (розліт стіни, режим
«Будівництво»), тут кімната не потрібна взагалі."""

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


def test_mechanism_scene_works_without_any_room(server):
    """Ключова відмінність від /api/scene3d: жодної кімнати не треба."""
    status, data = _get(server, "/api/mechanism/scene")
    assert status == 200
    names = {part["name"] for part in data["motion_rig"]}
    assert names == {"gear_a", "gear_b", "fragment"}


def test_mechanism_scene_has_no_room_related_fields(server):
    _, data = _get(server, "/api/mechanism/scene")
    assert set(data.keys()) == {"motion_rig"}


def test_mechanism_state_works_without_any_room(server):
    status, data = _post(server, "/api/mechanism/state", {"ts": [0.0, 1.0]})
    assert status == 200
    assert [f["t"] for f in data["frames"]] == [0.0, 1.0]
    assert set(data["frames"][0]["parts"].keys()) == {"gear_a", "gear_b", "fragment"}


def test_mechanism_state_rejects_empty_ts(server):
    status, _ = _post(server, "/api/mechanism/state", {"ts": []})
    assert status == 400


def test_mechanism_state_rejects_missing_ts(server):
    status, _ = _post(server, "/api/mechanism/state", {})
    assert status == 400


def test_mechanism_state_rejects_too_many_frames(server):
    status, _ = _post(server, "/api/mechanism/state", {"ts": list(range(2001))})
    assert status == 400


def test_mechanism_state_matches_scene_layout_part_names(server):
    _, scene = _get(server, "/api/mechanism/scene")
    layout_names = {part["name"] for part in scene["motion_rig"]}

    _, data = _post(server, "/api/mechanism/state", {"ts": [0.0]})
    assert set(data["frames"][0]["parts"].keys()) == layout_names


def test_mechanism_state_at_zero_is_identity_for_every_part(server):
    _, data = _post(server, "/api/mechanism/state", {"ts": [0.0]})
    identity = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
    for part in data["frames"][0]["parts"].values():
        assert part["matrix"] == pytest.approx(identity, abs=1e-9)
