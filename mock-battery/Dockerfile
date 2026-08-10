FROM python@sha256:cea0e6040540fb2b965b6e7fb5ffa00871e632eef63719f0ea54bca189ce14a6
WORKDIR /app
RUN pip install --no-cache-dir --only-binary :all: paho-mqtt==2.1.0 && \
    groupadd --gid 1000 appgroup && useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser
COPY --chown=root:root --chmod=755 mock_battery.py .
USER appuser
CMD ["python", "mock_battery.py"]
