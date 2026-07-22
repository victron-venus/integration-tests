#!/usr/bin/env python3
"""
Mock D-Bus for integration testing.
Simulates Victron D-Bus services (system, Ve.Bus, PV inverters).
"""

import json
import time
import os
from pathlib import Path

try:
    import paho.mqtt.client as mqtt
except ImportError:
    import sys
    print("ERROR: paho-mqtt not installed")
    sys.exit(1)

# D-Bus mock paths
SYSTEM_SERVICE = "/tmp/mock_dbus_system.json"
VEBUS_SERVICE = "/tmp/mock_dbus_vebus.json"


class MockDBusService:
    """Simulates a VeDbusService for testing."""

    def __init__(self, service_name: str):
        self._service_name = service_name
        self._paths = {}
        self._json_file = f"/tmp/mock_dbus_{service_name.replace('.', '_')}.json"

    def add_path(self, path: str, initial_value=None, writeable=False, **kwargs):
        self._paths[path] = {
            "value": initial_value,
            "writeable": writeable,
            "gettextcallback": kwargs.get("gettextcallback"),
        }

    def __setitem__(self, path: str, value):
        if path in self._paths:
            self._paths[path]["value"] = value
            self._save()

    def __getitem__(self, path: str):
        return self._paths.get(path, {}).get("value")

    def _save(self):
        Path(self._json_file).write_text(json.dumps(self._paths, indent=2))

    def register(self):
        self._save()
        print(f"[mock-dbus] Registered {self._service_name}")


class MockDBus:
    """Complete mock D-Bus system simulation."""

    def __init__(self):
        self.services = {}

    def register(self, service: MockDBusService):
        self.services[service._service_name] = service

    def read_path(self, service: str, path: str):
        if service in self.services:
            return self.services[service][path]
        return None

    def write_path(self, service: str, path: str, value):
        if service in self.services and path in self.services[service]._paths:
            self.services[service][path] = value


# Global instance
mock_dbus = MockDBus()


def create_system_service() -> MockDBusService:
    """Create mock /System service."""
    service = MockDBusService("com.victronenergy.system")

    service.add_path("/SystemType", "pvinverter")
    service.add_path("/BatteryOperationalLimits/MaxChargeVoltage", 58000)
    service.add_path("/BatteryOperationalLimits/MaxChargeCurrent", 100)
    service.add_path("/BatteryOperationalLimits/MaxDischargeCurrent", 120)
    service.add_path("/Dc/Battery/Voltage", 52.0)
    service.add_path("/Dc/Battery/Current", 0.0)
    service.add_path("/Dc/Battery/Power", 0.0)
    service.add_path("/Soc", 80)

    mock_dbus.register(service)
    return service


def create_vebus_service() -> MockDBusService:
    """Create mock Ve.Bus service."""
    service = MockDBusService("com.victronenergy.vebus.ttyUSB0")

    service.add_path("/Mgmt/ProcessName", "mock-dbus")
    service.add_path("/Mgmt/ProcessVersion", "1.0.0")
    service.add_path("/DeviceInstance", 0)
    service.add_path("/ProductId", 0xA142)
    service.add_path("/State", 9)  # Inverting
    service.add_path("/Ac/ActiveIn/ActiveInput", 0)
    service.add_path("/Ac/ActiveIn/P", 0)
    service.add_path("/Ac/ActiveIn/L1/P", 0)
    service.add_path("/Ac/ActiveIn/L2/P", 0)
    service.add_path("/Ac/Out/L1/P", 0)
    service.add_path("/Ac/Out/L2/P", 0)
    service.add_path("/Hub4/SystemMinSoc", 15)
    service.add_path("/Settings/SystemSetup/GridSetPoint", 0)
    service.add_path("/Settings/SystemSetup/AcOutputVoltage", 230)
    service.add_path("/Settings/SystemSetup/AcOutputFrequency", 50)

    mock_dbus.register(service)
    return service


def create_pv_inverter(instance: int) -> MockDBusService:
    """Create mock PV inverter service."""
    service = MockDBusService(f"com.victronenergy.pvinverter.tasmota_{instance}")

    service.add_path("/Mgmt/ProcessName", "mock-dbus")
    service.add_path("/Mgmt/ProcessVersion", "1.0.0")
    service.add_path("/DeviceInstance", instance)
    service.add_path("/ProductId", 0xA144)
    service.add_path("/Connected", 1)
    service.add_path("/Position", 0)
    service.add_path("/Ac/Power", 0.0)
    service.add_path("/Ac/L1/Power", 0.0)
    service.add_path("/Ac/L1/Voltage", 230.0)
    service.add_path("/Ac/L1/Current", 0.0)

    mock_dbus.register(service)
    return service


def setup_mock_services():
    """Initialize all mock D-Bus services."""
    create_system_service()
    create_vebus_service()
    create_pv_inverter(120)
    create_pv_inverter(121)


class DbusPublisher:
    """Publishes D-Bus state to MQTT for external services."""

    def __init__(self, broker: str, port: int):
        self.broker = broker
        self.port = port
        self.client = mqtt.Client(client_id="mock-dbus-publisher")
        self.client.on_connect = self._on_connect
        self.last_dbus_state = {}

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print("[mock-dbus] Connected to MQTT")
            client.subscribe("dbus/mock/#")

    def run(self):
        self.client.connect(self.broker, self.port)
        self.client.loop_start()

        setup_mock_services()

        print("[mock-dbus] Starting D-Bus simulation...")

        while True:
            # Simulate grid power fluctuation
            base_power = 0
            noise = (time.time() % 10) - 5  # -5 to +5W noise
            grid_power = base_power + noise

            # Publish to MQTT for inverter-control
            state = {
                "n2k": 0,
                "gs": grid_power,
                "ac": {
                    "L1": {"P": grid_power / 2},
                    "L2": {"P": -grid_power / 2},
                }
            }
            self.client.publish("venus/dbus/system/0/SystemType", json.dumps(state))

            # Simulate Ve.Bus state
            vebus_state = {
                "state": 9,  # Inverting
                "invertion_output_power": 0,
                "battery_current": 0,
                "ac_power_in": 0,
                "ac_power_out": 0,
            }
            self.client.publish("venus/dbus/vebus/0", json.dumps(vebus_state))

            time.sleep(1)


def main():
    broker = os.getenv("MQTT_HOST", "localhost")
    port = int(os.getenv("MQTT_PORT", "1883"))

    print(f"[mock-dbus] Starting mock D-Bus (MQTT: {broker}:{port})")

    publisher = DbusPublisher(broker, port)

    try:
        publisher.run()
    except KeyboardInterrupt:
        print("[mock-dbus] Shutdown")
        publisher.client.loop_stop()


if __name__ == "__main__":
    main()