#!/usr/bin/env bash
set -euo pipefail

echo "==> Local validate: tests + compile checks"

echo "==> Running pytest"
python -m pytest -q

echo "==> Running compileall on src/tests"
python -m compileall -q src tests

if [[ "${SKIP_E2E:-0}" != "1" ]]; then
  echo "==> Running deterministic E2E gate with artifact capture"
  python ./scripts/e2e_gate.py
fi

echo "==> Local validate passed"
