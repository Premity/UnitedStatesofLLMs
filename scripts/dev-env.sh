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
export PYTHONUTF8=1
export RETRIEVAL_BACKEND=stub   # context from data/index/citation_index.json until T1 lands
echo "dev env set: DATA_DIR=$DATA_DIR RETRIEVAL_BACKEND=$RETRIEVAL_BACKEND"
