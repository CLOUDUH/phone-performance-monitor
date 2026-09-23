FROM python:3.12-alpine

LABEL org.opencontainers.image.source="https://github.com/CLOUDUH/phone-performance-monitor"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv/app
RUN addgroup -S monitor && adduser -S -G monitor monitor
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN mkdir -p /data && chown -R monitor:monitor /data /srv/app
USER monitor
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD wget -q -O - http://127.0.0.1:8080/api/health || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
