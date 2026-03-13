# Web App

This directory hosts the Next.js frontend, which is the first client of the FastAPI product core.

Planned ownership:

- `app`
  - route segments and page-level UI
- `components`
  - shared UI components
- `lib`
  - API client, utilities, and app helpers
- `public`
  - static assets
- `tests`
  - frontend automated tests

Local env convention:

- copy `apps/web/.env.example` to `apps/web/.env.local`, or run `make init-env` from the repo root
- local API base URL default: `http://localhost:8000`
- Clerk keys remain placeholders until the auth backlog items land
