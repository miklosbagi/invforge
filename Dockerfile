FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY invforge ./invforge

EXPOSE 502 8080

HEALTHCHECK --interval=2s --timeout=2s --start-period=5s --retries=5 \
    CMD curl -sf http://127.0.0.1:8080/health || exit 1

ENTRYPOINT ["python", "-m", "invforge"]
CMD ["--vendor", "sigenergy", "--firmware", "V100R001C21SPC116", "--modbus-port", "502", "--control-port", "8080"]
