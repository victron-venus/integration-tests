#!/usr/bin/env python3
"""Integration tests for battery and PV MQTT mock publishers."""

import json
import time

import pytest

from tests.conftest import MqttClient, is_mqtt_available

pytestmark = pytest.mark.skipif(not is_mqtt_available(), reason="MQTT broker not available")


class TestBatteryMock:
    """Verify mock battery publisher topics."""

    def test_battery_soc_topic(self, mqtt_client: MqttClient) -> None:
        """Mock battery should publish SOC to jbd/bms/1 topics."""
        mqtt_client.subscribe("jbd/bms/1/#")
        time.sleep(3)

        soc_values = []
        for msg in mqtt_client.messages:
            if msg["topic"].endswith("/soc") or msg["topic"].endswith("/state"):
                data = json.loads(msg["payload"])
                val = data.get("value") or data.get("soc")
                if val is not None:
                    soc_values.append(float(val))

        assert soc_values, "Expected battery SOC on jbd/bms/1 topics"
        assert all(0 <= v <= 100 for v in soc_values), (
            f"SOC values {soc_values} outside 0-100 range"
        )

    def test_battery_voltage_topic(self, mqtt_client: MqttClient) -> None:
        """Mock battery should publish voltage to jbd/bms/1/voltage."""
        mqtt_client.subscribe("jbd/bms/1/voltage")
        time.sleep(3)

        messages = mqtt_client.messages_on("jbd/bms/1/voltage")
        assert messages, "No voltage messages received"

        data = json.loads(messages[0]["payload"])
        voltage = data.get("value")
        assert voltage is not None, "Voltage payload missing 'value' key"
        assert isinstance(voltage, int | float), f"Voltage {voltage} is not numeric"
        assert voltage > 0, f"Voltage should be positive, got {voltage}"


class TestPVMock:
    """Verify mock Tasmota PV publisher topics."""

    def test_tasmota_energy_topic(self, mqtt_client: MqttClient) -> None:
        """Mock PV should publish power to tele/tasmota-pv topics."""
        mqtt_client.subscribe("tele/tasmota-pv/#")
        time.sleep(3)

        powers = []
        for msg in mqtt_client.messages:
            if "tasmota-pv" in msg["topic"]:
                data = json.loads(msg["payload"])
                power = data.get("StatusSNS", {}).get("ENERGY", {}).get("Power")
                if power is not None:
                    powers.append(float(power))

        assert powers, "Expected Tasmota ENERGY.Power on tele/tasmota-pv/STATE"
        assert all(p >= 0 for p in powers), f"PV power should be >= 0, got {powers}"

    def test_tasmota_voltage_format(self, mqtt_client: MqttClient) -> None:
        """Tasmota payload should include Voltage and Current."""
        mqtt_client.subscribe("tele/tasmota-pv/STATE")
        time.sleep(3)

        messages = mqtt_client.messages_on("tele/tasmota-pv/STATE")
        assert messages, "No STATE messages from tasmota-pv"

        data = json.loads(messages[0]["payload"])
        energy = data.get("StatusSNS", {}).get("ENERGY", {})
        assert "Voltage" in energy, "ENERGY missing Voltage"
        assert "Current" in energy, "ENERGY missing Current"
        assert isinstance(energy["Voltage"], int | float)
        assert isinstance(energy["Current"], int | float)
