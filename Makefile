PYTHON ?= python3.12
MOCAP_FIXTURES ?= /mnt/g/mocap-studio-downloads/fixtures
FREEMOCAP_TEST_DATA = $(MOCAP_FIXTURES)/freemocap-test-data-v06_09_25
FREEMOCAP_TEST_DATA_URL = https://github.com/freemocap/skellysamples/releases/download/test_data_v06_09_25/freemocap_test_data.zip
FREEMOCAP_TEST_DATA_SHA256 = 543a38c86e591476975a8c3d8dd05c5243777a769c696e116c6aaea43f5170b1

.PHONY: venv test fixtures

venv:
	$(PYTHON) -m venv .venv
	.venv/bin/pip install -e '.[test]'

# FreeMoCap's test recording (skellysamples, AGPL-3.0), used by tests/test_body.py; never committed.
fixtures:
	mkdir -p $(FREEMOCAP_TEST_DATA)
	test -f $(FREEMOCAP_TEST_DATA)/freemocap_test_data.zip || curl -fsSL -o $(FREEMOCAP_TEST_DATA)/freemocap_test_data.zip $(FREEMOCAP_TEST_DATA_URL)
	echo "$(FREEMOCAP_TEST_DATA_SHA256)  $(FREEMOCAP_TEST_DATA)/freemocap_test_data.zip" | sha256sum -c -

test:
	MOCAP_FIXTURES=$(MOCAP_FIXTURES) .venv/bin/pytest
