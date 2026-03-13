# Alembic

This directory contains the migration environment for the API package.

Local usage:

- `uv run --directory apps/api --group dev alembic upgrade head`
- `uv run --directory apps/api --group dev alembic revision --autogenerate -m "describe change"`

Notes:

- the migration environment imports `benchloop_api.db.base.Base.metadata`
- runtime database URLs come from `apps/api/.env` unless explicitly overridden
