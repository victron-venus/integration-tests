#!/usr/bin/env python3
"""
Mock battery MQTT publisher for integration tests.
Simulates esphome-jbd-bms-mqtt / dbus-mqtt-battery input topics.
"""

import json
import os
import time

import paho.mqtt.client as mqtt


def main():
    host = os.getenv("MQTT_HOST", "localhost")
    port = int(os.getenv("MQTT_PORT", "1883"))
    client = mqtt.Client(client_id="mock-battery-publisher")
    client.connect(host, port)
    client.loop_start()

    print(f"[mock-battery] Publishing to {host}:{port}")

    soc = 78.0
    while True:
        soc = max(10.0, min(100.0, soc + (time.time() % 3 - 1) * 0.1))

        readings = {
            "jbd/bms/1/voltage": 52.4,
            "jbd/bms/1/current": -12.5,
            "jbd/bms/1/soc": round(soc, 1),
            "jbd/bms/1/cell_voltage_min": 3.28,
            "jbd/bms/1/cell_voltage_max": 3.31,
            "jbd/bms/1/temperature": 22.5,
        }

        for topic, value in readings.items():
            client.publish(topic, json.dumps({"value": value}))

        client.publish(
            "jbd/bms/1/state",
            json.dumps({"voltage": 52.4, "current": -12.5, "soc": round(soc, 1)}),
        )
        time.sleep(1)


if __name__ == "__main__":
    main()
