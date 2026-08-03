#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/scripts/r0-require-command.sh"
require_command pnpm 'Install pnpm 11.9.0.'
require_file "$ROOT/frontend/package.json" 'Restore the frontend package manifest.'
require_file "$ROOT/frontend/node_modules/.bin/tsc" 'Run pnpm install --frozen-lockfile in frontend before this command.'
require_file "$ROOT/frontend/node_modules/.bin/eslint" 'Run pnpm install --frozen-lockfile in frontend before this command.'
cd "$ROOT/frontend"

case "${1:-}" in
  typecheck)
    pnpm run typecheck
    ;;
  lint)
    pnpm run lint
    ;;
  build)
    pnpm run build
    ;;
  unit)
    if ! pnpm pkg get scripts.test | grep -qv '^{}$'; then
      printf 'R0 frontend unit/component gate is not configured: frontend/package.json needs a test script and declared runner.\n' >&2
      exit 2
    fi
    pnpm run test
    ;;
  *)
    printf 'Usage: %s {typecheck|lint|build|unit}\n' "$0" >&2
    exit 64
    ;;
esac
