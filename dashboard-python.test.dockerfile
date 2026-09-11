FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir . && useradd --uid 1000 --create-home appuser && chown -R appuser /app
USER appuser
CMD ["python", "-m", "inverter_dashboard", "--mqtt-host", "mqtt-broker", "--port", "8080"]
