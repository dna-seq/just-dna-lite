# ──────────────────────────────────────────────────────────────────────────────
# Just-DNA-Lite Containerfile
#
# Uses the official uv base image (Python 3.13 on Debian Trixie).
# Builds and runs the full stack: Reflex Web UI + Dagster Pipelines.
#
# Build:
#   podman build -t just-dna-lite .
#
# Run (easiest — use compose):
#   podman-compose up --build
#   docker compose up --build
#
# Run manually:
#   podman run -it --rm \
#     -p 3000:3000 -p 3005:3005 -p 8000:8000 \
#     -v ./my_genomes:/app/data/input/users/default \
#     -v ./my_results:/app/data/output/users/default \
#     -v just-dna-cache:/app/data/cache \
#     -v just-dna-state:/app/data/interim \
#     just-dna-lite
#
# With environment overrides:
#   podman run -it --rm \
#     -p 3000:3000 -p 3005:3005 -p 8000:8000 \
#     -e API_URL=http://your-server:8000 \
#     -e HF_TOKEN=hf_xxx \
#     -e GEMINI_API_KEY=xxx \
#     --env-file .env \
#     -v ./my_genomes:/app/data/input/users/default \
#     -v ./my_results:/app/data/output/users/default \
#     -v just-dna-cache:/app/data/cache \
#     -v just-dna-state:/app/data/interim \
#     just-dna-lite
# ──────────────────────────────────────────────────────────────────────────────

FROM ghcr.io/astral-sh/uv:python3.13-trixie

# System dependencies for polars-bio (needs cmake), DuckDB, and general build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    lsof \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Layer 1: Install workspace dependencies (cached unless lock changes) ─────
# Copy only files needed for dependency resolution
COPY pyproject.toml uv.lock ./
COPY just-dna-pipelines/pyproject.toml just-dna-pipelines/pyproject.toml
COPY webui/pyproject.toml webui/pyproject.toml

# Minimal package stubs so uv can resolve the workspace
RUN mkdir -p src/just_dna_lite && touch src/just_dna_lite/__init__.py \
    && mkdir -p just-dna-pipelines/src/just_dna_pipelines && touch just-dna-pipelines/src/just_dna_pipelines/__init__.py \
    && mkdir -p webui/src/webui && touch webui/src/webui/__init__.py

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-workspace

# ── Layer 2: Copy full source and install workspace packages ─────────────────
COPY . /app

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen

# ── Layer 3: Runtime configuration ───────────────────────────────────────────

# Runtime directories
RUN mkdir -p data/input data/interim data/output /tmp/uv-cache

# Run as root inside the container. In Podman rootless, UID 0 maps to the
# unprivileged host user, so this carries no security risk while avoiding
# all the UID-remapping permission issues with .venv, .web, .local, etc.
USER 0
ENV HOME=/root

# Activate the venv via PATH so scripts are directly callable
ENV PATH="/app/.venv/bin:$PATH"
# Fix backend port to 8000 inside the container (no auto-discovery needed)
ENV BACKEND_PORT=8000
# Default API URL — override at runtime for external access
ENV API_URL=http://localhost:8000
# Use Granian for the backend server
ENV REFLEX_USE_GRANIAN=true
# Dagster home inside the data volume
ENV DAGSTER_HOME=/app/data/interim/dagster
# Bind Dagster to all interfaces so it's reachable from outside the container
ENV DAGSTER_HOST=0.0.0.0
# uv cache in /tmp (always writable, not persisted — deps are already installed)
ENV UV_CACHE_DIR=/tmp/uv-cache
# Compile bytecode for faster startup
ENV UV_COMPILE_BYTECODE=1
# Ensure uv uses copy mode (cache may be on different filesystem)
ENV UV_LINK_MODE=copy
# Prevent uv run from re-syncing (env is already built)
ENV UV_FROZEN=1
# Login mode (default: no auth required)
ENV JUST_DNA_PIPELINES_LOGIN=none
# Pipelines cache inside the data volume (Ensembl, Zenodo, etc.)
ENV JUST_DNA_PIPELINES_CACHE_DIR=/app/data/cache
# PRS cache inside the data volume (PGS Catalog scores, percentiles)
ENV PRS_CACHE_DIR=/app/data/cache/just-prs

# ── Layer 4: Pre-initialize Reflex (creates .web dir, installs npm deps) ──────
# Speeds up first startup by ~20-30s.
WORKDIR /app/webui
RUN reflex init
WORKDIR /app

# Ports:
#   3000 - Reflex frontend (Vite dev server)
#   3005 - Dagster web UI
#   8000 - Reflex backend API + websocket
EXPOSE 3000 3005 8000

# The start command runs both Reflex UI and Dagster pipelines.
# Called directly via PATH (venv activated via ENV) rather than `uv run`
# to avoid permission issues in Podman rootless mode.
CMD ["start"]
