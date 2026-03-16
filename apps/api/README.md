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

Implemented in `B010`:

- `benchloop_api.ownership`
  - `UserOwnedMixin` adds the required `user_id` foreign key for user-owned tables
  - `UserOwnedRepository` only exposes user-scoped list, fetch, and delete helpers
  - `UserOwnedService` turns missing-or-cross-user access into a closed `UserOwnedResourceNotFoundError`

Implemented in `B012`:

- `benchloop_api.settings`
  - SQLAlchemy models for `user_settings` and `user_provider_credentials`
  - schema choices aligned with provider defaults, encrypted key storage, and validation metadata
- `apps/api/alembic/versions/0003_add_settings_tables.py`
  - migration that creates the settings tables and ownership constraints

Implemented in `B013`:

- `benchloop_api.settings.encryption`
  - server-only encryption abstraction for provider credentials
  - shared redaction helper for secret-bearing logs and payloads
- `benchloop_api.app:create_app`
  - wires a single encryption service into application state for later settings and credential APIs

Implemented in `B014`:

- `/api/v1/settings`
  - authenticated `GET` returns the caller's default provider, model, and timezone settings
  - authenticated `PUT` creates or replaces those profile-level defaults for the current user only
- `benchloop_api.settings`
  - dedicated repository and service keep settings reads and writes scoped by `user_id`

Implemented in `B015`:

- `/api/v1/settings/credentials`
  - authenticated `GET` lists the caller's active provider credentials as masked metadata only
  - authenticated `POST` creates a new encrypted provider credential and rejects duplicate active providers
- `/api/v1/settings/credentials/{credential_id}`
  - authenticated `PUT` replaces a stored credential secret without exposing plaintext and resets validation state
  - authenticated `DELETE` soft-deletes the credential so it cannot be used for future execution
- `benchloop_api.settings`
  - dedicated credential repository and service keep credential CRUD scoped by `user_id`
  - API responses mask stored key material instead of returning plaintext

Implemented in `B016`:

- `/api/v1/settings/credentials/{credential_id}/validate`
  - authenticated `POST` performs a provider-specific key check for the caller's stored credential
  - persists `validation_status` and `last_validated_at` without returning plaintext secrets
- `benchloop_api.settings.validation`
  - thin provider credential validation adapters for OpenAI and Anthropic
  - reusable validator registry aligned with the later execution adapter contract

Implemented in `B018`:

- `apps/api/tests`
  - regression coverage for auth enforcement across all settings routes
  - cross-user credential access remains closed with not-found semantics
  - credential validation errors redact submitted secret values before returning API error details

Implemented in `B020`:

- `benchloop_api.experiments`
  - user-owned `experiments` model plus repository and service for list, create, read, update, and delete flows
  - search by name, tag filtering, and archived-state handling stay behind the FastAPI contract instead of leaking into the web app
- `/api/v1/experiments`
  - authenticated list and create endpoints for the current user's experiments
  - supports `search`, repeated `tag`, and `include_archived` query parameters
- `/api/v1/experiments/{experiment_id}`
  - authenticated read, update, and delete endpoints scoped to the owning user only
- `apps/api/alembic/versions/0004_add_experiments_table.py`
  - migration that creates the `experiments` table with tags and archive state

Implemented in `B021`:

- `benchloop_api.test_cases`
  - user-owned `test_cases` model plus repository and service for experiment-scoped list, create, update, duplicate, and delete flows
  - service methods verify both the parent experiment and the nested test case through explicit `user_id` scoping
- `/api/v1/experiments/{experiment_id}/test-cases`
  - authenticated list and create endpoints for reusable experiment test inputs
- `/api/v1/experiments/{experiment_id}/test-cases/{test_case_id}`
  - authenticated update and delete endpoints for the owning user's test cases only
- `/api/v1/experiments/{experiment_id}/test-cases/{test_case_id}/duplicate`
  - authenticated duplication endpoint that copies test case content into a new row with a new id
- `apps/api/alembic/versions/0005_add_test_cases_table.py`
  - migration that creates the `test_cases` table with ownership and experiment foreign keys

Implemented in `B022`:

- `benchloop_api.configs`
  - user-owned `configs` model plus repository and service for experiment-scoped list, create, update, clone, baseline, and delete flows
  - service methods verify both the parent experiment and the nested config through explicit `user_id` scoping
- `/api/v1/experiments/{experiment_id}/configs`
  - authenticated list and create endpoints for reusable experiment configs
- `/api/v1/experiments/{experiment_id}/configs/{config_id}`
  - authenticated update and delete endpoints for the owning user's configs only
- `/api/v1/experiments/{experiment_id}/configs/{config_id}/clone`
  - authenticated clone endpoint that copies config fields into a new row with a generated version label
- `/api/v1/experiments/{experiment_id}/configs/{config_id}/baseline`
  - authenticated baseline endpoint that promotes one config as the visible experiment baseline
- `apps/api/alembic/versions/0006_add_configs_table.py`
  - migration that creates the `configs` table with prompt, model, generation params, tags, and baseline state

Implemented in `B023`:

- `benchloop_api.execution.rendering`
  - deterministic prompt interpolation for the supported `{{input}}`, `{{context}}`, and `{{intermediate}}` variables
  - validates unsupported template variables, missing runtime values, and workflow-mode/template mismatches before execution starts
- `benchloop_api.execution.snapshots`
  - immutable Pydantic snapshot models for config, input, and optional context runtime state
  - snapshot bundle builder that captures rendered prompt text and config parameters from the current config and test case without relying on later mutable rows
- `apps/api/tests/test_execution_snapshots.py`
  - unit coverage for deterministic rendering, workflow validation, and snapshot immutability guarantees

Implemented in `B024`:

- `benchloop_api.execution.adapters`
  - normalized single-shot provider adapter contract plus OpenAI and Anthropic HTTP adapters
  - shared execution result shape for output text, token usage, latency, and optional cost metadata
- `benchloop_api.execution.service:SingleShotExecutionService`
  - resolves the caller's owned provider credential, decrypts it only for the provider call, and persists a completed or failed run outcome
- `benchloop_api.runs`
  - `runs` table model plus lifecycle service for pending, running, completed, and failed execution attempts
  - stores immutable config and input snapshot JSON alongside normalized execution metadata for later history/detail work
- `apps/api/alembic/versions/0007_add_runs_table.py`
  - migration that creates the `runs` table used by the execution pipeline foundation

Implemented in `B025`:

- `/api/v1/experiments/{experiment_id}/runs`
  - authenticated single-run launch endpoint for one config against one owned test case
- `/api/v1/experiments/{experiment_id}/runs/batch`
  - authenticated batch launch endpoint for multiple owned configs against one owned test case
- `benchloop_api.execution.service:RunLaunchService`
  - orchestration layer that validates experiment ownership and launches single or batch single-shot runs

Implemented in `B026`:

- `/api/v1/runs`
  - authenticated run history index with ownership-scoped filtering by experiment, config, provider, model, status, tag, and created date
- `benchloop_api.runs.service:RunHistoryService`
  - sortable read model for run history entries with experiment context and snapshot-derived tags

Implemented in `B027`:

- `/api/v1/runs/{run_id}`
  - authenticated run detail endpoint that returns the immutable prompt, input, context, output, usage, latency, cost, and failure-state record for one owned run
- `benchloop_api.runs.service:RunHistoryService.get`
  - ownership-scoped detail lookup for the run history surface

Implemented in `B028`:

- `/api/v1/runs/{run_id}/rerun`
  - authenticated rerun endpoint that launches a new run from the stored snapshot on an owned historical run
- `benchloop_api.execution.service:RunLaunchService.rerun_from_snapshot`
  - rebuilds the execution request from immutable snapshot JSON instead of re-reading mutable config or test case rows

Implemented in `B030`:

- `/api/v1/runs/{run_id}/evaluation`
  - authenticated manual evaluation read, upsert, and delete endpoints scoped to the owning user's run only
- `benchloop_api.runs.RunEvaluation`
  - `run_evaluations` persistence for overall score, optional dimension scores, thumbs signal, and notes
- `benchloop_api.runs.RunHistoryService`
  - folds saved manual evaluation state into the run history and run detail read models so web and agent clients stay on one source of truth

Implemented in `B031`:

- `benchloop_api.context_bundles`
  - user-owned `context_bundles` model plus repository and service for experiment-scoped list, create, update, read, and delete flows
  - deleting a bundle clears attached config defaults before the bundle row is removed so later config edits do not keep dead references
- `/api/v1/experiments/{experiment_id}/context-bundles`
  - authenticated list and create endpoints for reusable experiment-owned context text
- `/api/v1/experiments/{experiment_id}/context-bundles/{context_bundle_id}`
  - authenticated update and delete endpoints scoped to the owning user and experiment only
- `benchloop_api.configs`
  - config create and update flows now validate attached `context_bundle_id` values against the same owned experiment before saving
- `apps/api/alembic/versions/0009_add_context_bundles_table.py`
  - migration that creates `context_bundles` and adds the config-level foreign key for default bundle attachment

Ownership conventions:

- user-owned SQLAlchemy models should compose `UserOwnedMixin`
- repositories for user-owned resources should build on `UserOwnedRepository`
- service methods for user-owned resources should accept `user_id` explicitly and use `UserOwnedService` or the same not-found-on-cross-user pattern
- do not add repository methods that fetch user-owned records by `id` alone

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
- `BENCHLOOP_ENCRYPTION_KEY` should be set to a long random app secret; committed values are development-only examples
- placeholder Clerk values are committed as examples only
- `BENCHLOOP_CORS_ALLOWED_ORIGINS` accepts a JSON array and remains backward-compatible with comma-separated values

Local commands:

- `make api-sync`
  - sync the locked `uv` environment for the API package
- `make api-dev`
  - run the FastAPI app with the FastAPI CLI on `http://localhost:8000`
- `make api-lint`
  - run Ruff against the backend source and tests
- `make api-format`
  - format the backend source and tests with Ruff
- `make api-typecheck`
  - run `mypy` against the backend source and tests
- `make api-test`
  - run the backend test suite inside the locked `uv` environment
- `make api-migrate`
  - apply migrations to the configured database
- `make api-migrations-check`
  - validate that Alembic upgrades to head and autogenerate state stays clean
- `make api-revision MESSAGE="describe change"`
  - generate a new migration revision against the shared SQLAlchemy metadata
- `make api-check`
  - run the full backend quality suite used in CI

Python version:

- `apps/api/.python-version`
  - pins the API project to Python `3.12`
