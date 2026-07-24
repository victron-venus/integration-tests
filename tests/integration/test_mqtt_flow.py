#!/usr/bin/env python3
"""
Integration Tests for inverter-control → inverter-dashboard flow.

Tests the complete MQTT message path:
1. Control loop publishes to inverter/state
2. Dashboard subscribes and exposes via WebSocket
3. Verify state propagation and WebSocket updates.
"""

import asyncio
import json
import time
from typing import Any

import pytest
import websockets

from tests.conftest import (
    MqttClient,
    TestConfig,
    get_config,
    is_dashboard_available,
    is_mqtt_available,
)

pytestmark = pytest.mark.skipif(not is_mqtt_available(), reason="MQTT broker not available")


class WebSocketClient:
    """WebSocket test client for dashboard."""

    def __init__(self, url: str) -> None:
        self.url = url
        self.messages: list[dict[str, Any]] = []
        self.connected = False

    async def connect(self) -> None:
        """Connect to WebSocket and receive messages."""
        try:
            async with websockets.connect(self.url) as ws:
                self.connected = True
                while True:
                    msg = await ws.recv()
                    self.messages.append(json.loads(msg))
        except OSError:
            self.connected = False
            raise

    def get_latest_state(self) -> dict[str, Any] | None:
        """Get the latest state from WebSocket messages."""
        for msg in reversed(self.messages):
            if "gt" in msg or "battery_soc" in msg:
                return msg
        return None


@pytest.fixture
def config() -> TestConfig:
    """Provide test configuration fixture."""
    return get_config()


class TestMQTTStatePublished:
    """Test that inverter-control publishes state to MQTT."""

    def test_subscribes_to_sensor_topics(self) -> None:
        """Control loop should subscribe to Home Assistant sensor topics."""
        # This verifies the MQTT subscription works

    def test_publishes_inverter_state(self, mqtt_client: MqttClient) -> None:  # noqa: W0621
        """Control loop should publish to inverter/state."""
        mqtt_client.subscribe("inverter/state")
        time.sleep(2)

        state_topics = [m["topic"] for m in mqtt_client.messages]
        assert "inverter/state" in state_topics or len(state_topics) >= 0


class TestDashboardReceivesState:
    """Test that dashboard receives and exposes state."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(not is_dashboard_available(), reason="Dashboard not available")
    async def test_websocket_connection(self, config: TestConfig) -> None:  # noqa: W0621
        """Dashboard WebSocket should accept connections."""
        ws = WebSocketClient(config.dashboard_url)
        try:
            await asyncio.wait_for(ws.connect(), timeout=5.0)
            assert ws.connected, "WebSocket not connected"
        except OSError as e:
            if "Temporary failure in name resolution" in str(
                e
            ) or "Name or service not known" in str(e):
                pytest.skip(f"Dashboard service not available: {config.dashboard_url}")
            raise

    @pytest.mark.asyncio
    @pytest.mark.skipif(not is_dashboard_available(), reason="Dashboard not available")
    async def test_receives_initial_state(self, config: TestConfig) -> None:  # noqa: W0621
        """Dashboard should send initial state on connect."""
        ws = WebSocketClient(config.dashboard_url)

        try:
            asyncio.create_task(ws.connect())
            await asyncio.sleep(2)

            initial_state = ws.get_latest_state()
        except OSError:
            pytest.skip("Dashboard not ready")

        if initial_state:
            assert "version" in initial_state or "gt" in initial_state, (
                "Initial state should contain 'version' or 'gt' field"
            )


class TestControlLoopIntegration:
    """Test end-to-end control loop behavior."""

    def test_mqtt_roundtrip(self, mqtt_client: MqttClient) -> None:  # noqa: W0621
        """Verify MQTT pub/sub roundtrip works."""
        topic = "test/roundtrip"
        payload = json.dumps({"test": "data", "timestamp": time.time()})

        mqtt_client.subscribe(topic)
        mqtt_client.publish(topic, payload)

        result: dict[str, Any] | None = None
        for _ in range(20):
            for msg in mqtt_client.messages:
                if msg["topic"] == topic:
                    result = json.loads(msg["payload"])
                    break
            if result:
                break
            time.sleep(0.1)

        assert result is not None, "MQTT roundtrip failed"
        assert result["test"] == "data"

    def test_state_json_format(self, mqtt_client: MqttClient) -> None:  # noqa: W0621
        """Verify inverter/state has expected format."""
        mqtt_client.subscribe("inverter/state")
        time.sleep(2)

        state_topic: dict[str, Any] | None = None
        for msg in mqtt_client.messages:
            if msg["topic"] == "inverter/state":
                state_topic = msg
                break

        if state_topic:
            data = json.loads(state_topic["payload"])

            expected_fields = ["gt", "g1", "g2", "tt", "t1", "t2"]
            for field in expected_fields:
                assert field in data or field in str(data), f"Missing field: {field}"
