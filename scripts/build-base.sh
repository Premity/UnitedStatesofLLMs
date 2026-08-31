#!/usr/bin/env bash
# Builds council-base, the shared image every Python service inherits from.
# Must run before `docker compose build` or the service builds fail with
# "image not found".
#
#   make build-base
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> Building council-base"
DOCKER_BUILDKIT=1 docker build \
    -f "$REPO_ROOT/Dockerfile.base" \
    -t council-base:latest \
    "$REPO_ROOT"

echo " ✓ council-base is ready"
