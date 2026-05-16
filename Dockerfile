# Stage 1: Build
FROM python:3.13-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libcairo2-dev \
    libpango1.0-dev \
    libgdk-pixbuf-2.0-dev \
    libxml2-dev \
    libxslt1-dev \
    libffi-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /build
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src/ src/

RUN uv sync --no-dev --no-editable --frozen --extra pdf

# Stage 2: Runtime
FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /build/.venv /build/.venv
ENV PATH="/build/.venv/bin:$PATH"

WORKDIR /work
ENTRYPOINT ["leafpress"]
CMD ["--help"]
