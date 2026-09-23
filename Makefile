.DEFAULT_GOAL := help
PY ?= .venv/bin/python
UV ?= uv

.PHONY: help venv install lint format typecheck test test-fast cov run migrate docker-up docker-down clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

venv: ## Create a virtualenv with uv
	$(UV) venv .venv --python 3.12

install: venv ## Install the project with dev extras
	VIRTUAL_ENV=.venv $(UV) pip install -e ".[dev]"
	.venv/bin/pre-commit install

lint: ## Ruff lint
	.venv/bin/ruff check app scripts alembic

format: ## Ruff format + autofix
	.venv/bin/ruff check app scripts alembic --fix
	.venv/bin/ruff format app scripts alembic

typecheck: ## mypy
	.venv/bin/mypy app

test: ## Full test suite with coverage
	$(PY) -m pytest -p no:cacheprovider

test-fast: ## Test suite without coverage, parallel
	$(PY) -m pytest -p no:cacheprovider --no-cov -n auto

cov: test ## Open the HTML coverage report
	open test-results/htmlcov/index.html

run: ## Run the API with reload
	$(PY) -m uvicorn app.main:app --reload --port 8000

migrate: ## Apply Alembic migrations
	.venv/bin/alembic upgrade head

docker-up: ## Start the compose stack
	docker compose up -d --build

docker-down: ## Stop the compose stack
	docker compose down

clean: ## Remove caches and build artefacts
	find . -name "__pycache__" -type d -prune -exec rm -rf {} +
	rm -rf .mypy_cache .ruff_cache .pytest_cache test-results coverage.xml build dist
