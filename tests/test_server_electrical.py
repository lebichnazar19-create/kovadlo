"""Тести HTTP-API модуля 5 (візуалізація електропроводки)."""

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


def test_state_is_empty_before_anything_placed(server):
    status, data = _get(server, "/api/electrical/state")
    assert status == 200
    assert data["panel"] is None
    assert data["points"] == []
    assert data["groups"] == []


def test_place_panel(server):
    status, data = _post(server, "/api/electrical/point", {"kind": "PANEL", "position": [100, 2900]})
    assert status == 200
    assert data["name"] == "Щиток"
    assert data["kind"] == "PANEL"

    status2, state = _get(server, "/api/electrical/state")
    assert state["panel"]["position"] == [100.0, 2900.0]


def test_place_consumption_point_autonames_and_defaults_power(server):
    status, data = _post(server, "/api/electrical/point", {"kind": "SOCKET", "position": [1000, 1000]})
    assert status == 200
    assert data["name"] == "Розетка 1"
    assert data["kind_label"] == "розетка"
    assert data["power_w"] == 100.0
    assert data["group"] is None
    assert data["has_route"] is False

    status2, data2 = _post(server, "/api/electrical/point", {"kind": "SOCKET", "position": [2000, 1000]})
    assert data2["name"] == "Розетка 2"


def test_place_point_with_explicit_power(server):
    status, data = _post(
        server, "/api/electrical/point", {"kind": "LIGHT", "position": [0, 0], "power_w": 15.0}
    )
    assert status == 200
    assert data["power_w"] == 15.0


def test_delete_point(server):
    _post(server, "/api/electrical/point", {"kind": "SOCKET", "position": [0, 0]})
    status, data = _post(server, "/api/electrical/point_delete", {"point_name": "Розетка 1"})
    assert status == 200
    _, state = _get(server, "/api/electrical/state")
    assert state["points"] == []


def test_route_requires_panel_first(server):
    _post(server, "/api/electrical/point", {"kind": "SOCKET", "position": [2000, 3000]})
    status, data = _post(
        server, "/api/electrical/route", {"point_name": "Розетка 1", "points": [[0, 3000], [2000, 3000]]}
    )
    assert status == 400


def test_full_flow_socket_group_report(server):
    _post(server, "/api/electrical/point", {"kind": "PANEL", "position": [0, 0]})
    _post(server, "/api/electrical/point", {"kind": "SOCKET", "position": [2000, 3000]})

    status, data = _post(
        server,
        "/api/electrical/route",
        {"point_name": "Розетка 1", "points": [[0, 3000], [2000, 3000]]},
    )
    assert status == 200
    assert data["length_m"] == pytest.approx(5.0)  # 3000 + 2000 мм

    status, data = _post(
        server,
        "/api/electrical/assign_group",
        {"point_name": "Розетка 1", "group_name": "Розетки", "phase": "SINGLE", "min_cross_section_mm2": 2.5},
    )
    assert status == 200

    status, state = _get(server, "/api/electrical/state")
    assert state["groups"] == ["Розетки"]
    assert state["routes"]["Розетка 1"] == [[0.0, 0.0], [0.0, 3000.0], [2000.0, 3000.0]]
    assert state["points"][0]["group"] == "Розетки"
    assert state["points"][0]["has_route"] is True

    status, report = _get(server, "/api/electrical/report")
    assert status == 200
    assert report["pending_points"] == []
    assert len(report["groups"]) == 1
    g = report["groups"][0]
    assert g["group_name"] == "Розетки"
    assert g["total_power_w"] == pytest.approx(100.0)
    assert g["cross_section_mm2"] == pytest.approx(2.5)
    assert g["rcd_required"] is True
    assert "Розетки" in report["report_text"]
    assert "Специфікація кабелів" in report["report_text"]


def test_report_lists_pending_points_without_blocking():
    from web.server import AppState, create_server as _create

    srv = _create(port=0, state=AppState())
    import threading as _threading

    t = _threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        _post(srv, "/api/electrical/point", {"kind": "PANEL", "position": [0, 0]})
        _post(srv, "/api/electrical/point", {"kind": "SOCKET", "position": [1000, 0]})  # без групи й траси

        status, report = _get(srv, "/api/electrical/report")
        assert status == 200
        assert report["groups"] == []
        assert report["pending_points"] == ["Розетка 1"]
    finally:
        srv.shutdown()
        srv.server_close()
        t.join(timeout=2)


def test_moving_panel_updates_existing_routes(server):
    _post(server, "/api/electrical/point", {"kind": "PANEL", "position": [0, 0]})
    _post(server, "/api/electrical/point", {"kind": "SOCKET", "position": [2000, 3000]})
    _post(server, "/api/electrical/route", {"point_name": "Розетка 1", "points": [[0, 3000], [2000, 3000]]})
    _post(
        server,
        "/api/electrical/assign_group",
        {"point_name": "Розетка 1", "group_name": "Розетки", "min_cross_section_mm2": 2.5},
    )

    # переставляємо щиток в інше місце
    _post(server, "/api/electrical/point", {"kind": "PANEL", "position": [500, 500]})

    _, state = _get(server, "/api/electrical/state")
    assert state["routes"]["Розетка 1"][0] == [500.0, 500.0]  # траса тепер починається з нового щитка


def test_reset_clears_everything_but_keeps_room():
    srv = create_server(port=0, state=AppState())
    import threading as _threading

    t = _threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        _post(srv, "/api/electrical/point", {"kind": "PANEL", "position": [0, 0]})
        _post(srv, "/api/electrical/point", {"kind": "SOCKET", "position": [1000, 0]})

        status, data = _post(srv, "/api/electrical/reset", {})
        assert status == 200

        _, state = _get(srv, "/api/electrical/state")
        assert state["panel"] is None
        assert state["points"] == []
    finally:
        srv.shutdown()
        srv.server_close()
        t.join(timeout=2)


def test_unknown_point_kind_rejected(server):
    status, data = _post(server, "/api/electrical/point", {"kind": "NOPE", "position": [0, 0]})
    assert status == 400


def test_unknown_phase_rejected(server):
    _post(server, "/api/electrical/point", {"kind": "PANEL", "position": [0, 0]})
    _post(server, "/api/electrical/point", {"kind": "SOCKET", "position": [1000, 0]})
    status, data = _post(
        server, "/api/electrical/assign_group", {"point_name": "Розетка 1", "group_name": "Х", "phase": "NOPE"}
    )
    assert status == 400
