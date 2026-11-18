.PHONY: install test lint typecheck benchmark benchmark-bge benchmark-experiment \
	eval-m13 api dashboard dashboard-install dashboard-test dashboard-lint test-all \
	demo demo-compose

PYTHON ?= python3
API_PORT ?= 8080
DASH_PORT ?= 3000

install:
	$(PYTHON) -m pip install -U pip setuptools wheel
	$(PYTHON) -m pip install -e "./packages/core" -e "./packages/provenance"
	$(PYTHON) -m pip install -e "./packages/risk" -e "./packages/policy" -e "./packages/audit"
	$(PYTHON) -m pip install -e "./packages/reconstruction"
	$(PYTHON) -m pip install -e "./packages/agent_sdk"
	$(PYTHON) -m pip install -e "./integrations/mock_email"
	$(PYTHON) -m pip install -e "./integrations/mock_filesystem"
	$(PYTHON) -m pip install -e "./integrations/mock_http"
	$(PYTHON) -m pip install -e "./integrations/mock_shell"
	$(PYTHON) -m pip install -e "./packages/mcp_proxy"
	$(PYTHON) -m pip install -e "./packages/benchmark"
	$(PYTHON) -m pip install -e "./packages/api"
	$(PYTHON) -m pip install -e "./packages/cli"
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m ruff check packages integrations tests scripts

benchmark:
	$(PYTHON) -m agenttaint_benchmark run --split test --seed 2120 --semantic-backend fixture

benchmark-bge:
	$(PYTHON) -m agenttaint_benchmark run --split test --seed 2120 --semantic-backend bge --tag bge

benchmark-experiment:
	$(PYTHON) -m agenttaint_benchmark experiment --split test --seed 2120 \
		--seeds 2120,7,42,99,12345 --semantic-backend fixture --tag experiment_fixture

eval-m13:
	PYTHONHASHSEED=0 $(PYTHON) scripts/run_m13_evaluation.py \
		--split test --seed 2120 --semantic-backend fixture --tag m13

typecheck:
	$(PYTHON) -m mypy packages/core/src packages/provenance/src packages/risk/src \
		packages/policy/src packages/audit/src packages/reconstruction/src \
		packages/agent_sdk/src packages/mcp_proxy/src integrations/mock_email/src \
		packages/cli/src

api:
	HOST=127.0.0.1 PORT=$(API_PORT) $(PYTHON) -m agenttaint_api

dashboard-install:
	cd apps/dashboard && npm install --legacy-peer-deps

dashboard:
	cd apps/dashboard && AGENTTAINT_API_ORIGIN=http://127.0.0.1:$(API_PORT) \
		npm run dev -- --port $(DASH_PORT) --hostname 0.0.0.0

dashboard-test:
	cd apps/dashboard && npm test

dashboard-lint:
	cd apps/dashboard && npm run lint

test-all: test dashboard-test

demo:
	API_PORT=$(API_PORT) DASH_PORT=$(DASH_PORT) PYTHON=$(PYTHON) bash scripts/demo.sh

demo-compose:
	docker compose --profile demo up --build
