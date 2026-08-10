FROM python@sha256:3a9d2dd3f18e5c7a9d8de7b3659418a4ab848ccd409fb9e91ef9d7a6a3520ba7

WORKDIR /app
RUN pip install --no-cache-dir --only-binary :all: paho-mqtt==2.1.0

COPY mock_dbus.py docker_entrypoint.sh ./
RUN chmod 755 docker_entrypoint.sh && \
    useradd --create-home --shell /usr/sbin/nologin mockdbus && \
    chown -R mockdbus:mockdbus /app

USER mockdbus

ENTRYPOINT ["./docker_entrypoint.sh"]
CMD ["python", "mock_dbus.py"]
