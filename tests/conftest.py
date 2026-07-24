"""Shared fixtures and helpers for integration tests."""

import json
import os
import socket
import time
from dataclasses import dataclass
from typing import Any

import paho.mqtt.client as mqtt
import pytest

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))


def check_socket(host: str, port: int) -> bool:
    """Check if a TCP port is reachable."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    try:
        sock.connect((host, port))
        return True
    except (TimeoutError, ConnectionRefusedError, OSError):
        return False
    finally:
        sock.close()


def is_mqtt_available() -> bool:
    """Check if MQTT broker is reachable."""
    return check_socket(MQTT_HOST, MQTT_PORT)


def is_dashboard_available() -> bool:
    """Check if dashboard is reachable."""
    url = os.getenv("DASHBOARD_URL", "ws://localhost:8080/ws")
    host_port = url.replace("ws://", "").replace("wss://", "").split("/")[0].split(":")
    host = host_port[0]
    port = int(host_port[1]) if len(host_port) > 1 else 80
    return check_socket(host, port)


@dataclass
class TestConfig:
    """Configuration for integration tests."""

    mqtt_host: str
    mqtt_port: int
    dashboard_url: str
    control_host: str


def get_config() -> TestConfig:
    """Get test configuration from environment variables."""
    return TestConfig(
        mqtt_host=os.getenv("MQTT_HOST", "localhost"),
        mqtt_port=int(os.getenv("MQTT_PORT", "1883")),
        dashboard_url=os.getenv("DASHBOARD_URL", "ws://localhost:8080/ws"),
        control_host=os.getenv("CONTROL_HOST", "inverter-control"),
    )


class MqttClient:
    """MQTT test client."""

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.client = mqtt.Client(client_id=f"test-{int(time.time())}")
        self.connected = False
        self.messages: list[dict[str, Any]] = []

        self.client.on_connect = self._on_connect  # type: ignore[method-assign]
        self.client.on_message = self._on_message  # type: ignore[method-assign]

    def _on_connect(self, _client: Any, _userdata: Any, _flags: Any, rc: int) -> None:
        if rc == 0:
            self.connected = True

    def _on_message(self, _client: Any, _userdata: Any, msg: Any) -> None:
        self.messages.append(
            {
                "topic": msg.topic,
                "payload": msg.payload.decode(),
            }
        )

    def connect(self) -> bool:
        """Connect to the MQTT broker and start the event loop."""
        self.client.connect(self.host, self.port)
        self.client.loop_start()
        for _ in range(50):
            if self.connected:
                return True
            time.sleep(0.1)
        return False

    def subscribe(self, topic: str) -> None:
        """Subscribe to an MQTT topic."""
        self.client.subscribe(topic)

    def publish(self, topic: str, payload: str) -> None:
        """Publish a message to an MQTT topic."""
        self.client.publish(topic, payload)

    def wait_for_message(self, topic: str, timeout: float = 5.0) -> dict[str, Any] | None:
        """Wait for a single message on the given topic, returning its payload or None."""
        start = time.time()
        while time.time() - start < timeout:
            for msg in self.messages:
                if msg["topic"] == topic:
                    return json.loads(msg["payload"])
            time.sleep(0.1)
        return None

    def wait_for_topic(self, topic_filter: str, timeout: float = 10.0) -> list[dict[str, Any]]:
        """Collect all messages matching a topic filter within timeout."""
        start = time.time()
        while time.time() - start < timeout:
            time.sleep(0.2)
        return [
            m for m in self.messages if topic_filter in m["topic"] or m["topic"] == topic_filter
        ]

    def messages_on(self, topic: str) -> list[dict[str, Any]]:
        """Return all messages received on a specific topic."""
        return [m for m in self.messages if m["topic"] == topic]

    def disconnect(self) -> None:
        """Disconnect from the MQTT broker and stop the event loop."""
        self.client.loop_stop()
        self.client.disconnect()


@pytest.fixture
def config() -> TestConfig:
    """Provide test configuration fixture."""
    return get_config()


@pytest.fixture
def mqtt_client(config: TestConfig) -> MqttClient:
    """Provide MQTT client fixture."""
    if not is_mqtt_available():
        pytest.skip("MQTT broker not available")
    client = MqttClient(config.mqtt_host, config.mqtt_port)
    if not client.connect():
        pytest.skip("Failed to connect to MQTT broker")
    yield client
    client.disconnect()
