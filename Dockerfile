# Base images are pinned by digest so builds are reproducible and a re-pushed
# tag can't silently change what we ship. Dependabot proposes digest updates.

# Stage 1: Build
FROM python:3.13-slim@sha256:7c61056e61ac89e852de05f3dc6fa51a6dd2181797bceed46aa725dd7cb2cd3b AS builder

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

COPY --from=ghcr.io/astral-sh/uv:0.12.18@sha256:3adc3706091ce7c2fe595e669628caedd6d951551b92b258b7e7dbe06d9440bc /uv /usr/local/bin/uv

WORKDIR /build
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src/ src/

RUN uv sync --no-dev --no-editable --frozen --extra pdf

# Stage 2: Runtime
FROM python:3.13-slim@sha256:7c61056e61ac89e852de05f3dc6fa51a6dd2181797bceed46aa725dd7cb2cd3b

RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    git \
    && rm -rf /var/lib/apt/lists/* \
    # The mounted project is usually owned by a different UID than the
    # container user; without this git refuses to read it and version info
    # is silently dropped.
    && git config --system --add safe.directory '*' \
    # Unprivileged user for `docker run --user leafpress` (or --user $(id -u):$(id -g))
    && useradd --create-home --uid 10001 leafpress

COPY --from=builder /build/.venv /build/.venv
ENV PATH="/build/.venv/bin:$PATH"

WORKDIR /work
ENTRYPOINT ["leafpress"]
CMD ["--help"]
