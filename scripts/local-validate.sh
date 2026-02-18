#!/usr/bin/env bash
set -euo pipefail

echo "==> Local validate: tests + compile checks"

echo "==> Running pytest"
python -m pytest -q

echo "==> Running compileall on src/tests"
python -m compileall -q src tests

echo "==> Local validate passed"
