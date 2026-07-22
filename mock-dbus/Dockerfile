FROM python:3.11-slim

WORKDIR /app
RUN pip install --no-cache-dir --only-binary :all: paho-mqtt==2.1.0

COPY mock_dbus.py docker_entrypoint.sh .
RUN chmod 644 docker_entrypoint.sh

ENTRYPOINT ["./docker_entrypoint.sh"]
CMD ["python", "mock_dbus.py"]
