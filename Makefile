PYTHON ?= python3

.PHONY: install sanity test test-unit run ingest-terran index-terran inspector-report

install:
	$(PYTHON) -m pip install -r requirements.txt

sanity:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) scripts/sanity_check.py

test:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m pytest -q

test-unit:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m unittest tests.test_regressions

run:
	$(PYTHON) -m streamlit run app.py

ingest-terran:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) scripts/ingest_universe.py --manifest corpus/universes/terran_empire/manifest.json

index-terran:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) scripts/build_retrieval_index.py --universe terran_empire

inspector-report:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m inspector.run_tests --report
