# syntax=docker/dockerfile:1
#
# Offline corpus fetcher. Runs to completion and exits — not a long-lived service.

FROM council-base

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --no-cache \
        "httpx>=0.27" \
        "beautifulsoup4>=4.12" \
        "lxml>=5.3" \
        "pypdf>=5.1" \
        "tenacity>=9.0"

COPY pipeline/fetcher/app /app/app

CMD ["python", "-m", "app.main"]
