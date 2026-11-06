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
