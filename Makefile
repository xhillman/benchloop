.PHONY: help check-structure init-env postgres-up postgres-down postgres-logs local-up

help:
	@echo "Benchloop repository commands"
	@echo ""
	@echo "Available targets:"
	@echo "  make check-structure  Verify the B001 monorepo skeleton exists"
	@echo "  make init-env         Create local env files from committed examples"
	@echo "  make postgres-up      Start the local Postgres container"
	@echo "  make postgres-down    Stop the local Postgres container"
	@echo "  make postgres-logs    Tail local Postgres logs"
	@echo "  make local-up         Initialize env files and start local Postgres"

check-structure:
	@test -d apps/api
	@test -d apps/web
	@test -d scripts
	@test -d dev/contracts
	@echo "Repository skeleton looks correct."

init-env:
	@./scripts/bootstrap_local_env.sh

postgres-up:
	@docker compose up -d postgres

postgres-down:
	@docker compose down

postgres-logs:
	@docker compose logs -f postgres

local-up: init-env postgres-up
	@echo "Local Postgres is ready on localhost:5432."
