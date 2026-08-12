FROM python@sha256:3a9d2dd3f18e5c7a9d8de7b3659418a4ab848ccd409fb9e91ef9d7a6a3520ba7
WORKDIR /app
RUN pip install --no-cache-dir --only-binary :all: paho-mqtt==2.1.0 && \
    groupadd --gid 1000 appgroup && useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser
COPY --chown=root:root --chmod=755 mock_pv.py .
USER appuser
CMD ["python", "mock_pv.py"]
