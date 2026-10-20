FROM python@sha256:e748956ccf3f50c9555f236753bbcd5f430d3937e665d3bd6922dd0e6e591a24
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --only-binary :all: --require-hashes -r requirements.txt && \
    groupadd --gid 1000 appgroup && useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser
COPY --chown=root:root --chmod=755 mock_pv.py .
USER appuser
CMD ["python", "mock_pv.py"]
