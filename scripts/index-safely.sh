#!/usr/bin/env bash
# Run the indexer under a hard memory cap, so a long embedding job cannot
# take the desktop down with it.
#
#   bash scripts/index-safely.sh            # cap at 4G
#   MEM_CAP=6G bash scripts/index-safely.sh
#
# Why this exists: embedding ~2,200 spans with a 1.2GB model on a 16GB laptop
# OOM-killed the editor twice. The kernel picks its victim by score, not by
# who started the trouble, so capping the job is the only way to be sure the
# job is what dies.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-${(%):-%x}}")/.." && pwd)"
cd "$REPO_ROOT"

MEM_CAP="${MEM_CAP:-4G}"
QDRANT_URL="${QDRANT_URL:-http://localhost:6333}"

if ! curl -fsS "$QDRANT_URL/healthz" >/dev/null 2>&1; then
    echo "Qdrant is not reachable at $QDRANT_URL. Start it with: make up" >&2
    exit 1
fi

if [[ ! -d data/cache ]] || ! ls data/cache/*.json >/dev/null 2>&1; then
    echo "No fetched documents in data/cache/. Run 'make fetch' first." >&2
    exit 1
fi

echo "Indexing under a ${MEM_CAP} cap. This takes a while; the cap is what"
echo "keeps it from competing with the rest of your session."
echo

run() {
    CORPUS_DIR=corpus DATA_DIR=data QDRANT_URL="$QDRANT_URL" \
    PYTHONPATH=pipeline/indexer \
        uv run python -I -m indexer.main
}

# systemd-run gives a real cgroup limit and is present on most Linux desktops.
# Without it the job still runs, just unbounded, and we say so.
if command -v systemd-run >/dev/null 2>&1 && systemd-run --user --quiet \
        --scope -p MemoryMax="$MEM_CAP" -p MemorySwapMax=0 true 2>/dev/null; then
    systemd-run --user --quiet --scope \
        -p MemoryMax="$MEM_CAP" -p MemorySwapMax=0 \
        --unit "council-index-$$" \
        bash -c "cd '$REPO_ROOT' && CORPUS_DIR=corpus DATA_DIR=data \
            QDRANT_URL='$QDRANT_URL' PYTHONPATH=pipeline/indexer \
            uv run python -I -m indexer.main"
    status=$?
    if [[ $status -ne 0 ]]; then
        echo >&2
        echo "The indexer stopped (exit $status). If it was killed at the cap," >&2
        echo "raise it: MEM_CAP=6G bash scripts/index-safely.sh" >&2
        echo "Already-written points are kept -- point ids come from locators," >&2
        echo "so re-running overwrites rather than duplicating." >&2
    fi
    exit $status
fi

echo "systemd-run is unavailable, so there is no memory cap on this run."
echo "Close heavy applications first, or run it when you are away."
echo
run
