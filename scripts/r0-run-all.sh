#!/usr/bin/env bash
# Execute every R0 gate even when the baseline exposes multiple failures.  The
# final non-zero status preserves CI's blocking behaviour while artefacts from
# later gates are still available for the remediation ledger.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
declare -a gates=(
  "bash scripts/r0-compose-validate.sh"
  "bash scripts/r0-migration-fixtures.sh"
  "bash scripts/r0-python-suite.sh"
  "bash scripts/r0-static-invariants.sh"
  "bash scripts/r0-frontend.sh typecheck"
  "bash scripts/r0-frontend.sh lint"
  "bash scripts/r0-frontend.sh unit"
  "bash scripts/r0-frontend.sh build"
  "bash scripts/r0-browser.sh"
)

failed=0
cd "$ROOT"
for gate in "${gates[@]}"; do
  printf '\n===== R0 gate: %s =====\n' "$gate"
  if ! eval "$gate"; then
    printf '===== R0 gate failed: %s =====\n' "$gate" >&2
    failed=1
  fi
done
exit "$failed"
