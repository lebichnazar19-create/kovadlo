"""Тести датчиків модуля 13 — потужність, зв'язок з модулем 4."""

import pytest

from kovadlo.electrical_point import PointKind
from kovadlo.geometry import Point
from kovadlo.sensors import OutputType, Sensor, SensorKind


def test_sensor_power_hand_verified():
    # P = U·I = 12·0.01 = 0.12 Вт
    sensor = Sensor(name="Кінцевик", kind=SensorKind.LIMIT_SWITCH, output_type=OutputType.DIGITAL, voltage_v=12.0, current_a=0.01)
    assert sensor.power_w == pytest.approx(0.12)


def test_sensor_rejects_non_positive_voltage():
    with pytest.raises(ValueError):
        Sensor(name="x", kind=SensorKind.DISTANCE, output_type=OutputType.ANALOG, voltage_v=0.0, current_a=0.01)


def test_sensor_rejects_negative_current():
    with pytest.raises(ValueError):
        Sensor(name="x", kind=SensorKind.DISTANCE, output_type=OutputType.ANALOG, voltage_v=5.0, current_a=-0.1)


def test_sensor_rejects_inverted_range():
    with pytest.raises(ValueError):
        Sensor(
            name="x", kind=SensorKind.DISTANCE, output_type=OutputType.ANALOG, voltage_v=5.0, current_a=0.01,
            range_min=100, range_max=10,
        )


def test_sensor_allows_none_range_for_digital_sensors():
    button = Sensor(name="Кнопка", kind=SensorKind.BUTTON, output_type=OutputType.DIGITAL, voltage_v=5.0, current_a=0.001)
    assert button.range_min is None
    assert button.range_max is None


def test_sensor_to_consumption_point_uses_socket_and_real_power():
    sensor = Sensor(name="Дальномір", kind=SensorKind.DISTANCE, output_type=OutputType.ANALOG, voltage_v=5.0, current_a=0.015, range_min=20, range_max=4000, unit="мм")
    point = sensor.to_consumption_point(Point(1000, 500), name="Д1")
    assert point.kind is PointKind.SOCKET
    assert point.name == "Д1"
    assert point.position == Point(1000, 500)
    assert point.power_w == pytest.approx(5.0 * 0.015)


def test_sensor_to_consumption_point_default_name():
    sensor = Sensor(name="Фотобар'єр", kind=SensorKind.PHOTOCELL, output_type=OutputType.DIGITAL, voltage_v=24.0, current_a=0.03)
    point = sensor.to_consumption_point(Point(0, 0))
    assert point.name == "Фотобар'єр"
