FROM python@sha256:f17ec845ebdd4f3347431579e1c22eaeec82913f039f2a54b937c7ff870bacdb

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --only-binary :all: --require-hashes -r requirements.txt

COPY mock_dbus.py docker_entrypoint.sh ./
RUN chmod 755 docker_entrypoint.sh && \
    useradd --create-home --shell /usr/sbin/nologin mockdbus && \
    chown -R mockdbus:mockdbus /app

USER mockdbus

ENTRYPOINT ["./docker_entrypoint.sh"]
CMD ["python", "mock_dbus.py"]
