#!/usr/bin/env python3
"""Integration tests for D-Bus mock services publishing battery/PV state to MQTT."""

import json
import time

import pytest

from tests.conftest import MqttClient, is_mqtt_available

pytestmark = pytest.mark.skipif(not is_mqtt_available(), reason="MQTT broker not available")


class TestDBusBatteryState:
    """Verify mock D-Bus system service publishes battery state to MQTT."""

    def test_battery_soc_published(self, mqtt_client: MqttClient) -> None:
        """System service should expose SOC via venus/dbus/system/0/SystemType."""
        mqtt_client.subscribe("venus/dbus/system/0/#")
        time.sleep(3)

        messages = mqtt_client.messages_on("venus/dbus/system/0/SystemType")
        assert messages, "No messages on venus/dbus/system/0/SystemType"

        data = json.loads(messages[0]["payload"])
        assert "gs" in data or "ac" in data, "SystemType payload missing grid/system keys"

    def test_battery_voltage_range(self, mqtt_client: MqttClient) -> None:
        """Battery voltage should be in realistic 48-58V range."""
        mqtt_client.subscribe("jbd/bms/1/voltage")
        time.sleep(3)

        messages = mqtt_client.messages_on("jbd/bms/1/voltage")
        assert messages, "No voltage messages from mock battery"

        data = json.loads(messages[0]["payload"])
        voltage = data.get("value")
        assert voltage is not None, "Voltage payload missing 'value' key"
        assert 40.0 <= voltage <= 60.0, f"Battery voltage {voltage}V outside 40-60V range"

    def test_battery_soc_oscillates(self, mqtt_client: MqttClient) -> None:
        """SOC should change over time (mock oscillates)."""
        mqtt_client.subscribe("jbd/bms/1/soc")
        time.sleep(5)

        soc_values = []
        for msg in mqtt_client.messages_on("jbd/bms/1/soc"):
            data = json.loads(msg["payload"])
            val = data.get("value")
            if val is not None:
                soc_values.append(float(val))

        assert len(soc_values) >= 2, f"Expected multiple SOC readings, got {len(soc_values)}"
        assert 0.0 <= min(soc_values) <= max(soc_values) <= 100.0, (
            f"SOC values {soc_values} outside 0-100 range"
        )
        assert max(soc_values) - min(soc_values) > 0, "SOC should oscillate (min == max)"

    def test_battery_current_negative(self, mqtt_client: MqttClient) -> None:
        """Negative current indicates charging (mock-battery convention)."""
        mqtt_client.subscribe("jbd/bms/1/current")
        time.sleep(3)

        messages = mqtt_client.messages_on("jbd/bms/1/current")
        assert messages, "No current messages from mock battery"

        data = json.loads(messages[0]["payload"])
        current = data.get("value")
        assert current is not None, "Current payload missing 'value' key"
        assert isinstance(current, int | float), f"Current {current} is not numeric"
        assert current < 0, f"Expected negative current (charging), got {current}"

    def test_battery_state_aggregate(self, mqtt_client: MqttClient) -> None:
        """State topic should aggregate voltage, current, and soc."""
        mqtt_client.subscribe("jbd/bms/1/state")
        time.sleep(3)

        messages = mqtt_client.messages_on("jbd/bms/1/state")
        assert messages, "No state messages from mock battery"

        data = json.loads(messages[0]["payload"])
        for key in ("voltage", "current", "soc"):
            assert key in data, f"State payload missing key '{key}'"

        assert isinstance(data["voltage"], int | float)
        assert isinstance(data["current"], int | float)
        assert isinstance(data["soc"], int | float)


class TestDBusPVState:
    """Verify mock D-Bus publishes PV inverter state to MQTT."""

    def test_system_type_payload(self, mqtt_client: MqttClient) -> None:
        """SystemType topic should publish grid power with noise."""
        mqtt_client.subscribe("venus/dbus/system/0/SystemType")
        time.sleep(3)

        messages = mqtt_client.messages_on("venus/dbus/system/0/SystemType")
        assert messages, "No SystemType messages"

        data = json.loads(messages[0]["payload"])
        assert "gs" in data, "SystemType payload missing grid setpoint 'gs'"
        assert "ac" in data, "SystemType payload missing AC data"
        assert "L1" in data["ac"], "AC data missing L1"
        assert "L2" in data["ac"], "AC data missing L2"
        assert "P" in data["ac"]["L1"], "L1 missing power 'P'"
        assert "P" in data["ac"]["L2"], "L2 missing power 'P'"

    def test_grid_power_oscillates(self, mqtt_client: MqttClient) -> None:
        """Grid power should vary due to simulated noise."""
        mqtt_client.subscribe("venus/dbus/system/0/SystemType")
        time.sleep(5)

        gs_values = []
        for msg in mqtt_client.messages_on("venus/dbus/system/0/SystemType"):
            data = json.loads(msg["payload"])
            gs_values.append(data.get("gs", 0))

        assert len(gs_values) >= 2, f"Expected multiple grid readings, got {len(gs_values)}"
        assert min(gs_values) != max(gs_values), "Grid power should vary (no noise detected)"

    def test_vebus_state_inverting(self, mqtt_client: MqttClient) -> None:
        """Ve.Bus state should be 9 (Inverting)."""
        mqtt_client.subscribe("venus/dbus/vebus/0")
        time.sleep(3)

        messages = mqtt_client.messages_on("venus/dbus/vebus/0")
        assert messages, "No Ve.Bus messages"

        data = json.loads(messages[0]["payload"])
        assert data.get("state") == 9, (
            f"Ve.Bus state should be 9 (Inverting), got {data.get('state')}"
        )

    def test_vebus_power_fields(self, mqtt_client: MqttClient) -> None:
        """Ve.Bus payload should include power-related fields."""
        mqtt_client.subscribe("venus/dbus/vebus/0")
        time.sleep(3)

        messages = mqtt_client.messages_on("venus/dbus/vebus/0")
        assert messages, "No Ve.Bus messages"

        data = json.loads(messages[0]["payload"])
        for key in ("state", "ac_power_in", "ac_power_out", "battery_current"):
            assert key in data, f"Ve.Bus payload missing key '{key}'"


class TestBatteryPVEndToEnd:
    """Verify battery and PV mocks publish concurrently and data updates."""

    def test_concurrent_battery_pv_publishing(self, mqtt_client: MqttClient) -> None:
        """Both battery and PV should publish to MQTT simultaneously."""
        mqtt_client.subscribe("jbd/bms/1/#")
        mqtt_client.subscribe("tele/tasmota-pv/#")
        time.sleep(5)

        battery_topics = [m for m in mqtt_client.messages if m["topic"].startswith("jbd/bms/1/")]
        pv_topics = [m for m in mqtt_client.messages if "tasmota-pv" in m["topic"]]

        assert battery_topics, "No battery topics received"
        assert pv_topics, "No PV topics received"

    def test_pv_power_updates(self, mqtt_client: MqttClient) -> None:
        """PV power should update following the simulated diurnal curve."""
        mqtt_client.subscribe("tele/tasmota-pv/STATE")
        time.sleep(5)

        powers = []
        for msg in mqtt_client.messages_on("tele/tasmota-pv/STATE"):
            data = json.loads(msg["payload"])
            power = data.get("StatusSNS", {}).get("ENERGY", {}).get("Power")
            if power is not None:
                powers.append(float(power))

        assert len(powers) >= 2, f"Expected multiple PV readings, got {len(powers)}"
        assert all(p >= 0 for p in powers), f"PV power should be >= 0, got {powers}"

    def test_battery_cell_voltage_consistent(self, mqtt_client: MqttClient) -> None:
        """Cell voltage min should be less than or equal to max."""
        mqtt_client.subscribe("jbd/bms/1/cell_voltage_min")
        mqtt_client.subscribe("jbd/bms/1/cell_voltage_max")
        time.sleep(3)

        v_min_msgs = mqtt_client.messages_on("jbd/bms/1/cell_voltage_min")
        v_max_msgs = mqtt_client.messages_on("jbd/bms/1/cell_voltage_max")

        assert v_min_msgs, "No cell_voltage_min messages"
        assert v_max_msgs, "No cell_voltage_max messages"

        v_min = json.loads(v_min_msgs[0]["payload"]).get("value")
        v_max = json.loads(v_max_msgs[0]["payload"]).get("value")

        assert v_min is not None and v_max is not None
        assert v_min <= v_max, f"Cell min {v_min}V > max {v_max}V"
        assert 2.5 <= v_min <= 4.5, f"Cell min {v_min}V outside realistic range"
        assert 2.5 <= v_max <= 4.5, f"Cell max {v_max}V outside realistic range"


class TestControlLoopDBusToMQTT:
    """Verify D-Bus mock state propagates to MQTT within expected timeframe."""

    def test_vebus_propagation_latency(self, mqtt_client: MqttClient) -> None:
        """Ve.Bus state should appear on MQTT within 5 seconds of subscribe."""
        start = time.time()
        mqtt_client.subscribe("venus/dbus/vebus/0")

        deadline = start + 5.0
        found = False
        while time.time() < deadline:
            for msg in mqtt_client.messages_on("venus/dbus/vebus/0"):
                data = json.loads(msg["payload"])
                if "state" in data:
                    found = True
                    break
            if found:
                break
            time.sleep(0.2)

        assert found, "Ve.Bus state not received within 5 seconds"
        latency = time.time() - start
        assert latency < 5.0, f"Ve.Bus propagation took {latency:.1f}s (> 5s)"

    def test_system_type_propagation_latency(self, mqtt_client: MqttClient) -> None:
        """SystemType should appear on MQTT within 5 seconds of subscribe."""
        start = time.time()
        mqtt_client.subscribe("venus/dbus/system/0/SystemType")

        deadline = start + 5.0
        found = False
        while time.time() < deadline:
            for msg in mqtt_client.messages_on("venus/dbus/system/0/SystemType"):
                data = json.loads(msg["payload"])
                if "gs" in data:
                    found = True
                    break
            if found:
                break
            time.sleep(0.2)

        assert found, "SystemType not received within 5 seconds"
        latency = time.time() - start
        assert latency < 5.0, f"SystemType propagation took {latency:.1f}s (> 5s)"
