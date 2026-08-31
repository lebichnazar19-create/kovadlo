"""Тести HTTP-API модуля 9 (візуалізація інженерних систем)."""

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


def _make_kitchen(server):
    _post(
        server,
        "/api/room",
        {
            "points": [[0, 0], [4000, 0], [4000, 3000], [0, 3000]],
            "wall_height": 2700,
            "wall_thickness": 200,
            "material_name": "цегла",
            "room_name": "Кухня",
        },
    )


# ---------------------------------------------------------------------------
# 9.1 Освітлення
# ---------------------------------------------------------------------------


def test_lighting_state_requires_room(server):
    status, data = _get(server, "/api/lighting/state")
    assert status == 400


def test_lighting_kitchen_six_fixtures_hits_exact_target(server):
    """Той самий контрольний приклад, що й у модулі 8: кухня 12 м²,
    6 світильників по 1500 лм/15Вт -> рівно 300 лк."""
    _make_kitchen(server)
    _post(server, "/api/lighting/settings", {"room_purpose": "KITCHEN"})
    for i in range(6):
        status, data = _post(
            server,
            "/api/lighting/fixture",
            {"kind": "CEILING", "position": [500 + i * 500, 1000], "luminous_flux_lm": 1500, "power_w": 15},
        )
        assert status == 200

    status, state = _get(server, "/api/lighting/state")
    assert status == 200
    assert state["target_lux"] == 300.0
    assert state["achieved_lux"] == pytest.approx(300.0)
    assert state["meets_target"] is True
    assert state["deficit_flux_lm"] is None
    assert len(state["fixtures"]) == 6
    assert state["total_power_w"] == pytest.approx(90.0)
    assert "Освітлення" in state["report_text"]


def test_lighting_reports_deficit_when_below_target(server):
    _make_kitchen(server)
    _post(server, "/api/lighting/settings", {"room_purpose": "KITCHEN"})
    _post(server, "/api/lighting/fixture", {"kind": "CEILING", "position": [1000, 1000], "luminous_flux_lm": 800, "power_w": 8})

    status, state = _get(server, "/api/lighting/state")
    assert status == 200
    assert state["meets_target"] is False
    assert state["deficit_flux_lm"] > 0


def test_lighting_delete_fixture(server):
    _make_kitchen(server)
    _post(server, "/api/lighting/fixture", {"kind": "CEILING", "position": [1000, 1000], "luminous_flux_lm": 800, "power_w": 8})
    _, state = _get(server, "/api/lighting/state")
    name = state["fixtures"][0]["name"]
    status, _ = _post(server, "/api/lighting/fixture_delete", {"name": name})
    assert status == 200
    _, state2 = _get(server, "/api/lighting/state")
    assert state2["fixtures"] == []


def test_lighting_reset(server):
    _make_kitchen(server)
    _post(server, "/api/lighting/fixture", {"kind": "CEILING", "position": [1000, 1000], "luminous_flux_lm": 800, "power_w": 8})
    _post(server, "/api/lighting/reset", {})
    _, state = _get(server, "/api/lighting/state")
    assert state["fixtures"] == []


def test_lighting_rejects_unknown_kind(server):
    _make_kitchen(server)
    status, _ = _post(server, "/api/lighting/fixture", {"kind": "NOPE", "position": [0, 0]})
    assert status == 400


# ---------------------------------------------------------------------------
# 9.2 Вентиляція
# ---------------------------------------------------------------------------


def test_ventilation_kitchen_hand_verified(server):
    """Той самий контрольний приклад, що й у модулі 8: кухня, 50 м³/год,
    ⌀80мм, ~11.45 Па, вентилятор посиленого класу."""
    _make_kitchen(server)
    _post(server, "/api/ventilation/settings", {"room_kind": "KITCHEN"})
    status, duct = _post(
        server, "/api/ventilation/duct", {"points": [[0, 0], [0, 5000], [5000, 5000]], "shape": "ROUND", "diameter_mm": 80}
    )
    assert status == 200
    assert duct["length_m"] == pytest.approx(10.0)

    status, state = _get(server, "/api/ventilation/state")
    assert status == 200
    assert state["required_airflow_m3_h"] == pytest.approx(50.0)
    assert len(state["ducts"]) == 1
    assert state["ducts"][0]["velocity_m_s"] == pytest.approx(2.7632, abs=1e-3)
    assert state["total_pressure_loss_pa"] == pytest.approx(11.45, abs=0.02)
    assert state["fan"]["max_flow_m3_h"] == 60.0
    assert "Вентиляція" in state["report_text"]


def test_ventilation_delete_duct_and_reset(server):
    _make_kitchen(server)
    _post(server, "/api/ventilation/duct", {"points": [[0, 0], [1000, 0]], "shape": "ROUND", "diameter_mm": 100})
    _, state = _get(server, "/api/ventilation/state")
    name = state["ducts"][0]["name"]
    _post(server, "/api/ventilation/duct_delete", {"name": name})
    _, state2 = _get(server, "/api/ventilation/state")
    assert state2["ducts"] == []

    _post(server, "/api/ventilation/duct", {"points": [[0, 0], [1000, 0]], "shape": "ROUND", "diameter_mm": 100})
    _post(server, "/api/ventilation/reset", {})
    _, state3 = _get(server, "/api/ventilation/state")
    assert state3["ducts"] == []


def test_ventilation_rectangular_duct_requires_width_and_height(server):
    _make_kitchen(server)
    status, _ = _post(
        server, "/api/ventilation/duct", {"points": [[0, 0], [1000, 0]], "shape": "RECTANGULAR", "width_mm": 200}
    )
    assert status == 400


# ---------------------------------------------------------------------------
# 9.4 Тепло
# ---------------------------------------------------------------------------


def test_heat_materials_lists_only_ones_with_conductivity(server):
    status, materials = _get(server, "/api/heat/materials")
    assert status == 200
    assert len(materials) > 0
    assert all(m["thermal_conductivity_w_mk"] is not None for m in materials)


def test_heat_wall_layers_hand_verified(server):
    """Той самий контрольний приклад, що й у модулі 8: бетон 200мм +
    вата 180мм -> R=5.018, U=0.199, відповідає WT2021."""
    _make_kitchen(server)
    status, _ = _post(
        server,
        "/api/heat/wall_layers",
        {
            "wall_index": 0,
            "layers": [
                {"material_name": "Бетон C25/30", "thickness_mm": 200},
                {"material_name": "Мінеральна вата (кам'яна)", "thickness_mm": 180},
            ],
        },
    )
    assert status == 200

    status, state = _get(server, "/api/heat/state")
    assert status == 200
    wall = state["walls"][0]
    assert wall["has_layers"] is True
    assert wall["r_value_m2k_w"] == pytest.approx(5.018, abs=1e-3)
    assert wall["u_value_w_m2k"] == pytest.approx(0.199, abs=1e-3)
    assert wall["meets_wt2021"] is True
    assert wall["condensation_warnings"] == []
    assert "Тепло" in state["report_text"]

    # решта стін кімнати досі без конструкції
    assert state["walls"][1]["has_layers"] is False


def test_heat_wall_layers_rejects_unknown_material(server):
    _make_kitchen(server)
    status, _ = _post(
        server, "/api/heat/wall_layers", {"wall_index": 0, "layers": [{"material_name": "Невідомий", "thickness_mm": 100}]}
    )
    assert status == 400


def test_heat_wall_layers_rejects_bad_wall_index(server):
    _make_kitchen(server)
    status, _ = _post(server, "/api/heat/wall_layers", {"wall_index": 99, "layers": []})
    assert status == 400


def test_heat_bare_wall_fails_wt2021(server):
    _make_kitchen(server)
    _post(server, "/api/heat/wall_layers", {"wall_index": 0, "layers": [{"material_name": "Бетон C25/30", "thickness_mm": 200}]})
    _, state = _get(server, "/api/heat/state")
    assert state["walls"][0]["meets_wt2021"] is False


def test_heat_reset(server):
    _make_kitchen(server)
    _post(server, "/api/heat/wall_layers", {"wall_index": 0, "layers": [{"material_name": "Бетон C25/30", "thickness_mm": 200}]})
    _post(server, "/api/heat/reset", {})
    _, state = _get(server, "/api/heat/state")
    assert all(not w["has_layers"] for w in state["walls"])


# ---------------------------------------------------------------------------
# 9.5 Пожежна безпека
# ---------------------------------------------------------------------------


def test_fire_auto_place_hand_verified(server):
    """Той самий контрольний приклад, що й у модулі 8: кухня 4×3 м ->
    2 димові датчики (периметр/9 домінує над площею/40)."""
    _make_kitchen(server)
    status, result = _post(server, "/api/fire/auto_place", {})
    assert status == 200
    assert result["count"] == 2

    status, state = _get(server, "/api/fire/state")
    assert status == 200
    assert len(state["detectors"]) == 2
    assert state["loop_length_m"] is None  # щиток ще не поставлений
    assert "Пожежна безпека" in state["report_text"]


def test_fire_loop_uses_electrical_panel_position(server):
    """Довжина шлейфу рахується від щитка модуля 5 (0,0) через 2 датчики
    й назад: 3000+4000 (по прямокутнику) + гіпотенузи ~ 9.69 м (як у модулі 8)."""
    _make_kitchen(server)
    _post(server, "/api/electrical/point", {"kind": "PANEL", "position": [0, 0]})
    _post(server, "/api/fire/auto_place", {})

    status, state = _get(server, "/api/fire/state")
    assert status == 200
    assert state["loop_length_m"] == pytest.approx(9.69, abs=0.01)
    assert state["panel_position"] == [0.0, 0.0]


def test_fire_settings_changes_detector_kind(server):
    _make_kitchen(server)
    status, _ = _post(server, "/api/fire/settings", {"detector_kind": "CO"})
    assert status == 200
    _post(server, "/api/fire/auto_place", {})
    _, state = _get(server, "/api/fire/state")
    assert state["detector_kind"] == "CO"
    assert all(d["kind"] == "CO" for d in state["detectors"])


def test_fire_reset(server):
    _make_kitchen(server)
    _post(server, "/api/fire/auto_place", {})
    _post(server, "/api/fire/reset", {})
    _, state = _get(server, "/api/fire/state")
    assert state["detectors"] == []


def test_fire_state_requires_room(server):
    status, _ = _get(server, "/api/fire/state")
    assert status == 400
