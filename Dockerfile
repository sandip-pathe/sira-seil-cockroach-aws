FROM python:3.13-slim-bookworm AS builder

ARG UV_VERSION=0.12.1

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN python -m pip install --no-cache-dir "uv==${UV_VERSION}"

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev --no-install-project --extra worker


FROM python:3.13-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:${PATH}" \
    PYTHONPATH="/app/python:/app/python/agents:/app/services/api:/app/services/worker" \
    HOME=/tmp \
    TMPDIR=/tmp

RUN groupadd --system --gid 10001 sira \
    && useradd --system --uid 10001 --gid sira --home-dir /nonexistent --shell /usr/sbin/nologin sira

WORKDIR /app

COPY --from=builder /app/.venv ./.venv
COPY python ./python
COPY services ./services
COPY fixtures/demo ./fixtures/demo
COPY alembic.ini ./

USER sira

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "sira_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
