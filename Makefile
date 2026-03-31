.PHONY: setup test clean reset help

help:
	@echo "OpenKiln development commands:"
	@echo "  make setup   — create venv and install dependencies"
	@echo "  make test    — run test suite"
	@echo "  make clean   — remove venv and build artifacts"
	@echo "  make reset   — remove ~/.openkiln (destructive)"

setup:
	python -m venv .venv
	.venv/bin/pip install -e ".[dev]"
	@echo ""
	@echo "Setup complete. Activate with:"
	@echo "  source .venv/bin/activate"

test:
	.venv/bin/pytest tests/ -v

clean:
	rm -rf .venv dist build *.egg-info .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

reset:
	@echo "WARNING: This will delete ~/.openkiln and all your OpenKiln data."
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ]
	rm -rf ~/.openkiln
	@echo "Reset complete. Run: openkiln init"
