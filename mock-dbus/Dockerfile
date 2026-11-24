FROM python@sha256:c3f4160f1cceaf4daa49e2b0b693cae9bb2405efe9e8f8f519dde1ea6c831248

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
