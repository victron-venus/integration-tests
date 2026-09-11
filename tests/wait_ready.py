"""Fail CI if the selected broker or dashboard never becomes ready."""

import asyncio
import json
import os
import socket
import time

import websockets


async def main() -> None:
    """Wait for both services or terminate with a failing exit status."""
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(
                (os.environ["MQTT_HOST"], int(os.environ["MQTT_PORT"])), timeout=2
            ):
                pass
            async with websockets.connect(os.environ["DASHBOARD_URL"], open_timeout=3) as ws:
                payload = json.loads(await asyncio.wait_for(ws.recv(), timeout=3))
                if not isinstance(payload, dict):
                    raise ValueError("Dashboard must send a JSON object")
            return
        except (OSError, TimeoutError, ValueError, websockets.exceptions.WebSocketException):
            await asyncio.sleep(1)
    raise SystemExit("MQTT broker or dashboard was not ready within 90 seconds")


if __name__ == "__main__":
    asyncio.run(main())
