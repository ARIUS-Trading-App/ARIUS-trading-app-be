# syntax=docker/dockerfile:1

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

WORKDIR /app

# System deps (build tools and git for some libs that might need it)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential curl git \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry matching lockfile generator (Poetry 2.2.1) and export plugin
RUN pip install --upgrade pip \
    && pip install "poetry==2.2.1" poetry-plugin-export

# Leverage layer caching: copy only project manifest first
COPY pyproject.toml ./

# Generate a fresh lock, export to requirements, and install via pip
RUN poetry lock \
    && poetry export -f requirements.txt --output requirements.txt --without-hashes \
    && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

EXPOSE 8000

# Default command: run the FastAPI app with Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]


