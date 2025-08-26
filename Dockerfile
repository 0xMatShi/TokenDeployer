# Part 1: production-grade multi-stage Dockerfile for TokenDeployer
# - Uses slim Python image
# - Creates non-root user
# - Installs only required system deps
# - Copies application code and installs pinned requirements
# - Does NOT bake any secrets into image

# Build stage: install dependencies
FROM python:3.12.11-slim AS builder

# Avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install build-time dependencies (kept minimal)
RUN apt-get update \
  && apt-get install -y --no-install-recommends build-essential ca-certificates git \
  && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy dependency files first for layer caching
COPY requirements.txt /app/requirements.txt

# Install wheel & dependencies into a target directory (no virtualenv)
RUN python -m pip install --upgrade pip setuptools wheel \
  && python -m pip install --prefix=/install -r /app/requirements.txt

# Final stage: smaller runtime image
FROM python:3.12.11-slim

ENV PYTHONUNBUFFERED=1 \
    # Do NOT put secrets here. Vault address can be configured at runtime via service discovery / Docker network.
    APP_HOME=/home/app

# Create a non-root user and group
RUN groupadd -r app && useradd --no-log-init -r -g app -d ${APP_HOME} -s /sbin/nologin app \
  && mkdir -p ${APP_HOME}/TokenDeployer \
  && chown -R app:app ${APP_HOME}

WORKDIR ${APP_HOME}/TokenDeployer

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY --chown=app:app . .

# Create a non-writable log directory for runtime-managed logs (mounted or captured by platform)
RUN mkdir -p /var/log/token_deployer && chown app:app /var/log/token_deployer

# Switch to non-root user
USER app

# Expose only what is needed (no Vault ports here)
EXPOSE 8000

# Healthcheck (simple): attempt to run a small script that checks app can import package
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s CMD python -c "import src.logger" || exit 1

# Entrypoint: run main.py (do not include secrets)
ENTRYPOINT ["python", "main.py"]
