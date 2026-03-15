.PHONY: help check-structure init-env postgres-up postgres-down postgres-logs local-up format lint typecheck test migrations-check check api-sync api-dev api-lint api-format api-typecheck api-test api-migrate api-migrations-check api-revision api-check web-install web-dev web-lint web-format web-typecheck web-test web-build web-check

help:
	@echo "Benchloop repository commands"
	@echo ""
	@echo "Available targets:"
	@echo "  make check-structure  Verify the B001 monorepo skeleton exists"
	@echo "  make init-env         Create local env files from committed examples"
	@echo "  make postgres-up      Start the local Postgres container"
	@echo "  make postgres-down    Stop the local Postgres container"
	@echo "  make postgres-logs    Tail local Postgres logs"
	@echo "  make local-up         Initialize env files and start local Postgres"
	@echo "  make api-sync         Sync the uv-managed FastAPI environment"
	@echo "  make api-dev          Run the FastAPI app locally"
	@echo "  make api-lint         Lint the FastAPI app with Ruff"
	@echo "  make api-format       Format the FastAPI app with Ruff"
	@echo "  make api-typecheck    Run the FastAPI type checks with mypy"
	@echo "  make api-test         Run the FastAPI tests"
	@echo "  make api-migrate      Apply Alembic migrations for the API package"
	@echo "  make api-migrations-check  Validate Alembic head and autogenerate state"
	@echo "  make api-revision     Generate an Alembic revision (requires MESSAGE=...)"
	@echo "  make api-check        Run the full FastAPI quality suite"
	@echo "  make web-install      Install the web app dependencies"
	@echo "  make web-dev          Run the Next.js app locally"
	@echo "  make web-lint         Lint the web app"
	@echo "  make web-format       Format the web app with Prettier"
	@echo "  make web-typecheck    Run the web TypeScript checks"
	@echo "  make web-test         Run the web test suite"
	@echo "  make web-build        Build the web app for production verification"
	@echo "  make web-check        Run the full web quality suite"
	@echo "  make lint             Run repo lint checks"
	@echo "  make typecheck        Run repo type checks"
	@echo "  make test             Run repo automated tests"
	@echo "  make migrations-check Run repo migration validation"
	@echo "  make check            Run the full repo quality suite"

check-structure:
	@test -d apps/api
	@test -d apps/web
	@test -d scripts
	@test -d dev/contracts
	@echo "Repository skeleton looks correct."

init-env:
	@./scripts/bootstrap_local_env.sh

postgres-up:
	@docker compose up -d postgres

postgres-down:
	@docker compose down

postgres-logs:
	@docker compose logs -f postgres

local-up: init-env postgres-up
	@echo "Local Postgres is ready on localhost:5432."

format: api-format web-format

lint: api-lint web-lint

typecheck: api-typecheck web-typecheck

test: api-test web-test

migrations-check: api-migrations-check

check: lint typecheck test migrations-check

api-sync:
	@uv sync --directory apps/api --group dev

api-dev:
	@uv run --directory apps/api fastapi dev src/benchloop_api/main.py --host 0.0.0.0 --port 8000

api-lint:
	@uv run --directory apps/api --group dev ruff check src tests

api-format:
	@uv run --directory apps/api --group dev ruff format src tests

api-typecheck:
	@uv run --directory apps/api --group dev mypy

api-test:
	@uv run --directory apps/api --group dev pytest

api-migrate:
	@uv run --directory apps/api --group dev alembic upgrade head

api-migrations-check:
	@uv run --directory apps/api --group dev pytest tests/test_migrations.py

api-revision:
	@test -n "$(MESSAGE)" || (echo "Usage: make api-revision MESSAGE='describe change'" && exit 1)
	@uv run --directory apps/api --group dev alembic revision --autogenerate -m "$(MESSAGE)"

api-check: api-lint api-typecheck api-test api-migrations-check

web-install:
	@npm ci --prefix apps/web

web-dev:
	@npm run --prefix apps/web dev

web-lint:
	@npm run --prefix apps/web lint

web-format:
	@npm run --prefix apps/web format

web-typecheck:
	@npm run --prefix apps/web typecheck

web-test:
	@npm run --prefix apps/web test -- --run

web-build:
	@npm run --prefix apps/web build

web-check: web-lint web-typecheck web-test
