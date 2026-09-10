FROM python@sha256:e06cc1111ed84189e91866447f562b89faadbfbbb9937cd67e6bf4172cdb45df
WORKDIR /app
RUN pip install --no-cache-dir --only-binary :all: paho-mqtt==2.1.0 && \
    groupadd --gid 1000 appgroup && useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser
COPY --chown=root:root --chmod=755 mock_battery.py .
USER appuser
CMD ["python", "mock_battery.py"]
