# Usage: source scripts/dev-env.sh   (from the project root)
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -W)"
export DATA_DIR="$ROOT/data"
export PROMPTS_DIR="$ROOT/prompts"
export CORPUS_DIR="$ROOT/corpus"
export COUNCIL_OLLAMA_BASE_URL="http://localhost:11434"
export PYTHONUTF8=1
export RETRIEVAL_BACKEND=stub   # context from data/index/citation_index.json until T1 lands
echo "dev env set: DATA_DIR=$DATA_DIR RETRIEVAL_BACKEND=$RETRIEVAL_BACKEND"
