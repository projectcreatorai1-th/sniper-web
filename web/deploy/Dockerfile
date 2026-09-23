# Docker deploy (optional) — SNIPER CashFlow Analyzer Web
# Build:  docker build -f web/deploy/Dockerfile -t sniper-web .
# Run:    docker run --rm -p 8080:8080 -e WEB_PORT=8080 sniper-web
FROM python:3.12-slim

WORKDIR /app
COPY core /app/core
COPY web /app/web

ENV WEB_HOST=0.0.0.0 \
    WEB_PORT=8080 \
    PYTHONUNBUFFERED=1

EXPOSE 8080
CMD ["python", "web/backend/run_server.py"]
