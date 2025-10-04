# syntax=docker/dockerfile:1

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential curl git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip \
    && pip install "poetry==2.2.1" poetry-plugin-export

COPY pyproject.toml ./

RUN poetry lock \
    && poetry export -f requirements.txt --output requirements.txt --without-hashes \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
