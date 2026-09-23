FROM python@sha256:be8ccd085666c34273c9dc5607c9842f8b2e3116128aae45148ce164c07ce09d

WORKDIR /app
RUN pip install --no-cache-dir --only-binary :all: paho-mqtt==2.1.0

COPY mock_dbus.py docker_entrypoint.sh ./
RUN chmod 755 docker_entrypoint.sh && \
    useradd --create-home --shell /usr/sbin/nologin mockdbus && \
    chown -R mockdbus:mockdbus /app

USER mockdbus

ENTRYPOINT ["./docker_entrypoint.sh"]
CMD ["python", "mock_dbus.py"]
