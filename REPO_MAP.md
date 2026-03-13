# REPO_MAP.md

## Purpose

This file is the primary context router for work in this repository.

Use it to minimize context usage while preserving enough cohesion to make correct changes.

## Required Workflow

For any non-trivial task:

1. Open this file first.
2. Identify the task type.
3. Read only the files listed for that task type.
4. Read additional files only when the mapped files point to them or when execution proves they are necessary.
5. If you change repo structure, ownership boundaries, or task routing, update this file in the same task.

## Global Authority Files

These files define project intent and execution order. Read them only when needed by the task.

- [AGENTS.md](/Users/xavierhillman/blackbox/code/benchloop/AGENTS.md)
  - repo operating rules and architecture constraints
- [dev/benchloop-prd.md](/Users/xavierhillman/blackbox/code/benchloop/dev/benchloop-prd.md)
  - product requirements and scope authority
- [dev/contracts/README.md](/Users/xavierhillman/blackbox/code/benchloop/dev/contracts/README.md)
  - implementation contract index
- [dev/contracts/BACKLOG.md](/Users/xavierhillman/blackbox/code/benchloop/dev/contracts/BACKLOG.md)
  - execution sequence and current backlog baseline

## Repository Areas

- [apps/api](/Users/xavierhillman/blackbox/code/benchloop/apps/api)
  - FastAPI product core, data layer, migrations, backend tests
- [apps/web](/Users/xavierhillman/blackbox/code/benchloop/apps/web)
  - Next.js client, UI components, frontend tests
- [scripts](/Users/xavierhillman/blackbox/code/benchloop/scripts)
  - repo-level automation and CI helpers
- [dev](/Users/xavierhillman/blackbox/code/benchloop/dev)
  - internal planning docs only, not production code

## Task Routing

### 1. Product Planning Or Scope Changes

Use when:

- changing product scope
- clarifying requirements
- adding or splitting contracts
- modifying backlog order

Read:

- [dev/benchloop-prd.md](/Users/xavierhillman/blackbox/code/benchloop/dev/benchloop-prd.md)
- [dev/contracts/README.md](/Users/xavierhillman/blackbox/code/benchloop/dev/contracts/README.md)
- [dev/contracts/BACKLOG.md](/Users/xavierhillman/blackbox/code/benchloop/dev/contracts/BACKLOG.md)
- [AGENTS.md](/Users/xavierhillman/blackbox/code/benchloop/AGENTS.md)

Then:

- open only the contract files directly affected

### 2. Repo Foundation Work

Use when:

- creating or changing repo structure
- adding tooling
- changing local setup
- adding shared scripts

Read:

- [AGENTS.md](/Users/xavierhillman/blackbox/code/benchloop/AGENTS.md)
- [README.md](/Users/xavierhillman/blackbox/code/benchloop/README.md)
- [dev/contracts/C001-platform-monorepo-foundation.md](/Users/xavierhillman/blackbox/code/benchloop/dev/contracts/C001-platform-monorepo-foundation.md)
- [dev/contracts/BACKLOG.md](/Users/xavierhillman/blackbox/code/benchloop/dev/contracts/BACKLOG.md)
- [Makefile](/Users/xavierhillman/blackbox/code/benchloop/Makefile)

Then:

- open only the specific files or directories being created or changed

### 3. Backend Architecture Work

Use when:

- adding FastAPI app structure
- changing backend conventions
- adding database base patterns
- changing migrations setup

Read:

- [AGENTS.md](/Users/xavierhillman/blackbox/code/benchloop/AGENTS.md)
- [dev/contracts/C002-api-and-data-foundation.md](/Users/xavierhillman/blackbox/code/benchloop/dev/contracts/C002-api-and-data-foundation.md)
- [dev/contracts/BACKLOG.md](/Users/xavierhillman/blackbox/code/benchloop/dev/contracts/BACKLOG.md)
- [apps/api/README.md](/Users/xavierhillman/blackbox/code/benchloop/apps/api/README.md)

Then:

- open only files under [apps/api](/Users/xavierhillman/blackbox/code/benchloop/apps/api) that are directly involved

### 4. Auth, Identity, And Ownership Work

Use when:

- integrating Clerk
- adding auth middleware or dependencies
- creating user sync flows
- enforcing `user_id` scoping

Read:

- [AGENTS.md](/Users/xavierhillman/blackbox/code/benchloop/AGENTS.md)
- [dev/benchloop-prd.md](/Users/xavierhillman/blackbox/code/benchloop/dev/benchloop-prd.md)
  - focus on ownership and auth sections
- [dev/contracts/C003-auth-identity-and-ownership.md](/Users/xavierhillman/blackbox/code/benchloop/dev/contracts/C003-auth-identity-and-ownership.md)
- [dev/contracts/BACKLOG.md](/Users/xavierhillman/blackbox/code/benchloop/dev/contracts/BACKLOG.md)

Then:

- open only the backend auth files and the web auth entrypoints being changed

### 5. Web Shell And Client Contract Work

Use when:

- building the app shell
- adding route groups
- adding API client plumbing
- changing navigation or shared app states

Read:

- [AGENTS.md](/Users/xavierhillman/blackbox/code/benchloop/AGENTS.md)
- [dev/contracts/C004-web-app-shell-and-client-contract.md](/Users/xavierhillman/blackbox/code/benchloop/dev/contracts/C004-web-app-shell-and-client-contract.md)
- [dev/contracts/BACKLOG.md](/Users/xavierhillman/blackbox/code/benchloop/dev/contracts/BACKLOG.md)
- [apps/web/README.md](/Users/xavierhillman/blackbox/code/benchloop/apps/web/README.md)

Then:

- open only the specific files under [apps/web/app](/Users/xavierhillman/blackbox/code/benchloop/apps/web/app), [apps/web/components](/Users/xavierhillman/blackbox/code/benchloop/apps/web/components), and [apps/web/lib](/Users/xavierhillman/blackbox/code/benchloop/apps/web/lib) involved in the task

### 6. Settings And Provider Credential Work

Use when:

- implementing settings
- adding secret storage behavior
- adding credential validation
- changing default provider or model logic

Read:

- [AGENTS.md](/Users/xavierhillman/blackbox/code/benchloop/AGENTS.md)
- [dev/contracts/C005-settings-and-provider-credentials.md](/Users/xavierhillman/blackbox/code/benchloop/dev/contracts/C005-settings-and-provider-credentials.md)
- [dev/contracts/BACKLOG.md](/Users/xavierhillman/blackbox/code/benchloop/dev/contracts/BACKLOG.md)

Then:

- open only the settings-related backend modules, migrations, and matching settings UI files

### 7. Experiment, Test Case, And Config Work

Use when:

- implementing core lab entities
- changing CRUD for experiments, test cases, or configs
- changing clone, baseline, or tags behavior

Read:

- [AGENTS.md](/Users/xavierhillman/blackbox/code/benchloop/AGENTS.md)
- [dev/contracts/C006-experiments.md](/Users/xavierhillman/blackbox/code/benchloop/dev/contracts/C006-experiments.md)
- [dev/contracts/C007-test-cases.md](/Users/xavierhillman/blackbox/code/benchloop/dev/contracts/C007-test-cases.md)
- [dev/contracts/C008-configs-and-versioning.md](/Users/xavierhillman/blackbox/code/benchloop/dev/contracts/C008-configs-and-versioning.md)
- [dev/contracts/BACKLOG.md](/Users/xavierhillman/blackbox/code/benchloop/dev/contracts/BACKLOG.md)

Then:

- open only the relevant entity module and the specific experiment-detail UI files being touched

### 8. Execution, Runs, And Provider Adapter Work

Use when:

- implementing prompt rendering
- adding execution services
- integrating providers
- working on run snapshots, run history, rerun, or run detail

Read:

- [AGENTS.md](/Users/xavierhillman/blackbox/code/benchloop/AGENTS.md)
- [dev/contracts/C009-prompt-rendering-and-run-snapshots.md](/Users/xavierhillman/blackbox/code/benchloop/dev/contracts/C009-prompt-rendering-and-run-snapshots.md)
- [dev/contracts/C010-provider-adapters-and-single-shot-execution.md](/Users/xavierhillman/blackbox/code/benchloop/dev/contracts/C010-provider-adapters-and-single-shot-execution.md)
- [dev/contracts/C011-runs-history-detail-and-rerun.md](/Users/xavierhillman/blackbox/code/benchloop/dev/contracts/C011-runs-history-detail-and-rerun.md)
- [dev/contracts/BACKLOG.md](/Users/xavierhillman/blackbox/code/benchloop/dev/contracts/BACKLOG.md)

Then:

- open only the execution pipeline modules, provider adapters, run-related schemas, and matching run UI files

### 9. Compare, Evaluation, Context, Dashboard, Export, Or Two-Step Work

Use when:

- implementing compare view
- manual evaluation
- context bundles
- dashboard aggregates
- export
- two-step workflow mode

Read:

- [AGENTS.md](/Users/xavierhillman/blackbox/code/benchloop/AGENTS.md)
- [dev/contracts/C012-compare-and-manual-evaluation.md](/Users/xavierhillman/blackbox/code/benchloop/dev/contracts/C012-compare-and-manual-evaluation.md)
- [dev/contracts/C013-context-bundles-and-prompt-plus-context-mode.md](/Users/xavierhillman/blackbox/code/benchloop/dev/contracts/C013-context-bundles-and-prompt-plus-context-mode.md)
- [dev/contracts/C014-dashboard-aggregates-and-export.md](/Users/xavierhillman/blackbox/code/benchloop/dev/contracts/C014-dashboard-aggregates-and-export.md)
- [dev/contracts/C015-two-step-chain-mode.md](/Users/xavierhillman/blackbox/code/benchloop/dev/contracts/C015-two-step-chain-mode.md)
- [dev/contracts/BACKLOG.md](/Users/xavierhillman/blackbox/code/benchloop/dev/contracts/BACKLOG.md)

Then:

- open only the specific backend and frontend files for that feature slice

### 10. Testing, Security Review, Or Release Hardening

Use when:

- adding tests
- reviewing security boundaries
- tightening logging
- updating CI or quality gates

Read:

- [AGENTS.md](/Users/xavierhillman/blackbox/code/benchloop/AGENTS.md)
- [dev/contracts/C016-quality-security-and-operability.md](/Users/xavierhillman/blackbox/code/benchloop/dev/contracts/C016-quality-security-and-operability.md)
- [dev/contracts/BACKLOG.md](/Users/xavierhillman/blackbox/code/benchloop/dev/contracts/BACKLOG.md)
- [README.md](/Users/xavierhillman/blackbox/code/benchloop/README.md)

Then:

- open only the affected tests, CI config, or runtime code paths under review

## Minimal Context Rules

- Do not read all contracts by default.
- Do not read all files in `apps/api` or `apps/web` by default.
- Do not load the full PRD for a narrowly scoped implementation if the relevant contract already covers the needed behavior.
- Prefer opening one contract plus the exact implementation files over broad repo sweeps.
- If you need to expand context, do it incrementally and explain why.

## Update Rules

Update this file whenever any of the following change:

- a new top-level repo area is added
- a new major subsystem is added
- task routing should point to different authority files
- the implementation sequence changes enough that routing guidance would mislead future work

If `AGENTS.md` changes in a way that affects workflow expectations, update both files together.

