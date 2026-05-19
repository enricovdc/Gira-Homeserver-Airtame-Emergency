# Top-level convenience commands for the Gira HomeServer x Airtame Emergency
# Alert module project. Wraps the scripts/ entry points so a single
# `make build` regenerates every artefact and `make test` runs the suite.
#
# Required env (set on the developer machine, not in CI):
#   GIRA_SDK_DIR  Path to the unpacked "Gira HomeServer SDK Doku" folder
#   PYTHON27      Path to a Python 2.7 interpreter (for HSL2 generator.pyc)
#   PYTHON39      Path to a Python 3.9 interpreter (for HSL3 generator3.cpython-39.pyc)
#
# Sensible defaults are baked in for the standalone interpreters used
# during development of this repo; override per call as needed:
#   make build GIRA_SDK_DIR=/path/to/SDK PYTHON27=python2.7 PYTHON39=python3.9

PYTHON27 ?= python2.7
PYTHON39 ?= python3.9
GIRA_SDK_DIR ?= $$HOME/Documents/Gira_HomeServer_SDK_Doku

.PHONY: help test build hsl hslz lint clean install-deps verify

help:
	@echo "Targets:"
	@echo "  make test          Run the pytest suite (no SDK / Python 2.7 needed)."
	@echo "  make build         Regenerate both .hsl files + .hslz archives."
	@echo "  make hsl           Regenerate just the .hsl files (skip HSLZ)."
	@echo "  make hslz          Repackage .hslz from existing .hsl + help files."
	@echo "  make verify        Run tests + build + sanity-check the .hsl record 5000."
	@echo "  make install-deps  pip install -r requirements.txt."
	@echo "  make clean         Remove __pycache__ / .pytest_cache."

test:
	python3 -m pytest -q

install-deps:
	python3 -m pip install --quiet -r requirements.txt

build: hsl hslz

hsl:
	GIRA_SDK_DIR="$(GIRA_SDK_DIR)" PYTHON27="$(PYTHON27)" PYTHON39="$(PYTHON39)" \
	  ./scripts/generate_hsl.sh

hslz:
	python3 scripts/build_hslz.py

verify: test build
	@echo
	@N_IN=$$(grep -c '<input ' projects/airtame_emergency/config.xml); \
	  N_OUT=$$(grep -c '<output ' projects/airtame_emergency/config.xml); \
	  EXPECTED=$$(( 4 + $$N_IN + 1 + $$N_OUT + 1 )); \
	  echo "Sanity-checking record 5000 field count"; \
	  echo "  expected: 4 + $$N_IN inputs + 1 + $$N_OUT outputs + 1 = $$EXPECTED"; \
	  awk -F'|' -v want=$$EXPECTED 'NR==2{ if (NF==want) { printf "  HSL2 record 5000 OK (%d fields)\n", NF } \
	                                        else { printf "  HSL2 record 5000 BAD: %d fields (expected %d)\n", NF, want; exit 1 } }' \
	    projects/airtame_emergency/release/24815_AirtameEmergencyAlert.hsl

clean:
	find . -type d \( -name __pycache__ -o -name .pytest_cache \) \
	    -not -path "./.git/*" -exec rm -rf {} + 2>/dev/null || true
