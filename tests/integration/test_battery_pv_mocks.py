#!/usr/bin/env python3
"""Integration tests for battery and PV MQTT mock publishers."""

import json
import os
import time

import paho.mqtt.client as mqtt


def _mqtt_client():
    host = os.getenv("MQTT_HOST", "localhost")
    port = int(os.getenv("MQTT_PORT", "1883"))
    messages = []

    def on_message(_client, _userdata, msg):
        messages.append((msg.topic, msg.payload.decode()))

    client = mqtt.Client(client_id=f"test-battery-pv-{int(time.time())}")
    client.on_message = on_message
    client.connect(host, port)
    client.loop_start()
    time.sleep(0.3)
    return client, messages


class TestBatteryMock:
    """Verify mock battery publisher topics."""

    def test_battery_soc_topic(self):
        """Mock battery should publish SOC to jbd/bms/1 topics."""
        client, messages = _mqtt_client()
        client.subscribe("jbd/bms/1/#")

        found_soc = False
        deadline = time.time() + 10
        while time.time() < deadline:
            for topic, payload in messages:
                if topic.endswith("/soc") or topic.endswith("/state"):
                    data = json.loads(payload)
                    if "soc" in data or "value" in data:
                        found_soc = True
                        break
            if found_soc:
                break
            time.sleep(0.2)

        client.loop_stop()
        client.disconnect()
        assert found_soc, "Expected battery SOC on jbd/bms/1 topics"


class TestPVMock:
    """Verify mock Tasmota PV publisher topics."""

    def test_tasmota_energy_topic(self):
        """Mock PV should publish power to tele/tasmota-pv topics."""
        client, messages = _mqtt_client()
        client.subscribe("tele/tasmota-pv/#")

        found_power = False
        deadline = time.time() + 10
        while time.time() < deadline:
            for topic, payload in messages:
                if "tasmota-pv" in topic:
                    data = json.loads(payload)
                    power = data.get("StatusSNS", {}).get("ENERGY", {}).get("Power")
                    if power is not None and power >= 0:
                        found_power = True
                        break
            if found_power:
                break
            time.sleep(0.2)

        client.loop_stop()
        client.disconnect()
        assert found_power, "Expected Tasmota ENERGY.Power on tele/tasmota-pv/STATE"
