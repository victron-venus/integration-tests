FROM python:3.11-slim

WORKDIR /app
RUN pip install paho-mqtt

COPY mock_dbus.py .
CMD ["python", "mock_dbus.py"]
