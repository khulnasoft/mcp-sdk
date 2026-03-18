.PHONY: install dev test lint format clean docs run-example docker-build docker-push pypi-build pypi-publish

# ── Setup ──────────────────────────────────────────────────────────────────────
install:
	uv pip install -e . 

dev:
	uv pip install -e ".[dev,docs]"
	uv pre-commit install
	./scripts/setup-pre-commit.sh

# ── Testing ────────────────────────────────────────────────────────────────────
test:
	uv pytest tests/ -v --cov=mcp_sdk --cov-report=term-missing

test-fast:
	uv pytest tests/ -v -x --no-cov

# ── Code Quality ───────────────────────────────────────────────────────────────
lint:
	uv ruff check mcp_sdk/ tests/
	uv mypy mcp_sdk/

format:
	black mcp_sdk/ tests/ examples/
	ruff check --fix mcp_sdk/ tests/

# Pre-commit hooks
pre-commit:
	pre-commit run --all-files

pre-commit-update:
	pre-commit autoupdate
	pre-commit run --all-files

# ── Examples ───────────────────────────────────────────────────────────────────
run-a2a:
	uv run python examples/a2a_delegation.py

run-b2c:
	uv run python examples/b2c_support_agent.py

run-rules:
	uv run python examples/rules_showcase.py

run-mcp:
	uv run python examples/mcp_server.py

# ── CLI ────────────────────────────────────────────────────────────────────────
cli-version:
	uv run python -m mcp_sdk.cli.main version

cli-validate-rules:
	uv run python -m mcp_sdk.cli.main rule validate examples/rules.yaml

# ── Docs ───────────────────────────────────────────────────────────────────────
docs:
	uv run mkdocs serve

docs-build:
	uv run mkdocs build

# ── Clean ──────────────────────────────────────────────────────────────────────
clean:
	uv find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	uv find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	uv find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	uv find . -type f -name "*.pyc" -delete
	uv rm -rf .coverage htmlcov/ dist/ build/

# ── Docker ───────────────────────────────────────────────────────────────────────
docker-build:
	docker build -t mcp-sdk:latest .
	docker build -t mcp-sdk:$(shell uv run python -c "import mcp_sdk; print(mcp_sdk.__version__)") .

docker-push:
	docker push mcp-sdk:latest
	docker push mcp-sdk:$(shell uv run python -c "import mcp_sdk; print(mcp_sdk.__version__)")

# ── PyPI ────────────────────────────────────────────────────────────────────────
pypi-build:
	uv build

pypi-publish:
	uv publish

# ── Release ───────────────────────────────────────────────────────────────────────
release: clean test lint pypi-build docker-build
	@echo "Ready to publish to PyPI and Docker Hub"
	@echo "Run 'make pypi-publish docker-push' to publish"
