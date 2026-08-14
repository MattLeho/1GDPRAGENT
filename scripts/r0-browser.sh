#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/scripts/r0-require-command.sh"
require_command pnpm 'Install pnpm 11.9.0.'
require_file "$ROOT/frontend/node_modules/.bin/playwright" 'Add @playwright/test to frontend devDependencies, run pnpm install, then run pnpm exec playwright install --with-deps chromium.'
require_file "$ROOT/tests/browser/r0-authenticated-baseline.spec.ts" 'Add the R0 authenticated browser baseline specification.'
require_command python 'Install Python 3.11+ with the migration dependencies.'
require_command curl 'Install curl for managed browser-stack readiness checks.'
export R0_BASE_URL="${R0_BASE_URL:-http://127.0.0.1:3000}"
export R0_EXECUTE_BROWSER="1"
server_pid=""
cleanup() {
  if [[ -n "$server_pid" ]]; then
    kill -TERM -- -"$server_pid" 2>/dev/null || true
    kill -TERM "$server_pid" 2>/dev/null || true
    sleep 1
    if kill -0 "$server_pid" 2>/dev/null; then
      kill -KILL -- -"$server_pid" 2>/dev/null || true
      kill -KILL "$server_pid" 2>/dev/null || true
    fi
    wait "$server_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT

browser_script="$(cd "$ROOT/frontend" && pnpm pkg get scripts.test:browser)"
if [[ -z "$browser_script" || "$browser_script" == "{}" || "$browser_script" == "null" ]]; then
  printf 'R0 authenticated browser gate is not configured: frontend/package.json needs a test:browser script.\n' >&2
  exit 2
fi

if [[ "${R0_MANAGED_BROWSER_STACK:-0}" == "1" ]]; then
  if [[ "${CI:-}" != "true" ]]; then
    printf 'R0_MANAGED_BROWSER_STACK is CI-only; use an isolated database and CI=true.\n' >&2
    exit 2
  fi
  if [[ -z "${DATABASE_URL:-}" ]]; then
    printf 'R0 managed browser prerequisite missing: DATABASE_URL.\n' >&2
    exit 2
  fi
  if [[ "${R0_TEST_MODE:-}" != "1" ]]; then
    printf 'R0 managed browser stack requires R0_TEST_MODE=1 to fail closed against provider and service dependencies.\n' >&2
    exit 2
  fi
  require_file "$ROOT/frontend/.next/BUILD_ID" 'Run the R0 production-build gate before managed browser acceptance.'
  mkdir -p "$ROOT/test-results"
  (cd "$ROOT" && python database/migrate.py)
  (cd "$ROOT/frontend" && exec setsid pnpm start > "$ROOT/test-results/r0-nextjs.log" 2>&1) &
  server_pid="$!"
  for attempt in $(seq 1 60); do
    if curl --fail --silent "$R0_BASE_URL/login" >/dev/null; then break; fi
    sleep 1
  done
  if ! curl --fail --silent "$R0_BASE_URL/login" >/dev/null; then
    printf 'R0 managed browser stack did not become ready; see test-results/r0-nextjs.log.\n' >&2
    exit 1
  fi
fi
cd "$ROOT/frontend"
pnpm run test:browser -- "$@"
