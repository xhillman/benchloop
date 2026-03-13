# API App

This directory hosts the FastAPI product core.

Current ownership:

- `src/benchloop_api`
  - application package, app factory, config loading, API routes, and database helpers
- `alembic`
  - database migrations
- `tests`
  - backend automated tests for the FastAPI runtime

Implemented in `B003`:

- `benchloop_api.app:create_app`
  - centralized FastAPI factory with `/api/v1` router registration
- `benchloop_api.config.AppSettings`
  - `pydantic-settings` runtime config loaded from `apps/api/.env`
- `benchloop_api.errors`
  - shared JSON error envelope for HTTP, validation, and unexpected errors
- `/api/v1/health`
  - boot-time health check for local verification

Implemented in `B004`:

- `benchloop_api.db`
  - SQLAlchemy engine/session helpers, declarative base, and shared UUID plus timestamp mixins
- `apps/api/alembic.ini`
  - Alembic entrypoint configured against the application metadata
- `apps/api/alembic`
  - migration environment and baseline revision scaffold

Local env convention:

- copy `apps/api/.env.example` to `apps/api/.env`, or run `make init-env` from the repo root
- local database default: `postgresql+psycopg://benchloop:benchloop@localhost:5432/benchloop`
- placeholder encryption and Clerk values are committed as examples only
- `BENCHLOOP_CORS_ALLOWED_ORIGINS` accepts a JSON array and remains backward-compatible with comma-separated values

Local commands:

- `make api-sync`
  - sync the locked `uv` environment for the API package
- `make api-dev`
  - run the FastAPI app with the FastAPI CLI on `http://localhost:8000`
- `make api-test`
  - run the backend test suite inside the locked `uv` environment
- `make api-migrate`
  - apply migrations to the configured database
- `make api-revision MESSAGE="describe change"`
  - generate a new migration revision against the shared SQLAlchemy metadata

Python version:

- `apps/api/.python-version`
  - pins the API project to Python `3.12`
