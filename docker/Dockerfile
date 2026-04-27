# syntax=docker/dockerfile:1.7
# ──────────────────────────────────────────────────────────────────
# Multi-stage Dockerfile for fastapi-boilerplate.
#
# Stage 1 (builder): system deps, Python deps, pybabel compile of .mo files.
# Stage 2 (runtime): minimal slim image, non-root user, single SERVICE_ROLE.
# ──────────────────────────────────────────────────────────────────
ARG PYTHON_VERSION=3.14-slim-bookworm

FROM python:${PYTHON_VERSION} AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        build-essential \
        gettext \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY pyproject.toml uv.lock README.md ./

# Install runtime dependencies exactly as locked (no dev extra).
RUN pip install --upgrade pip wheel uv \
    && uv export --frozen --no-dev --no-emit-workspace -o /tmp/requirements.txt \
    && pip install --prefix=/install -r /tmp/requirements.txt

# Must use --ignore-installed: otherwise pip skips (satisfied in image /usr/local) and nothing
# lands under /install; the runtime stage then copies /install over site-packages and drops it.
RUN pip install --prefix=/install --ignore-installed "packaging>=24.0"

COPY app ./app
COPY babel.cfg ./babel.cfg

# Compile .po → .mo so the runtime image ships ready-to-use catalogs.
RUN PYTHONPATH=/install/lib/python3.14/site-packages \
    python -m babel.messages.frontend compile \
    --directory app/locales \
    --domain messages \
    --use-fuzzy

# ──────────────────────────────────────────────────────────────────
# Runtime stage
# ──────────────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION} AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    SERVICE_ROLE=web \
    APP_PORT=8000

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

# Copy installed Python deps from the builder.
COPY --from=builder /install /usr/local

WORKDIR /app

# Copy application code, locales, and templates only.
COPY --chown=app:app app ./app
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app alembic.ini ./alembic.ini
COPY --chown=app:app babel.cfg ./babel.cfg
COPY --chown=app:app pyproject.toml ./pyproject.toml
COPY --chown=app:app docker/entrypoint.sh /usr/local/bin/entrypoint.sh
COPY --chown=app:app docker/healthcheck.sh /usr/local/bin/healthcheck.sh

# Copy compiled .mo catalogs from the builder, if present.
COPY --from=builder /build/app/locales /app/app/locales

RUN chmod +x /usr/local/bin/entrypoint.sh /usr/local/bin/healthcheck.sh

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["/usr/local/bin/healthcheck.sh"]

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]
