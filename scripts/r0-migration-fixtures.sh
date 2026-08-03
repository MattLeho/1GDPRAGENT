#!/usr/bin/env bash
# Run only against a disposable PostgreSQL server.  The fixture itself creates
# uniquely named databases and never mutates DATABASE_URL's database.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/scripts/r0-require-command.sh"
require_command python 'Install Python 3.11+ and the intelligence dev requirements.'
if [[ -z "${DATABASE_URL:-}" ]]; then
  printf 'R0 prerequisite missing: DATABASE_URL must point to a PostgreSQL role with CREATEDB privilege.\n' >&2
  exit 2
fi
cd "$ROOT"
python -m pytest -q tests/migration_fixtures "$@"
