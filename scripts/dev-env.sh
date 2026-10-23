# Usage: source scripts/dev-env.sh   (from the project root)
# This file is sourced, so $0 is the shell, not the script. bash and zsh each
# expose the sourced path differently, and `pwd -W` gives a Windows path under
# Git Bash but is not an option anywhere else.
_src="${BASH_SOURCE[0]:-${(%):-%x}}"
ROOT="$(cd "$(dirname "$_src")/.." && { pwd -W 2>/dev/null || pwd; })"
unset _src
export DATA_DIR="$ROOT/data"
export PROMPTS_DIR="$ROOT/prompts"
export CORPUS_DIR="$ROOT/corpus"
export COUNCIL_OLLAMA_BASE_URL="http://localhost:11434"
# Compose resolves `qdrant` on its own network; from the host it is localhost.
export QDRANT_URL="${QDRANT_URL:-http://localhost:6333}"
export PYTHONUTF8=1
# The real corpus now exists (T1), so retrieval goes to Qdrant. Set
# RETRIEVAL_BACKEND=stub by hand only to work without Qdrant running -- it
# serves word-overlap matches from the citation index and is not semantic
# search, so it must never be used for a scored run.
export RETRIEVAL_BACKEND="${RETRIEVAL_BACKEND:-qdrant}"
echo "dev env set: DATA_DIR=$DATA_DIR RETRIEVAL_BACKEND=$RETRIEVAL_BACKEND"
