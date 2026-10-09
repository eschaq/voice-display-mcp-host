.PHONY: install dev host example client test lint build e2e clean

VENV ?= .venv
PY   := $(VENV)/bin/python
PIP  := $(VENV)/bin/pip

install: $(VENV)/bin/activate client/node_modules

$(VENV)/bin/activate:
	python3 -m venv $(VENV)
	$(PIP) install -q --upgrade pip
	$(PIP) install -q -e "host[dev]" mcp uvicorn

client/node_modules: client/package.json
	cd client && npm install --silent

# Everything, locally, in one command: the example MCP server, the host
# agent in front of it, and the client. No cloud account, no keys.
dev: install
	@echo "example server :8081   host :8080   client :5180"
	@trap 'kill 0' EXIT; \
	 EXAMPLE_PORT=8081 $(PY) example-server/server.py & \
	 sleep 1; \
	 MCP_URL=http://127.0.0.1:8081/mcp PORT=8080 $(PY) -m voice_display_host & \
	 cd client && npm run dev -- --host 127.0.0.1

host: install
	MCP_URL=$${MCP_URL:-http://127.0.0.1:8081/mcp} PORT=8080 $(PY) -m voice_display_host

example: install
	EXAMPLE_PORT=8081 $(PY) example-server/server.py

client: client/node_modules
	cd client && npm run dev

test: install
	$(VENV)/bin/pytest host/tests example-server/tests -q
	cd client && npm run typecheck

lint: install
	$(VENV)/bin/ruff check host example-server
	$(VENV)/bin/ruff format --check host example-server

build: client/node_modules
	cd client && npm run build

# Drives the real thing in headless Chromium: example server, host, client,
# one spoken turn, and the card's handshake completing.
e2e: install build scripts/e2e/node_modules
	$(PY) scripts/e2e/run_e2e.py

scripts/e2e/node_modules: scripts/e2e/package.json
	cd scripts/e2e && npm install --silent

clean:
	rm -rf $(VENV) client/node_modules client/dist
