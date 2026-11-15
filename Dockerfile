FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev libpq5 postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt alembic pgspecial PyGreSQL

COPY stma ./stma
RUN useradd --create-home --uid 10001 stma \
    && mkdir -p /app/storage \
    && chown -R stma:stma /app

USER stma
EXPOSE 8000
CMD ["uvicorn", "stma.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
