# Web App

This directory hosts the Next.js frontend, which is the first client of the FastAPI product core.

Current ownership:

- `app`
  - route groups, page-level shells, and shared loading or error entrypoints
- `components`
  - shared shell chrome, providers, and reusable state components
- `lib`
  - app-level configuration plus the shared FastAPI client entrypoints
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

Implemented in `B007`:

- Clerk-backed auth entrypoints
  - root `ClerkProvider`, dedicated `sign-in` and `sign-up` routes, and protected shell routing
- Signed-in shell behavior
  - shell routes require a Clerk session and surface a live user menu instead of placeholder auth copy
- Local auth env convention
  - committed placeholders for Clerk publishable and secret keys plus explicit local auth route paths

Implemented in `B011`:

- Typed FastAPI client layer
  - shared request helper under `lib/api/client.ts` with normalized FastAPI error handling
  - `lib/api/server.ts` for Clerk-authenticated server calls and `lib/api/browser.ts` for client components
- First live API-backed shell surface
  - dashboard bootstrap reads FastAPI health plus the authenticated subject through the shared client instead of placeholder-only copy

Implemented in `B017`:

- Settings workspace
  - server-rendered settings bootstrap under `app/(shell)/settings/page.tsx` reads FastAPI defaults and masked credential metadata before the client hydrates
  - client-side workspace under `components/settings` manages default provider or model updates plus credential add, replace, delete, and validate flows through the shared API client
- Typed settings client contract
  - `lib/api/client.ts` now exposes settings and provider credential request helpers for both server and browser callers
- Frontend coverage
  - Vitest coverage exercises the settings page bootstrap and the core settings mutation flows against the shared client contract

Implemented in `B020`:

- Experiments index
  - server-rendered bootstrap under `app/(shell)/experiments/page.tsx` reads the caller's experiment list from FastAPI before hydrating the client workspace
  - client workspace under `components/experiments/experiments-workspace.tsx` handles create, search, tag filtering, archive visibility, and links into detail routes
- Experiment detail shell
  - `app/(shell)/experiments/[experimentId]/page.tsx` loads one experiment through the shared FastAPI client
  - `components/experiments/experiment-detail-shell.tsx` provides the edit and delete flow plus tab navigation placeholders for test cases, configs, runs, and compare
- Typed experiment client contract
  - `lib/api/client.ts` now exposes experiment list, create, read, update, and delete helpers used by both server and browser callers
- Frontend coverage
  - Vitest coverage exercises experiments page bootstrap, list filtering, creation flow, and detail-shell editing

Implemented in `B021`:

- Experiment detail test case workspace
  - `app/(shell)/experiments/[experimentId]/page.tsx` now bootstraps experiment-scoped test cases alongside the parent experiment record
  - `components/experiments/experiment-test-cases-workspace.tsx` handles create, edit, duplicate, delete, notes, tags, and local selection state for later run-launch work
- Typed test case client contract
  - `lib/api/client.ts` now exposes experiment-scoped test case CRUD and duplication helpers shared by server and browser callers
- Frontend coverage
  - Vitest coverage now exercises the test case client contract and the experiment detail tab workflow

Local commands:

- `make web-install`
  - install the committed web dependencies from `apps/web/package-lock.json`
- `make web-dev`
  - run the Next.js app on `http://localhost:3000`
- `make web-lint`
  - lint the web app
- `make web-format`
  - format the web app with Prettier
- `make web-typecheck`
  - run TypeScript with no emit
- `make web-test`
  - run the Vitest suite once
- `make web-build`
  - verify the production Next.js build
- `make web-check`
  - run the full web quality suite used in CI

Local env convention:

- copy `apps/web/.env.example` to `apps/web/.env.local`, or run `make init-env` from the repo root
- local API base URL default: `http://localhost:8000`
- local Clerk paths default to `/sign-in` and `/sign-up`
- replace the Clerk key placeholders before testing authenticated routes locally
