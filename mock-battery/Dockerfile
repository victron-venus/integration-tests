FROM python@sha256:8edbf9e42c7fb168b9c523718ed907117e6d2e60f5889c0c499bbda3a787da53
WORKDIR /app
RUN pip install --no-cache-dir --only-binary :all: paho-mqtt==2.1.0 && \
    groupadd --gid 1000 appgroup && useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser
COPY --chown=root:root --chmod=755 mock_battery.py .
USER appuser
CMD ["python", "mock_battery.py"]
