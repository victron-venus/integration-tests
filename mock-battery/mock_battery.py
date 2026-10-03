#!/usr/bin/env python3
"""
Mock battery MQTT publisher for integration tests.
Simulates esphome-jbd-bms-mqtt topics consumed by dbus-mqtt-battery
(topic_prefix battery, ESPHome .../sensor/<name>/state scalar payloads).
"""

import os
import time

import paho.mqtt.client as mqtt


def main():
    host = os.getenv("MQTT_HOST", "localhost")
    port = int(os.getenv("MQTT_PORT", "1883"))
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION1,
        client_id="mock-battery-publisher",
    )
    client.connect(host, port)
    client.loop_start()

    print(f"[mock-battery] Publishing to {host}:{port}")

    soc = 78.0
    while True:
        soc = max(10.0, min(100.0, soc + (time.time() % 3 - 1) * 0.1))
        soc_s = f"{soc:.1f}"

        # Match dbus-mqtt-battery / esphome-jbd layout (battery/sensor/.../state).
        readings = {
            "battery/sensor/voltage_bms1/state": "52.4",
            "battery/sensor/current_bms1/state": "-12.5",
            "battery/sensor/soc_bms1/state": soc_s,
            "battery/sensor/voltage_cell1_bms1/state": "3.28",
            "battery/sensor/voltage_cell2_bms1/state": "3.31",
            "battery/sensor/temperature1_bms1/state": "22.5",
            "battery/sensor/voltage_total/state": "52.4",
            "battery/sensor/current_total/state": "-12.5",
            "battery/sensor/soc_total/state": soc_s,
        }

        for topic, value in readings.items():
            client.publish(topic, value)

        time.sleep(1)


if __name__ == "__main__":
    main()
