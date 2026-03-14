FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

WORKDIR /workspace

COPY --from=ghcr.io/astral-sh/uv:0.7.20 /uv /uvx /bin/

COPY pyproject.toml uv.lock README.md /workspace/
COPY src /workspace/src

RUN uv sync --locked

CMD ["uv", "run", "python", "-c", "import streamdiffusion; print('streamdiffusion import OK')"]
