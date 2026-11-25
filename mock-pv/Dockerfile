FROM python@sha256:e4bc83a3314d078d651f06c8440e9a03ba892ee2f6577437f174abd8731fb343
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --only-binary :all: --require-hashes -r requirements.txt && \
    groupadd --gid 1000 appgroup && useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser
COPY --chown=root:root --chmod=755 mock_pv.py .
USER appuser
CMD ["python", "mock_pv.py"]
