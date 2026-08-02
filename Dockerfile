FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY kgeo ./kgeo
COPY static ./static
COPY vendor/geo-optimizer-skill/src ./vendor/geo-optimizer-skill/src
RUN mkdir -p /app/data

ENV KGEO_HOST=0.0.0.0 KGEO_DATA_DIR=/app/data
EXPOSE 8080
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
