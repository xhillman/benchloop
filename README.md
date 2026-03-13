# Benchloop

Benchloop is a personal AI experimentation workbench with `FastAPI` as the product core and `Next.js` as the first client.

## Repository Layout

- `apps/api`
  - backend application, data layer, migrations, and tests
- `apps/web`
  - frontend application and UI tests
- `dev`
  - product docs, contracts, and planning artifacts
- `scripts`
  - top-level repository scripts and helper utilities

## Local Foundation Startup

B002 establishes the local infrastructure and environment conventions that later backlog items build on.

Prerequisites:

- Docker with Compose support
- `uv`

Startup path:

1. Run `make local-up`.
2. Run `make api-sync` to create the pinned Python 3.12 API environment from `apps/api/uv.lock`.
3. Run `make api-dev` to boot the FastAPI runtime with the FastAPI CLI.
4. Review the generated env files and replace placeholder secrets before wiring real app runtimes:
   - `/.env`
   - `/apps/api/.env`
   - `/apps/web/.env.local`
5. When you are done, run `make postgres-down`.

What `make local-up` does:

- creates missing local env files from committed examples without overwriting existing values
- starts a local Postgres 16 container on `localhost:5432`

Current status:

- local Postgres bootstrapping is ready now
- FastAPI runtime scaffolding is ready through `B003`
- the API uses a `uv`-managed, locked Python environment under `apps/api`
- Next.js runtime scaffolding lands in `B006`
