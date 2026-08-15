#!/usr/bin/env bash
# One-command local equivalent of the CI "integration" job: build, bring
# up, wait for healthy, run the real integration suite against the
# mapped ports, tear down. Uses the repo's own .venv if present, falling
# back to whatever `python`/`pytest` is already on PATH.
set -euo pipefail
cd "$(dirname "$0")/.."

docker compose up -d --build
trap 'docker compose down' EXIT

scripts/wait-healthy.sh invforge

PYTHON=python3
[[ -x .venv/bin/python ]] && PYTHON=.venv/bin/python

"$PYTHON" -m pip install -q -r requirements-dev.txt

INVFORGE_MODBUS_PORT=5020 INVFORGE_CONTROL_PORT=8080 "$PYTHON" -m pytest tests/integration -q
