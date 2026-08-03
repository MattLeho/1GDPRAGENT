#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/scripts/r0-require-command.sh"
require_command python 'Install Python 3.11+ and pip install -r intelligence/requirements-dev.txt.'
cd "$ROOT"
python -c "import pytest" || {
  printf 'R0 prerequisite missing: pytest. Run pip install -r intelligence/requirements-dev.txt.\n' >&2
  exit 2
}
# These tests include the architecture/security invariants rather than relying
# on a best-effort grep that could silently omit a directory.
python -m pytest -q \
  tests/test_audit_static.py \
  tests/test_task2_architecture.py \
  tests/test_task3_graph_projection_policy.py \
  tests/integration "$@"
