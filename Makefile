.PHONY: api test lint web-install web-dev

api:
	uv run uvicorn --app-dir apps/api lotus_api.main:app --reload --port 8000

test:
	uv run pytest

lint:
	uv run ruff check apps/api tests

web-install:
	npm install --prefix apps/web

web-dev:
	npm run dev --prefix apps/web
