# ── United States of LLMs ─────────────────────────────────────────────────────
# One entrypoint for every routine task. Run `make` or `make help` for the list.
#
# Targets stay short; anything longer than a few lines lives in scripts/.

.DEFAULT_GOAL := help
SHELL := /bin/bash

COMPOSE      := docker compose
COMPOSE_PROD := docker compose -f docker-compose.yml -f docker-compose.prod.yml
COMPOSE_PIPE := docker compose -f pipeline/docker-compose.yml

.PHONY: help
help: ## Show this help
	@echo ""
	@echo "  United States of LLMs — development commands"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
	@echo ""

# ── Setup ─────────────────────────────────────────────────────────────────────

.PHONY: setup
setup: ## First-time setup: env file, Python deps, git hooks
	@bash scripts/setup.sh

.PHONY: env
env: ## Create .env from .env.example if it does not exist
	@test -f .env || (cp .env.example .env && echo "Created .env — fill in your API keys.")

.PHONY: sync
sync: ## Install/update Python dependencies (uv)
	uv sync --all-extras

.PHONY: hooks
hooks: ## Install the pre-commit and commit-msg git hooks
	uv run pre-commit install --install-hooks
	uv run pre-commit install --hook-type commit-msg

# ── Docker: development ───────────────────────────────────────────────────────

.PHONY: build-base
build-base: ## Build the shared council-base image (run before build/up)
	@bash scripts/build-base.sh

.PHONY: build
build: build-base ## Build all service images
	$(COMPOSE) build

.PHONY: up
up: build-base ## Start the dev stack (hot reload, ports exposed)
	$(COMPOSE) up -d
	@echo ""
	@echo "  Frontend  http://localhost:3000"
	@echo "  API       http://localhost:8000/docs"
	@echo "  Qdrant    http://localhost:6333/dashboard"
	@echo ""

.PHONY: up-ollama
up-ollama: build-base ## Start the dev stack with a containerised Ollama
	$(COMPOSE) --profile ollama up -d

.PHONY: down
down: ## Stop the stack
	$(COMPOSE) down

.PHONY: restart
restart: down up ## Restart the stack

.PHONY: logs
logs: ## Tail all logs (make logs S=api for one service)
	$(COMPOSE) logs -f $(S)

.PHONY: ps
ps: ## Show running containers
	$(COMPOSE) ps

.PHONY: shell
shell: ## Open a shell in the api container
	$(COMPOSE) exec api /bin/bash

# ── Docker: production ────────────────────────────────────────────────────────

.PHONY: prod-build
prod-build: build-base ## Build production images
	$(COMPOSE_PROD) build

.PHONY: prod-up
prod-up: build-base ## Start the production stack
	$(COMPOSE_PROD) up -d

.PHONY: prod-down
prod-down: ## Stop the production stack
	$(COMPOSE_PROD) down

.PHONY: prod-logs
prod-logs: ## Tail production logs
	$(COMPOSE_PROD) logs -f $(S)

# ── Corpus pipeline ───────────────────────────────────────────────────────────

.PHONY: fetch
fetch: ## Download the curated corpus (reads corpus/manifests/)
	$(COMPOSE_PIPE) run --rm fetcher

.PHONY: index
index: ## Chunk, embed, and index the corpus (runtime stack must be up)
	$(COMPOSE_PIPE) run --rm indexer

.PHONY: corpus
corpus: fetch index ## Fetch and index in one go

.PHONY: reindex
reindex: ## Wipe the Qdrant collection and rebuild the index
	@bash scripts/reset-index.sh
	$(MAKE) index

# ── Quality ───────────────────────────────────────────────────────────────────

.PHONY: lint
lint: ## Lint Python (ruff) and type-check the frontend
	uv run ruff check .
	uv run ruff format --check .
	@cd runtime/frontend && npx tsc --noEmit

.PHONY: fmt
fmt: ## Auto-fix lint issues and format
	uv run ruff check --fix .
	uv run ruff format .

.PHONY: test
test: ## Run the unit test suite (fast, no network, no model calls)
	uv run pytest

.PHONY: test-cov
test-cov: ## Run tests with a coverage report
	uv run pytest --cov=council_core --cov=app --cov-report=term-missing

.PHONY: check
check: lint test ## Everything CI runs, locally

# ── Evaluation ────────────────────────────────────────────────────────────────

.PHONY: eval
eval: ## Run the full ablation harness (SLOW — consumes API quota)
	uv run python -m harness.run --all-arms

.PHONY: eval-arm
eval-arm: ## Run one arm, e.g. make eval-arm ARM=full_council
	uv run python -m harness.run --arm $(ARM)

.PHONY: eval-report
eval-report: ## Rebuild the evaluation report from existing results
	uv run python -m metrics.report

# ── Housekeeping ──────────────────────────────────────────────────────────────

.PHONY: clean
clean: ## Remove caches and build artifacts (keeps data/ and corpus/)
	find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -prune -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf runtime/frontend/dist runtime/frontend/.vite htmlcov .coverage

.PHONY: clean-runs
clean-runs: ## Delete all saved debate runs (destructive)
	@read -p "Delete every run in data/runs/? [y/N] " ok && [[ $$ok == [yY] ]] && rm -rf data/runs/* || echo "Cancelled."

.PHONY: nuke
nuke: down ## Stop everything and remove volumes (destructive — wipes the index)
	@read -p "Remove all Docker volumes, including the Qdrant index? [y/N] " ok && [[ $$ok == [yY] ]] && $(COMPOSE) down -v || echo "Cancelled."
