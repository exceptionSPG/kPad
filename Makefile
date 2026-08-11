# LAN Trackpad — dev Makefile.
VENV := .venv
PY   := $(VENV)/bin/python
PIP  := $(VENV)/bin/pip

.PHONY: run proto venv clean

# Start the server (regenerates the client protocol mirror first).
run: venv proto
	$(PY) -m server.main

# Regenerate web/protocol.js from server/protocol.py (single source of truth).
proto: venv
	$(PY) scripts/gen_protocol.py

# Create/refresh the virtualenv only when requirements change.
venv: $(VENV)/.stamp
$(VENV)/.stamp: requirements.txt
	python3 -m venv $(VENV)
	$(PIP) install -q -U pip
	$(PIP) install -q -r requirements.txt
	@touch $(VENV)/.stamp

clean:
	rm -rf $(VENV) web/protocol.js
