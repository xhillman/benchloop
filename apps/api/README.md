# API App

This directory hosts the FastAPI product core.

Planned ownership:

- `src/benchloop_api`
  - application package
- `alembic`
  - database migrations
- `tests`
  - backend automated tests

Local env convention:

- copy `apps/api/.env.example` to `apps/api/.env`, or run `make init-env` from the repo root
- local database default: `postgresql+psycopg://benchloop:benchloop@localhost:5432/benchloop`
- placeholder encryption and Clerk values are committed as examples only
