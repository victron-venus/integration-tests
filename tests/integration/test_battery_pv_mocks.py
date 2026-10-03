#!/usr/bin/env python3
"""Integration tests for battery and PV MQTT mock publishers.

Aligned with production contracts (INTEG-1/2):
- dbus-tasmota-pv: tele/<topic>/SENSOR with top-level ENERGY
- dbus-mqtt-battery: <prefix>/sensor/<name>/state scalar payloads
"""

import json
import time

import pytest

from tests.conftest import MqttClient, is_mqtt_available

pytestmark = pytest.mark.skipif(not is_mqtt_available(), reason="MQTT broker not available")


class TestBatteryMock:
    """Verify mock battery publisher topics."""

    def test_battery_soc_topic(self, mqtt_client: MqttClient) -> None:
        """Mock battery should publish SOC on battery/sensor/.../state topics."""
        mqtt_client.subscribe("battery/sensor/#")
        time.sleep(3)

        soc_values = []
        for msg in mqtt_client.messages:
            if msg["topic"].endswith("soc_bms1/state") or msg["topic"].endswith("soc_total/state"):
                soc_values.append(float(msg["payload"]))

        assert soc_values, "Expected battery SOC on battery/sensor topics"
        assert all(0 <= v <= 100 for v in soc_values), (
            f"SOC values {soc_values} outside 0-100 range"
        )

    def test_battery_voltage_topic(self, mqtt_client: MqttClient) -> None:
        """Mock battery should publish voltage to battery/sensor/voltage_bms1/state."""
        mqtt_client.subscribe("battery/sensor/voltage_bms1/state")
        time.sleep(3)

        messages = mqtt_client.messages_on("battery/sensor/voltage_bms1/state")
        assert messages, "No voltage messages received"

        voltage = float(messages[0]["payload"])
        assert voltage > 0, f"Voltage should be positive, got {voltage}"


class TestPVMock:
    """Verify mock Tasmota PV publisher topics."""

    def test_tasmota_energy_topic(self, mqtt_client: MqttClient) -> None:
        """Mock PV should publish power on tele/tasmota-pv/SENSOR ENERGY.Power."""
        mqtt_client.subscribe("tele/tasmota-pv/#")
        time.sleep(3)

        powers = []
        for msg in mqtt_client.messages:
            if msg["topic"].endswith("/SENSOR"):
                data = json.loads(msg["payload"])
                power = data.get("ENERGY", {}).get("Power")
                if power is not None:
                    powers.append(float(power))

        assert powers, "Expected Tasmota ENERGY.Power on tele/tasmota-pv/SENSOR"
        assert all(p >= 0 for p in powers), f"PV power should be >= 0, got {powers}"

    def test_tasmota_voltage_format(self, mqtt_client: MqttClient) -> None:
        """Tasmota SENSOR payload should include Voltage and Current under ENERGY."""
        mqtt_client.subscribe("tele/tasmota-pv/SENSOR")
        time.sleep(3)

        messages = mqtt_client.messages_on("tele/tasmota-pv/SENSOR")
        assert messages, "No SENSOR messages from tasmota-pv"

        data = json.loads(messages[0]["payload"])
        energy = data.get("ENERGY", {})
        assert "Voltage" in energy, "ENERGY missing Voltage"
        assert "Current" in energy, "ENERGY missing Current"
        assert isinstance(energy["Voltage"], int | float)
        assert isinstance(energy["Current"], int | float)
