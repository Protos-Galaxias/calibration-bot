FROM python:3.12-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_HTTP_TIMEOUT=600
ENV UV_CONCURRENT_DOWNLOADS=2

COPY pyproject.toml .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --no-install-project

COPY src/ src/

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

CMD [".venv/bin/python", "-m", "bot.main"]
