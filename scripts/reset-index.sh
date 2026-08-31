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

echo "==> Removing the citation index"
rm -f "$REPO_ROOT/data/index/citation_index.json"
echo " ✓ citation index removed"

echo
echo "Run 'make index' to rebuild."
