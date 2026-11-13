.PHONY: install test lint typecheck benchmark benchmark-test

PYTHON ?= python3

install:
	$(PYTHON) -m pip install -U pip setuptools wheel
	$(PYTHON) -m pip install -e "./packages/core" -e "./packages/provenance"
	$(PYTHON) -m pip install -e "./packages/risk" -e "./packages/policy" -e "./packages/audit"
	$(PYTHON) -m pip install -e "./packages/reconstruction"
	$(PYTHON) -m pip install -e "./packages/agent_sdk"
	$(PYTHON) -m pip install -e "./integrations/mock_email"
	$(PYTHON) -m pip install -e "./packages/mcp_proxy"
	$(PYTHON) -m pip install -e "./packages/benchmark"
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m ruff check packages integrations tests scripts

benchmark:
	$(PYTHON) -m agenttaint_benchmark run --split test --seed 2120

benchmark-test:
	$(PYTHON) -m agenttaint_benchmark run --split test --seed 2120

typecheck:
	$(PYTHON) -m mypy packages/core/src packages/provenance/src packages/risk/src \
		packages/policy/src packages/audit/src packages/reconstruction/src \
		packages/agent_sdk/src packages/mcp_proxy/src integrations/mock_email/src
