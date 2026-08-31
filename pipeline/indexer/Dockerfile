# syntax=docker/dockerfile:1
#
# Offline indexer: chunks the corpus, embeds it, writes Qdrant + the citation index.
# Runs to completion and exits.

FROM council-base

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --no-cache \
        "fastembed>=0.4.2" \
        "qdrant-client>=1.12"

# Bake the ONNX embedding weights into the image so the first run does not
# stall on a download.
RUN python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='BAAI/bge-m3')"

COPY pipeline/indexer/app /app/app

CMD ["python", "-m", "app.main"]
