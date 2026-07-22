#!/usr/bin/env python3
"""
Mock Tasmota PV meter publisher for integration tests.
Simulates HTTP-polled power data via MQTT (as dbus-tasmota-pv consumes).
"""

import json
import os
import time

import paho.mqtt.client as mqtt


def main():
    host = os.getenv("MQTT_HOST", "localhost")
    port = int(os.getenv("MQTT_PORT", "1883"))
    client = mqtt.Client(client_id="mock-pv-publisher")
    client.connect(host, port)
    client.loop_start()

    print(f"[mock-pv] Publishing to {host}:{port}")

    base_w = 450.0
    while True:
        # Simulate diurnal PV curve
        hour_factor = abs((time.time() % 120) / 120 - 0.5) * 2  # 0..1 over 2 min
        power = round(base_w * hour_factor, 1)

        tasmota_state = {
            "StatusSNS": {
                "Time": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "ENERGY": {
                    "TotalStartTime": "2024-01-01T00:00:00",
                    "Total": 1000.0,
                    "Yesterday": 5.0,
                    "Today": power / 1000,
                    "Power": power,
                    "ApparentPower": power,
                    "ReactivePower": 0,
                    "Factor": 1.0,
                    "Voltage": 230,
                    "Current": round(power / 230, 2),
                },
            }
        }

        client.publish("tele/tasmota-pv/STATE", json.dumps(tasmota_state))
        client.publish("stat/tasmota-pv/RESULT", json.dumps({"POWER": "ON"}))
        time.sleep(1)


if __name__ == "__main__":
    main()
