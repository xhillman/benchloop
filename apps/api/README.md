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

Implemented in `B005`:

- `benchloop_api.api.contracts`
  - shared request and response base models with strict public-API defaults
  - reusable OpenAPI error-response docs built around the shared error envelope
  - documented Clerk bearer auth scheme injected into OpenAPI

API contract conventions:

- keep public request bodies on `ApiRequestModel`
  - strips surrounding whitespace from strings
  - forbids undeclared fields so contracts stay stable for web and agent clients
- keep public response bodies on `ApiResponseModel`
  - preserves the same strict field rules and supports loading from ORM or service objects
- document route-level error envelopes with `build_error_responses(...)`
  - use the shared `ErrorEnvelope` model instead of ad hoc error shapes
- keep API routes mounted under the shared `/api/v1` prefix constant
  - versioning stays centralized instead of being repeated per route module

Implemented in `B008`:

- `benchloop_api.auth`
  - Clerk JWT verification against the configured JWKS endpoint
  - reusable authenticated-principal dependency for protected routes
- `/api/v1/auth/me`
  - protected API proofpoint that resolves the authenticated Clerk subject

Implemented in `B009`:

- `benchloop_api.users`
  - internal `users` table model plus repository and sync service
- `benchloop_api.auth.require_current_user`
  - resolves the authenticated Clerk principal to a persisted internal user row
  - creates the user on first authenticated access and refreshes synced profile data when present
- `/api/v1/auth/me`
  - protected API proofpoint that now exercises `CurrentUser` resolution

Auth env convention:

- `CLERK_JWKS_URL`
  - JWKS endpoint used to verify Clerk-issued bearer tokens
- `CLERK_JWT_ISSUER`
  - expected token issuer for backend verification
- `CLERK_JWT_AUDIENCE`
  - expected audience when session tokens include `aud`
- `CLERK_JWKS_CACHE_TTL_SECONDS`
  - in-memory JWKS cache lifetime for the FastAPI process

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
