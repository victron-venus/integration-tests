FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir paho-mqtt==2.1.0
COPY mock_pv.py .
CMD ["python", "mock_pv.py"]
