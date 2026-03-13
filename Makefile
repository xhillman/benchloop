.PHONY: help check-structure

help:
	@echo "Benchloop repository commands"
	@echo ""
	@echo "Available targets:"
	@echo "  make check-structure  Verify the B001 monorepo skeleton exists"

check-structure:
	@test -d apps/api
	@test -d apps/web
	@test -d scripts
	@test -d dev/contracts
	@echo "Repository skeleton looks correct."

