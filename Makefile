export UV_CACHE_DIR ?= $(CURDIR)/.cache/uv
export PYTHONPATH := $(CURDIR)/backend

.PHONY: install api web import worker test build
install:
	uv sync --locked
	cd frontend && npm ci
api:
	uv run uvicorn investor.api:app --reload --host 127.0.0.1 --port 8000
web:
	cd frontend && npm run dev
import:
	uv run python -m investor.ingest
worker:
	uv run python -m investor.worker
test:
	uv run pytest -q
build:
	cd frontend && npm run build

.PHONY: test-web test-all
test-web:
	cd frontend && npm test
test-all: test test-web
	cd frontend && npm run test:unit

.PHONY: lint format test-unit check check-all
lint:
	uv run ruff check backend scripts
	uv run ruff format --check backend scripts
	cd frontend && npm run lint && npm run format:check && npm run deadcode
	uv run python scripts/check_structure.py
format:
	uv run ruff check --fix backend scripts
	uv run ruff format backend scripts
	cd frontend && npm run lint:fix && npm run format
test-unit:
	uv run pytest -q backend/tests/unit
	cd frontend && npm run test:unit
check: lint test build
	cd frontend && npm run test:unit
check-all: check test-web
