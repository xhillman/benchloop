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
- Node.js with `npm`

Startup path:

1. Run `make local-up`.
2. Run `make api-sync` to create the pinned Python 3.12 API environment from `apps/api/uv.lock`.
3. Run `make web-install` to install the committed Next.js dependencies for `apps/web`.
4. Run `make api-dev` to boot the FastAPI runtime with the FastAPI CLI.
5. Run `make web-dev` in a second terminal to boot the Next.js product shell on `http://localhost:3000`.
6. Review the generated env files and replace placeholder secrets before wiring real app runtimes:
   - `/.env`
   - `/apps/api/.env`
   - `/apps/web/.env.local`
7. When you are done, run `make postgres-down`.

What `make local-up` does:

- creates missing local env files from committed examples without overwriting existing values
- starts a local Postgres 16 container on `localhost:5432`

Current status:

- local Postgres bootstrapping is ready now
- FastAPI runtime scaffolding is ready through `B003`
- SQLAlchemy base wiring and Alembic scaffolding are ready through `B004`
- FastAPI Clerk bearer-token verification is ready through `B008`
- the API uses a `uv`-managed, locked Python environment under `apps/api`
- the Next.js product shell, route groups, and frontend checks are ready through `B006`
