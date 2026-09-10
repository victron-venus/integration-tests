FROM python@sha256:e06cc1111ed84189e91866447f562b89faadbfbbb9937cd67e6bf4172cdb45df

WORKDIR /app
RUN pip install --no-cache-dir --only-binary :all: paho-mqtt==2.1.0

COPY mock_dbus.py docker_entrypoint.sh ./
RUN chmod 755 docker_entrypoint.sh && \
    useradd --create-home --shell /usr/sbin/nologin mockdbus && \
    chown -R mockdbus:mockdbus /app

USER mockdbus

ENTRYPOINT ["./docker_entrypoint.sh"]
CMD ["python", "mock_dbus.py"]
