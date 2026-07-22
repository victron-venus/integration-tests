FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir --only-binary :all: paho-mqtt==2.1.0
RUN groupadd --gid 1000 appgroup && useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser
COPY --chown=appuser:appgroup mock_pv.py .
USER appuser
CMD ["python", "mock_pv.py"]
