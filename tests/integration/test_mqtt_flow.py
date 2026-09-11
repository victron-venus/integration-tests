"""Exercise real MQTT roundtrips and the selected dashboard's WebSocket bridge."""

import asyncio
import json
import os
import time

import pytest
import websockets

from tests.conftest import MqttClient, TestConfig


def test_mqtt_roundtrip(mqtt_client: MqttClient) -> None:
    """Publish and receive an actual message through the broker."""
    topic = "test/roundtrip"
    payload = {"timestamp": time.time(), "test": "data"}
    mqtt_client.subscribe(topic)
    # Wait for the broker to accept the subscription before publishing.
    time.sleep(0.2)
    mqtt_client.publish(topic, json.dumps(payload))
    assert mqtt_client.wait_for_message(topic) == payload


@pytest.mark.skipif(os.getenv("REQUIRE_DASHBOARD") != "1", reason="Dashboard profile not selected")
@pytest.mark.asyncio
async def test_dashboard_receives_mqtt_state(config: TestConfig, mqtt_client: MqttClient) -> None:
    """Require the selected dashboard to forward MQTT state to its WebSocket."""
    expected = {"gt": 2345, "g1": 1234, "g2": 1111, "tt": 3000, "t1": 1500, "t2": 1500}
    async with websockets.connect(config.dashboard_url, open_timeout=5) as ws:
        initial = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        assert isinstance(initial, dict)
        deadline = asyncio.get_running_loop().time() + 10
        while asyncio.get_running_loop().time() < deadline:
            mqtt_client.publish("inverter/state", json.dumps(expected))
            try:
                payload = json.loads(await asyncio.wait_for(ws.recv(), timeout=1))
            except TimeoutError:
                continue
            state = payload.get("data", payload)
            if state.get("gt") == expected["gt"]:
                assert all(state.get(key) == value for key, value in expected.items())
                return
        pytest.fail("Dashboard never forwarded the published inverter/state payload")
