.PHONY: setup db-up db-down migrate seed-sample import-geo import-mastr dev-backend dev-frontend test lint eval mcp-inspect

setup:
	cd backend && uv sync
	cd frontend && npm install
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example - add your ANTHROPIC_API_KEY")

db-up:
	docker compose up -d

db-down:
	docker compose down

migrate:
	cd backend && uv run python manage.py migrate

seed-sample:
	cd backend && uv run python manage.py seed_sample

import-geo:
	cd backend && uv run python manage.py import_municipalities

import-mastr:
	cd backend && uv run python manage.py import_mastr

dev-backend:
	cd backend && uv run uvicorn config.asgi:application --reload --port 8000

dev-frontend:
	cd frontend && npm run dev

test:
	cd backend && uv run pytest
	cd frontend && npm test

lint:
	cd backend && uv run ruff check . && uv run ruff format --check .
	cd frontend && npm run lint

eval:
	cd backend && uv run python -m eval.run_eval

mcp-inspect:
	npx @modelcontextprotocol/inspector uv run --directory $(CURDIR)/backend python -m mcp_server.server
