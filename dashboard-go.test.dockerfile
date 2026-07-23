# Dockerfile.test for integration testing
# Uses environment variables for MQTT connection

FROM ghcr.io/victron-venus/inverter-dashboard-go:v1.2.0

ENV MQTT_HOST=${MQTT_HOST:-mqtt-broker}
ENV MQTT_PORT=${MQTT_PORT:-1883}

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD wget -q --spider http://localhost:8080/api/state || exit 1

EXPOSE 8080

# Run as non-root user for security
USER 1000
