FROM python:3.12-slim AS builder

ARG UV_VERSION=0.9.26

WORKDIR /build

ENV UV_PROJECT_ENVIRONMENT=/app/.venv

RUN python -m pip install --no-cache-dir "uv==${UV_VERSION}"

COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src

RUN uv sync --frozen --no-dev --no-editable


FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.source="https://github.com/MohamedElashri/inspirehep-mcp" \
      org.opencontainers.image.description="Read-only MCP server for the public INSPIRE HEP API" \
      org.opencontainers.image.licenses="AGPL-3.0-only"

RUN groupadd --system inspirehep \
    && useradd --system --gid inspirehep --home-dir /app inspirehep \
    && mkdir -p /app \
    && chown inspirehep:inspirehep /app

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

USER inspirehep

ENV INSPIREHEP_TRANSPORT=streamable-http \
    INSPIREHEP_HOST=0.0.0.0 \
    PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; port = os.getenv('INSPIREHEP_PORT', os.getenv('PORT', '8000')); urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=3)"]

CMD ["/app/.venv/bin/inspirehep-mcp"]
