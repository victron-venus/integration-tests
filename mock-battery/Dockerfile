FROM python@sha256:b0aed0e0059e9b1527ef57689a7206f32526627b0713e2228a916df62880188a
WORKDIR /app
RUN pip install --no-cache-dir --only-binary :all: paho-mqtt==2.1.0 && \
    groupadd --gid 1000 appgroup && useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser
COPY --chown=root:root --chmod=755 mock_battery.py .
USER appuser
CMD ["python", "mock_battery.py"]
