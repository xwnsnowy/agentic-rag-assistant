# Container image for the FastAPI AI service.
#
# Why this exists: production deploys via Render (managed, no Docker) — see
# DEPLOY.md. This Dockerfile is a PORTABLE artifact proving the service can be
# containerized, and it is built + smoke-tested in CI (.github/workflows/ci.yml,
# job "docker") so correctness is verified in the cloud without needing Docker
# on the dev machine.
#
# Base: 3.12-slim (matches the CI Python and has prebuilt wheels for psycopg/
# langgraph/mcp, so the build is fast and reliable).
FROM python:3.12-slim

# PYTHONDONTWRITEBYTECODE: no .pyc clutter in the image.
# PYTHONUNBUFFERED: logs stream out immediately (good for container log viewers).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

# Install dependencies FIRST, in their own layer. Deps change far less often than
# app code, so this layer stays cached across rebuilds → much faster CI builds.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code. We intentionally do NOT copy data/ (the corpus is generated at runtime
# by fetch_corpus + ingest and lives in Postgres; list_doc_topics degrades cleanly
# if the local manifest is absent).
COPY app ./app
COPY scripts ./scripts

# Run as an unprivileged user (don't run containers as root).
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

# Shell form so ${PORT} expands — the host/port come from env, never hardcoded
# (same rule as the rest of the deploy: Render injects $PORT).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
