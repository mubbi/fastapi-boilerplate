# syntax=docker/dockerfile:1.9
# ──────────────────────────────────────────────────────────────────
# Multi-stage production image for fastapi-boilerplate.
#
# Stage 1 (builder): locked runtime deps into an isolated venv + pybabel compile.
# Stage 2 (runtime): minimal slim image, non-root user, single SERVICE_ROLE.
#
# Dependencies are installed with `uv sync --frozen` (uv.lock is the source of
# truth) into /app/.venv, which is copied verbatim into the runtime stage.
# ──────────────────────────────────────────────────────────────────
ARG PYTHON_VERSION=3.14-slim-bookworm
ARG UV_VERSION=0.11.8

# Pinned, prebuilt uv binary — copied into the build stage (no pip bootstrap).
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

# ──────────────────────────────────────────────────────────────────
# Builder
# ──────────────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION} AS builder

COPY --from=uv /uv /usr/local/bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        build-essential \
        gettext \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install ONLY locked runtime deps first — this layer is cached until the lock
# (or pyproject) changes, so source edits never re-resolve dependencies.
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Compile .po → .mo so the runtime image ships ready-to-use catalogs.
COPY app ./app
COPY babel.cfg ./babel.cfg
RUN /app/.venv/bin/pybabel compile -d app/locales -D messages --use-fuzzy

# ──────────────────────────────────────────────────────────────────
# Runtime
# ──────────────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION} AS runtime

ARG APP_REVISION=dev
ARG APP_VERSION=0.1.0
LABEL org.opencontainers.image.title="fastapi-boilerplate" \
      org.opencontainers.image.description="Production-grade layered FastAPI backend boilerplate" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${APP_REVISION}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH=/app/.venv/bin:$PATH \
    VIRTUAL_ENV=/app/.venv \
    SERVICE_ROLE=web \
    APP_PORT=8000 \
    APP_VERSION=${APP_VERSION}

# Runtime libs only — no build toolchain.
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        libpq5 \
        curl \
        tini \
    && rm -rf /var/lib/apt/lists/*

# Non-root user.
RUN groupadd --system --gid 1000 app \
    && useradd --system --uid 1000 --gid app --create-home --home /home/app app

WORKDIR /app

# Locked dependencies (isolated venv built above), owned by the runtime user.
COPY --from=builder --chown=app:app /app/.venv /app/.venv

# Application code, migrations, and build metadata.
COPY --chown=app:app app ./app
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app alembic.ini babel.cfg pyproject.toml ./
COPY --chown=app:app docker/entrypoint.sh /usr/local/bin/entrypoint.sh
COPY --chown=app:app docker/healthcheck.sh /usr/local/bin/healthcheck.sh

# Compiled .mo catalogs from the builder (overlay the source .po tree).
COPY --from=builder --chown=app:app /app/app/locales /app/app/locales

RUN chmod +x /usr/local/bin/entrypoint.sh /usr/local/bin/healthcheck.sh

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["/usr/local/bin/healthcheck.sh"]

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]
