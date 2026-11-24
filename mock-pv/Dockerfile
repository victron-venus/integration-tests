FROM python@sha256:c3f4160f1cceaf4daa49e2b0b693cae9bb2405efe9e8f8f519dde1ea6c831248
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --only-binary :all: --require-hashes -r requirements.txt && \
    groupadd --gid 1000 appgroup && useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser
COPY --chown=root:root --chmod=755 mock_pv.py .
USER appuser
CMD ["python", "mock_pv.py"]
