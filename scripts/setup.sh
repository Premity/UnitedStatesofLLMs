#!/usr/bin/env bash
# First-time setup. Idempotent — safe to re-run.
#
#   make setup
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

info() { printf '\033[36m==>\033[0m %s\n' "$1"; }
warn() { printf '\033[33m!!\033[0m %s\n' "$1"; }
ok()   { printf '\033[32m ✓\033[0m %s\n' "$1"; }

# ── Prerequisites ─────────────────────────────────────────────────────────────
info "Checking prerequisites"

if ! command -v uv >/dev/null 2>&1; then
    warn "uv is not installed. Install it with:"
    echo "    curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi
ok "uv $(uv --version | awk '{print $2}')"

if ! command -v docker >/dev/null 2>&1; then
    warn "docker is not installed — see https://docs.docker.com/engine/install/"
    exit 1
fi
ok "docker $(docker --version | awk '{print $3}' | tr -d ,)"

if ! docker compose version >/dev/null 2>&1; then
    warn "docker compose v2 is not available."
    exit 1
fi
ok "docker compose $(docker compose version --short)"

# ── Environment ───────────────────────────────────────────────────────────────
info "Setting up .env"
if [[ -f .env ]]; then
    ok ".env already exists — leaving it alone"
else
    cp .env.example .env
    ok "Created .env from .env.example"
    warn "Fill in MISTRAL_API_KEY and GEMINI_API_KEY before running a debate."
fi

# ── Python ────────────────────────────────────────────────────────────────────
info "Installing Python dependencies"
uv sync --all-extras
ok "Dependencies installed"

# ── Git hooks ─────────────────────────────────────────────────────────────────
info "Installing git hooks"
uv run pre-commit install --install-hooks >/dev/null
uv run pre-commit install --hook-type commit-msg >/dev/null
ok "pre-commit and commit-msg hooks installed"

# ── Ollama ────────────────────────────────────────────────────────────────────
info "Checking Ollama (attacker models)"
if command -v ollama >/dev/null 2>&1; then
    ok "ollama found"
    echo "    Pull the attacker models if you have not already:"
    echo "      ollama pull qwen3.5:14b"
    echo "      ollama pull gemma3:12b"
else
    warn "ollama not found on the host."
    echo "    Either install it (https://ollama.com/download) — recommended —"
    echo "    or run the containerised profile:  make up-ollama"
    echo "    then set COUNCIL_OLLAMA_BASE_URL=http://ollama:11434 in .env"
fi

echo
ok "Setup complete."
echo
echo "  Next:"
echo "    1. Fill in API keys in .env"
echo "    2. make up          start the stack"
echo "    3. make corpus      fetch and index the corpus"
echo "    4. open http://localhost:3000"
echo
