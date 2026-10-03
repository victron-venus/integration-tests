"""Exercise one publisher cycle without opening sockets or running a broker."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]


class CycleComplete(Exception):
    """Stop a publisher after its first batch of messages."""


def publish_cycle(name, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        name, ROOT / name / f"{name.replace('-', '_')}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    messages = []
    client = Mock()
    client.publish.side_effect = lambda topic, payload: messages.append((topic, payload))
    monkeypatch.setattr(
        module,
        "mqtt",
        SimpleNamespace(
            Client=lambda **kwargs: client,
            CallbackAPIVersion=SimpleNamespace(VERSION1=1),
        ),
    )
    monkeypatch.setattr(module, "os", SimpleNamespace(getenv=lambda key, fallback: fallback))

    def stop_cycle(_delay):
        raise CycleComplete

    monkeypatch.setattr(
        module,
        "time",
        SimpleNamespace(
            time=lambda: 10.0,
            strftime=lambda _format: "2000-01-01T00:00:00",
            sleep=stop_cycle,
        ),
    )
    with pytest.raises(CycleComplete):
        module.main()
    return dict(messages)


def test_mock_pv_publishes_tele_sensor_with_top_level_energy(monkeypatch):
    messages = publish_cycle("mock-pv", monkeypatch)
    payload = json.loads(messages["tele/tasmota-pv/SENSOR"])
    assert payload["ENERGY"]["Power"] == 375.0
    assert payload["ENERGY"]["Voltage"] == 230
    assert "StatusSNS" not in payload


def test_mock_battery_uses_esphome_scalar_battery_topics(monkeypatch):
    messages = publish_cycle("mock-battery", monkeypatch)
    expected = {
        "voltage_bms1": 52.4,
        "current_bms1": -12.5,
        "soc_bms1": 78.0,
        "voltage_cell1_bms1": 3.28,
        "voltage_cell2_bms1": 3.31,
        "temperature1_bms1": 22.5,
        "voltage_total": 52.4,
        "current_total": -12.5,
        "soc_total": 78.0,
    }
    assert set(messages) == {f"battery/sensor/{name}/state" for name in expected}
    for name, value in expected.items():
        assert float(messages[f"battery/sensor/{name}/state"]) == value
