FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir --only-binary :all: uv==0.12.7 && \
    uv sync --frozen --no-dev --no-install-project --no-build && \
    useradd --uid 1000 --create-home appuser
COPY src/inverter_dashboard/ ./src/inverter_dashboard/
COPY VERSION ./src/inverter_dashboard/VERSION
RUN chown -R appuser /app
ENV PYTHONPATH=/app/src
USER appuser
CMD ["/app/.venv/bin/python", "-m", "inverter_dashboard", "--mqtt-host", "mqtt-broker", "--port", "8080"]
