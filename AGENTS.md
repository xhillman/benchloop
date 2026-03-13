# AGENTS.md

## Project Purpose

Benchloop is a personal AI experimentation workbench.

Product intent:

- `FastAPI` is the product core and canonical API surface.
- `Next.js` is the first client, not a privileged backend.
- all product features should be reachable through backend APIs in a form that AI agents can call
- `Postgres` is the system of record

Read the PRD first for product context:

- [dev/benchloop-prd.md](/Users/xavierhillman/blackbox/code/benchloop/dev/benchloop-prd.md)

Read the repo router before non-trivial work:

- [REPO_MAP.md](/Users/xavierhillman/blackbox/code/benchloop/REPO_MAP.md)

Read the contracts and backlog before implementing features:

- [dev/contracts/README.md](/Users/xavierhillman/blackbox/code/benchloop/dev/contracts/README.md)
- [dev/contracts/BACKLOG.md](/Users/xavierhillman/blackbox/code/benchloop/dev/contracts/BACKLOG.md)

## Repository Layout

- `apps/api`
  - FastAPI backend, database layer, migrations, backend tests
- `apps/web`
  - Next.js frontend, UI components, frontend tests
- `dev`
  - PRD, contracts, backlog, and engineering notes
- `scripts`
  - repo-level scripts and CI helpers

## Architectural Rules

These are hard rules, not preferences.

1. `FastAPI` owns product behavior.
   - Do not move core product logic into the web app.
   - Do not add direct database access from the frontend.

2. All user-facing behavior must be API-accessible.
   - If the web app can do it, an agent should be able to do it through FastAPI too.
   - Favor explicit JSON contracts over UI-coupled behavior.

3. All user-owned records must include `user_id`.
   - This includes experiments, test cases, configs, runs, evaluations, context bundles, settings, and provider credentials.

4. No user-owned query may rely on `id` alone.
   - Repositories and services must require `user_id`.
   - Parent-child foreign keys are not enough for authorization.

5. Run history must be reproducible.
   - Every run stores immutable runtime snapshots.
   - Never treat mutable config rows as historical truth.

6. Provider credentials must be handled as secrets.
   - Encrypt at rest.
   - Never return plaintext after save.
   - Never log raw credentials.

7. Do not overbuild.
   - Stay inside the PRD and current contract scope.
   - Avoid generic workflow engines, auto-evals, billing, collaboration, and RAG infrastructure unless explicitly added to the plan.

## Delivery Workflow

When implementing work in this repo:

1. Open `REPO_MAP.md` and use it to constrain context to the task.
2. Identify the relevant contract in `dev/contracts`.
3. Check the backlog entry and dependency order in `dev/contracts/BACKLOG.md`.
4. Implement the smallest complete slice that satisfies the current backlog item.
5. Keep foundations boring and literal. Prefer clear names over clever abstractions.
6. Verify the work locally with the narrowest useful check.
7. Update docs if the repo structure, setup flow, or implementation contract changes.

## Current Planning Baseline

Current backlog status:

- `B001` repository skeleton is in place.
- next planned item is `B002` local infrastructure and env conventions unless directed otherwise

Do not skip ahead casually. If you choose to work out of order, explain why the dependency change is safe.

## Backend Guidance

- Organize backend code by domain, not by HTTP transport alone.
- Keep service and repository boundaries explicit.
- Prefer Pydantic schemas that are stable for both the web app and agent callers.
- Keep provider integrations behind a thin adapter layer.
- Fail closed on auth and ownership violations.

Expected backend home:

- `apps/api/src/benchloop_api`

## Frontend Guidance

- The web app is a client of FastAPI.
- Keep API calling code centralized under `apps/web/lib`.
- Build UI around the product workflows in the PRD: experiments, runs, compare, settings.
- Do not embed backend business rules in React components.

Expected frontend home:

- `apps/web/app`
- `apps/web/components`
- `apps/web/lib`

## Documentation Guidance

- Product requirements belong in `dev/benchloop-prd.md`.
- Implementation contracts belong in `dev/contracts`.
- Lightweight engineering notes belong in `dev/notes`.
- Repo routing guidance belongs in `REPO_MAP.md`.

If a change affects execution order or scope, update the relevant contract or backlog entry in the same task.
If a change affects repo structure or task routing, update `REPO_MAP.md` in the same task.

## Early-Stage Constraints

This repository is still in the foundation phase.

Until later backlog items are implemented:

- avoid introducing production deployment complexity
- avoid adding alternate clients
- avoid speculative shared packages unless two apps actually need them
- avoid heavyweight abstractions for providers, workflows, or persistence

## Done Criteria

A task is not done when code exists. It is done when:

- the implementation matches the active contract or backlog item
- the change respects the architecture rules above
- basic verification has been run or the gap is explicitly called out
- relevant docs remain accurate

## Developer Notes

- Utilize TDD (Red-Green-Refactor) whenever touching critical logic, especially in the backend. Don't skip tests, but also don't overbuild them. Focus on the core happy path and key edge cases. Tests are not required for doc changes, but are required for any new behavior or logic. Appropriate tests should be included for frontend components as well, but the same principle applies: cover the core behavior without overbuilding for every possible UI state. The goal is to have a safety net for regressions while keeping the test suite maintainable and focused on critical functionality.
- When you finish a task, run the relevant tests locally to verify the change. For backend changes, this means running the FastAPI test suite. For frontend changes, this means running the Next.js test suite. If you have made a change that affects both, run both test suites. If you have made a doc change that does not affect code behavior, you can skip tests but should still verify that the documentation is clear and accurate.
- Documentation, including README files, contracts, the PRD, enginering notes, inline code comments and docstrings, as well as this AGENTS.md file, should be updated as needed to reflect any changes in implementation, architecture, or project structure. If you make a change that affects how the system works or how developers interact with it, update the relevant documentation to ensure it remains accurate and helpful for future contributors.
- Whenever you complete a non-documentation task, include a commit message. It should be concise but descriptive enough to understand the change without looking at the code. For example, "Implement experiment creation endpoint" or "Add test for run history reproducibility".
- If you make a change that affects the execution order of tasks in the backlog, update the relevant backlog entry to reflect the new order. If you make a change that affects the scope of a task, update the relevant contract to reflect the new scope. This ensures that future work is based on accurate assumptions about dependencies and requirements.
- Anything in the dev/ directory is for internal use and intentionally gitignored. This includes the PRD, contracts, backlog, and engineering notes. Do not add any code or documentation to this directory that is meant to be shared or used by the web app or backend. If you need to share code or documentation between the web app and backend, consider whether it belongs in a shared package or if it should be duplicated with clear ownership in each app. The dev/ directory is meant for planning and internal reference only, not for production code or shared resources.
