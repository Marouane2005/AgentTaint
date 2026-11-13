.PHONY: install test lint typecheck

PYTHON ?= python3

install:
	$(PYTHON) -m pip install -U pip setuptools wheel
	$(PYTHON) -m pip install -e "./packages/core" -e "./packages/provenance"
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m ruff check packages tests

typecheck:
	$(PYTHON) -m mypy packages/core/src packages/provenance/src
