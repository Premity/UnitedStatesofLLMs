#!/usr/bin/env bash
# Brings up the dev stack and waits until it is actually usable.
#
#   make up
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [[ ! -f .env ]]; then
    echo "!! No .env found. Run 'make setup' first."
    exit 1
fi

bash scripts/build-base.sh
docker compose up -d

echo "==> Waiting for the API to become healthy"
for _ in $(seq 1 60); do
    if curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
        echo " ✓ API is up"
        break
    fi
    sleep 2
done

echo
echo "  Frontend  http://localhost:3000"
echo "  API docs  http://localhost:8000/docs"
echo "  Qdrant    http://localhost:6333/dashboard"
echo
