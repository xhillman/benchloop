# API App

This directory hosts the FastAPI product core.

Current ownership:

- `src/benchloop_api`
  - application package, app factory, config loading, and API routes
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

Python version:

- `apps/api/.python-version`
  - pins the API project to Python `3.12`
