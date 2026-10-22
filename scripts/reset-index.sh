#!/usr/bin/env bash
# Drops the Qdrant collection and the citation index so the next `make index`
# rebuilds from scratch.
#
# Use when the chunking strategy or embedding model changes — a collection built
# with one embedding model is meaningless when queried with another.
#
#   make reindex     (this, then make index)
set -euo pipefail

QDRANT_URL="${QDRANT_URL:-http://localhost:6333}"
COLLECTION="${QDRANT_COLLECTION:-ihl_corpus}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

read -rp "Drop Qdrant collection '$COLLECTION' and the citation index? [y/N] " confirm
if [[ ! $confirm =~ ^[yY]$ ]]; then
    echo "Cancelled."
    exit 0
fi

echo "==> Dropping collection '$COLLECTION'"
curl -fsS -X DELETE "$QDRANT_URL/collections/$COLLECTION" >/dev/null \
    && echo " ✓ collection dropped" \
    || echo " !  collection did not exist (or Qdrant is not running)"

echo "==> Resetting the citation index"
STUB="$REPO_ROOT/corpus/stub/citation_index.json"
LIVE="$REPO_ROOT/data/index/citation_index.json"
rm -f "$LIVE"
# Until the indexer emits one (T1-6), the hand-built stub IS the index, and
# deleting it leaves every citation resolving out_of_corpus. Put it back.
if [[ -f "$STUB" ]]; then
    mkdir -p "$(dirname "$LIVE")"
    cp "$STUB" "$LIVE"
    echo " ✓ restored the development stub from corpus/stub/"
else
    echo " ✓ citation index removed"
fi

echo
echo "Run 'make index' to rebuild."
