PYTHON ?= python3.12

.PHONY: venv test

venv:
	$(PYTHON) -m venv .venv
	.venv/bin/pip install -e '.[test]'

test:
	.venv/bin/pytest
