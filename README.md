# Benchloop

Benchloop is a personal AI experimentation workbench with `FastAPI` as the product core, `Next.js` as the first client, and Postgres as the system of record.

## Repository Layout

- `apps/api`
  - FastAPI application package, database layer, Alembic migrations, and backend tests
- `apps/web`
  - Next.js client, UI components, and frontend tests
- `scripts`
  - repo-level helper scripts
- `dev`
  - internal product docs, contracts, and backlog notes

## Prerequisites

- Python `3.12`
- [`uv`](https://docs.astral.sh/uv/)
- Node.js `22` with `npm`
- Docker with Compose support

## Local Setup

1. Run `make local-up` to create missing env files and start the local Postgres container.
2. Run `make api-sync` to install the locked API environment from [`apps/api/uv.lock`](/Users/xavierhillman/blackbox/code/benchloop/apps/api/uv.lock).
3. Run `make web-install` to install the locked web dependencies from [`apps/web/package-lock.json`](/Users/xavierhillman/blackbox/code/benchloop/apps/web/package-lock.json).
4. Review the generated env files and replace placeholder secrets before using authenticated or credential-backed flows:
   - [`.env`](/Users/xavierhillman/blackbox/code/benchloop/.env)
   - [`apps/api/.env`](/Users/xavierhillman/blackbox/code/benchloop/apps/api/.env)
   - [`apps/web/.env.local`](/Users/xavierhillman/blackbox/code/benchloop/apps/web/.env.local)
5. Run `make api-migrate` if you need the local Postgres database brought to the latest Alembic revision.
6. Start the API with `make api-dev` and the web app with `make web-dev`.

Local default URLs:

- API: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- Web app: `http://localhost:3000`

When you are done, stop the local database with `make postgres-down`.

## Environment Files

- [`.env.example`](/Users/xavierhillman/blackbox/code/benchloop/.env.example)
  - docker-compose defaults for the local Postgres container
- [`apps/api/.env.example`](/Users/xavierhillman/blackbox/code/benchloop/apps/api/.env.example)
  - FastAPI runtime settings, database URL, encryption key, CORS, and Clerk verification placeholders
- [`apps/web/.env.example`](/Users/xavierhillman/blackbox/code/benchloop/apps/web/.env.example)
  - Next.js app URL, API base URL, and Clerk web placeholders

Replace placeholders before using real Clerk sessions or provider credentials. `BENCHLOOP_ENCRYPTION_KEY` must be set to a long random secret for any environment that stores credentials.

## Common Commands

- `make format`
  - format both apps
- `make lint`
  - run Ruff for the API and ESLint for the web app
- `make typecheck`
  - run `mypy` for the API and `tsc --noEmit` for the web app
- `make test`
  - run the backend and frontend automated test suites
- `make migrations-check`
  - validate that Alembic upgrades cleanly and that autogeneration is in sync
- `make check`
  - run the full repo quality suite used by CI

App-specific targets are listed in [`Makefile`](/Users/xavierhillman/blackbox/code/benchloop/Makefile) and surfaced through `make help`.

## Migrations

- `make api-migrate`
  - apply Alembic migrations to the configured database
- `make api-revision MESSAGE="describe change"`
  - generate a new Alembic revision from the current SQLAlchemy metadata
- `make api-migrations-check`
  - run the migration validation tests directly

## CI

GitHub Actions runs the same repo-level gates defined in the Makefile:

- lint
- typecheck
- tests
- migrations validation

The workflow lives at [`.github/workflows/ci.yml`](/Users/xavierhillman/blackbox/code/benchloop/.github/workflows/ci.yml).
