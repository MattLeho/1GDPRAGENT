#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/scripts/r0-require-command.sh"
require_command python 'Install Python 3.11+ and pip install -r intelligence/requirements-dev.txt.'
cd "$ROOT"
python -c "import pytest, pytest_asyncio" || {
  printf 'R0 prerequisite missing: pytest and pytest-asyncio. Run pip install -r intelligence/requirements-dev.txt.\n' >&2
  exit 2
}
python -m pytest -q tests "$@"
