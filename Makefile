SHELL := /usr/bin/env bash
.SHELLFLAGS := -euo pipefail -c

REPORT_DIR ?= artifacts/reports
SCHEMAS := $(shell find schemas -name '*.schema.json' | sort)

.PHONY: help quickstart doctor validate lint test pre-commit ci clean

help:
	@printf '%s\n' \
		'quickstart  install tools and run validation' \
		'doctor      show local tool versions' \
		'validate    validate schemas, fixtures, and YAML' \
		'lint        run ruff' \
		'test        run pytest' \
		'ci          run validate, lint, and tests'

quickstart:
	python -m pip install --disable-pip-version-check -r requirements-dev.txt
	$(MAKE) ci

doctor:
	mkdir -p "$(REPORT_DIR)"
	python --version | tee "$(REPORT_DIR)/python-version.txt"
	check-jsonschema --version | tee "$(REPORT_DIR)/check-jsonschema-version.txt"
	yamllint --version | tee "$(REPORT_DIR)/yamllint-version.txt"
	ruff --version | tee "$(REPORT_DIR)/ruff-version.txt"

validate: validate-json validate-yaml

validate-json:
	mkdir -p "$(REPORT_DIR)"
	python -m pytest tests/test_contracts.py

validate-yaml:
	yamllint .

lint:
	ruff check .

test:
	python -m pytest

pre-commit:
	pre-commit run --all-files

ci: validate lint test

clean:
	rm -rf artifacts .pytest_cache .ruff_cache
