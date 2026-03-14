# Web App

This directory hosts the Next.js frontend, which is the first client of the FastAPI product core.

Current ownership:

- `app`
  - route groups, page-level shells, and shared loading or error entrypoints
- `components`
  - shared shell chrome, providers, and reusable state components
- `lib`
  - app-level configuration and future client helpers
- `tests`
  - frontend automated tests for the shell and route surfaces

Implemented in `B006`:

- App Router scaffold
  - shared root layout with design system variables and app-wide providers
  - public landing route plus dedicated shell route group for product pages
- Product shell
  - left-nav chrome for Dashboard, Experiments, Runs, and Settings
  - reusable empty, loading, and error state components
  - centralized shell loading and error state provider
- Frontend checks
  - TypeScript config, ESLint config, and Vitest plus Testing Library setup

Local commands:

- `make web-install`
  - install the committed web dependencies from `apps/web/package-lock.json`
- `make web-dev`
  - run the Next.js app on `http://localhost:3000`
- `make web-lint`
  - lint the web app
- `make web-typecheck`
  - run TypeScript with no emit
- `make web-test`
  - run the Vitest suite once
- `make web-build`
  - verify the production Next.js build

Local env convention:

- copy `apps/web/.env.example` to `apps/web/.env.local`, or run `make init-env` from the repo root
- local API base URL default: `http://localhost:8000`
- Clerk keys remain placeholders until the auth backlog items land
