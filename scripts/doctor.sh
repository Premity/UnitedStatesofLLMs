#!/usr/bin/env bash
# What state is this checkout in, and what should I run next?
#
# Read-only: it changes nothing, so it is always safe to run. Every line is
# either OK, a warning, or a thing to fix with the command to fix it.
#
#   make doctor
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

QDRANT_URL="${QDRANT_URL:-http://localhost:6333}"
COLLECTION="${QDRANT_COLLECTION:-ihl_corpus}"

if [[ -t 1 ]]; then
    G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; D=$'\033[2m'; N=$'\033[0m'
else
    G=""; Y=""; R=""; D=""; N=""
fi

todo=()
ok()   { echo "  ${G}ok${N}    $1"; }
warn() { echo "  ${Y}warn${N}  $1"; }
bad()  { echo "  ${R}no${N}    $1"; }
note() { echo "        ${D}$1${N}"; }
fix()  { todo+=("$1"); }

section() { echo; echo "$1"; }

# ── Tooling ───────────────────────────────────────────────────────────────────
section "Tooling"

if command -v uv >/dev/null 2>&1; then
    ok "uv $(uv --version 2>/dev/null | awk '{print $2}')"
else
    bad "uv not installed"; note "https://docs.astral.sh/uv/"
    fix "install uv, then: make setup"
fi

if docker info >/dev/null 2>&1; then
    ok "docker $(docker info --format '{{.ServerVersion}}' 2>/dev/null)"
    DOCKER_UP=1
else
    bad "docker is not running"
    note "Qdrant, the indexer and the dev stack all need it"
    fix "start Docker, then: make up"
    DOCKER_UP=0
fi

if command -v ollama >/dev/null 2>&1; then
    tags=$(ollama list 2>/dev/null | tail -n +2 | awk '{print $1}' | paste -sd' ' -)
    [[ -n "$tags" ]] && ok "ollama — $tags" || warn "ollama installed, no models pulled"
else
    warn "ollama not installed — the two attackers have no backend"
    note "alternatives: make up-ollama, or Cloudflare Workers AI (ADR 0006)"
fi

# ── Configuration ─────────────────────────────────────────────────────────────
section "Configuration"

if [[ -f .env ]]; then
    ok ".env exists"
    for key in GROQ_API_KEY GEMINI_API_KEY; do
        val=$(grep -E "^${key}=" .env 2>/dev/null | head -1 | cut -d= -f2-)
        if [[ -n "$val" ]]; then
            ok "$key set"
        else
            warn "$key is empty"
            note "$([[ $key == GROQ_API_KEY ]] && echo 'console.groq.com' || echo 'aistudio.google.com')"
        fi
    done
    if grep -qE "^\s*[A-Z_]+\s+=|=\s+" .env 2>/dev/null; then
        warn ".env has spaces around '=' — those lines will not parse"
    fi
else
    bad ".env missing"
    fix "make setup"
fi

# ── Citation index ────────────────────────────────────────────────────────────
section "Citation index"

STUB="corpus/stub/citation_index.json"
LIVE="data/index/citation_index.json"

if [[ -f "$LIVE" ]]; then
    read -r n_entries n_instruments < <(
        python3 -c "
import json,sys
d=json.load(open('$LIVE'))
print(len(d.get('entries',{})), len(d.get('instruments',[])))
" 2>/dev/null || echo "0 0"
    )
    if [[ "$n_entries" == "0" ]]; then
        bad "$LIVE is present but has no entries"
        fix "make fetch"
    else
        ok "$n_entries entries across $n_instruments instruments"
        if [[ -f "$STUB" ]] && cmp -s "$STUB" "$LIVE"; then
            warn "this is the placeholder index, not the real corpus"
            note "24 hand-written articles; the corpus is 23 instruments + 161 rules"
            fix "make fetch"
        fi
    fi
else
    bad "no citation index — every citation will resolve out_of_corpus"
    fix "make fetch   (or: cp $STUB $LIVE for the placeholder)"
fi

# ── Qdrant ────────────────────────────────────────────────────────────────────
section "Qdrant"

if [[ "$DOCKER_UP" == "1" ]] && curl -fsS "$QDRANT_URL/healthz" >/dev/null 2>&1; then
    ok "reachable at $QDRANT_URL"
    points=$(curl -fsS "$QDRANT_URL/collections/$COLLECTION" 2>/dev/null \
        | python3 -c "import json,sys; print(json.load(sys.stdin)['result']['points_count'])" 2>/dev/null)
    if [[ -z "$points" ]]; then
        warn "collection '$COLLECTION' does not exist yet"
        note "expected until the indexer lands (T1-5)"
        fix "make corpus   (once the fetcher and indexer are implemented)"
    elif [[ "$points" == "0" ]]; then
        warn "collection '$COLLECTION' exists but is empty"
        fix "make index"
    else
        # A partial index looks healthy from outside: the collection exists,
        # queries return results, and the spans that never got embedded are
        # simply never retrieved.
        expected=$(python3 -c "
import json
print(len(json.load(open('$LIVE')).get('entries', {})))
" 2>/dev/null || echo 0)
        if [[ "$expected" -gt 0 && "$points" -lt "$expected" ]]; then
            warn "collection holds $points points but the index has $expected entries"
            note "an interrupted index run; the missing spans are never retrieved"
            fix "make index-local"
        else
            ok "collection '$COLLECTION' holds $points points"
        fi
    fi
else
    if [[ "$DOCKER_UP" == "1" ]]; then
        warn "not reachable at $QDRANT_URL"
        fix "make up"
    else
        warn "skipped — Docker is not running"
    fi
fi

# ── Base image ────────────────────────────────────────────────────────────────
section "Base image"

if [[ "$DOCKER_UP" == "1" ]]; then
    built=$(docker image inspect council-base:latest --format '{{.Created}}' 2>/dev/null)
    if [[ -z "$built" ]]; then
        warn "council-base not built yet"
        note "make up builds it; a bare 'docker compose build' does not"
        fix "make build-base"
    else
        # council-core is installed into the base image, so an edit there
        # leaves containers importing a stale copy -- which shows up as
        # ModuleNotFoundError for a module that exists locally. Compare
        # content, not timestamps: a cached rebuild keeps the original layer
        # date, and git checkout changes mtimes without changing anything.
        # Hash the file contents alone -- paths differ between the checkout
        # and site-packages, and sorting the hashes makes order irrelevant.
        here=$(find packages/council-core/src/council_core -name '*.py' -type f \
               -exec sha1sum {} + 2>/dev/null | awk '{print $1}' | sort | sha1sum | cut -c1-12)
        there=$(docker run --rm --entrypoint sh council-base:latest -c \
                "find /usr/local/lib/python3.12/site-packages/council_core -name '*.py' -type f \
                 -exec sha1sum {} + 2>/dev/null | awk '{print \$1}' | sort | sha1sum | cut -c1-12" \
                2>/dev/null)
        if [[ -n "$there" && "$here" == "$there" ]]; then
            ok "council-base carries the current council-core"
        else
            warn "council-core has changed since council-base was built"
            note "containers will import the old copy; local runs are unaffected"
            fix "make build-base   (~90s, only needed before running containers)"
        fi
    fi
else
    warn "skipped — Docker is not running"
fi

# ── Corpus ────────────────────────────────────────────────────────────────────
section "Corpus"

fetched=$(ls data/cache/*.json 2>/dev/null | wc -l | tr -d ' ')
if [[ "$fetched" -gt 0 ]]; then
    ok "$fetched instrument(s) fetched to data/cache/"
else
    warn "nothing fetched yet — the fetcher is still a stub (T1-2)"
fi

runs=$(ls data/runs/*.json 2>/dev/null | wc -l | tr -d ' ')
if [[ "$runs" -gt 0 ]]; then
    ok "$runs saved run(s) in data/runs/"
else
    warn "no saved runs — the system has not completed a debate yet"
fi

fixture="runtime/frontend/src/fixtures/sample-run.json"
if [[ -f "$fixture" ]]; then
    ok "frontend replay fixture present"
else
    warn "no frontend fixture — the frontend track is blocked on this (T0-5)"
    note "uv run --env-file .env python scripts/record_fixture.py"
fi

# ── Next ──────────────────────────────────────────────────────────────────────
echo
if [[ ${#todo[@]} -eq 0 ]]; then
    echo "${G}Nothing to fix.${N}"
    echo "${D}Where the work is: docs/planning/implementation-plan.md${N}"
else
    echo "Next:"
    for t in "${todo[@]}"; do echo "  - $t"; done
fi
echo
