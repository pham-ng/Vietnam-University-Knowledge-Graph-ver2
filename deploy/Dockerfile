FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VNEDU_SITE_DIR=site_server \
    VNEDU_SITE_ROOT=/

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python scripts/step7_publish.py

RUN useradd --create-home --uid 10001 vnedu \
    && chown -R vnedu:vnedu /app
USER 10001:10001

EXPOSE 8000
ENTRYPOINT ["python", "app/server.py"]
