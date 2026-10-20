# Builder: resolve the locked runtime deps and bake the embedding model (FR-011).
FROM python:3.12-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    FASTEMBED_CACHE_PATH=/opt/fastembed

RUN python -m pip install uv

WORKDIR /src
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

COPY scripts/download_model.py /tmp/download_model.py
RUN /opt/venv/bin/python /tmp/download_model.py && chmod -R a+rX /opt/fastembed

# Runtime: no network needed. Model and venv are read-only copies owned by root.
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp \
    PATH=/opt/venv/bin:$PATH \
    FASTEMBED_CACHE_PATH=/opt/fastembed \
    HF_HUB_OFFLINE=1

RUN groupadd --gid 10001 easy-context \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin easy-context

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/fastembed /opt/fastembed

USER 10001:10001
WORKDIR /tmp

ENTRYPOINT ["easy-context-mcp"]
