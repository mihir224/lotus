.PHONY: api db-up db-down migrate seed test lint web-install web-dev

api:
	uv run uvicorn --app-dir apps/api lotus_api.main:app --reload --port 8000

db-up:
	docker compose up -d db

db-down:
	docker compose down

migrate:
	uv run alembic upgrade head

seed:
	PYTHONPATH=apps/api uv run python -m lotus_api.seed

test:
	uv run pytest

lint:
	uv run ruff check apps/api tests

web-install:
	npm install --prefix apps/web

web-dev:
	npm run dev --prefix apps/web
