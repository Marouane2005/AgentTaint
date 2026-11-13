.PHONY: install test lint typecheck

PYTHON ?= python3

install:
	$(PYTHON) -m pip install -U pip setuptools wheel
	$(PYTHON) -m pip install -e "./packages/core" -e "./packages/provenance"
	$(PYTHON) -m pip install -e "./packages/risk" -e "./packages/policy" -e "./packages/audit"
	$(PYTHON) -m pip install -e "./integrations/mock_email"
	$(PYTHON) -m pip install -e "./packages/mcp_proxy"
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m ruff check packages integrations tests

typecheck:
	$(PYTHON) -m mypy packages/core/src packages/provenance/src packages/risk/src \
		packages/policy/src packages/audit/src packages/mcp_proxy/src \
		integrations/mock_email/src
