# Integration Tests

Environment for testing the complete data flow:
- MQTT broker (eclipse-mosquitto:2)
- Mock D-Bus (simulates Venus OS)
- inverter-control (real service)
- inverter-dashboard-go (real dashboard)
- pytest test runner

## Quick Start

```bash
# Run all tests
docker compose up --abort-on-container-exit

# Run specific test
docker compose run test-runner pytest tests/integration/test_mqtt_flow.py -v

# Watch logs
docker compose logs -f test-runner

# Cleanup
docker compose down -v
```

## Expected Test Flow

1. mosquitto starts (port 1883)
2. mock-dbus publishes simulated sensor data
3. inverter-control subscribes and publishes to inverter/state
4. dashboard-go subscribes to MQTT, exposes via WebSocket
5. test-runner verifies:
   - MQTT pub/sub roundtrip
   - inverter/state format
   - WebSocket state propagation

## Debugging

```bash
# Watch MQTT traffic
docker compose exec mqtt-broker mosquitto_sub -v -t '#'

# Check control publishes
docker compose exec mqtt-broker mosquitto_sub -v -t 'inverter/#'

# Test MQTT manually
docker compose run --rm test-runner python -c "
import paho.mqtt.client as mqtt
c = mqtt.Client()
c.connect('mqtt-broker', 1883)
c.subscribe('inverter/#')
c.loop_forever()
"