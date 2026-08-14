#!/usr/bin/env bash
# Execute every R0 gate even when the baseline exposes multiple failures.  The
# final non-zero status preserves CI's blocking behaviour while artefacts from
# later gates are still available for the remediation ledger.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
declare -a default_gates=(
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
if [[ -n "${R0_GATE_COMMANDS_FILE:-}" ]]; then
  mapfile -t gates < "$R0_GATE_COMMANDS_FILE"
else
  gates=("${default_gates[@]}")
fi

failed=0
cd "$ROOT"
results_dir="${R0_RESULTS_DIR:-$ROOT/test-results}"
mkdir -p "$results_dir"
manifest="$results_dir/r0-gates.json"
log="$results_dir/r0-run-all.log"
commit="$(git rev-parse HEAD 2>/dev/null || printf 'unknown')"
: > "$log"
printf '{\n  "commit": "%s",\n  "gates": [\n' "$commit" > "$manifest"
first=1
for gate in "${gates[@]}"; do
  printf '\n===== R0 gate: %s =====\n' "$gate" | tee -a "$log"
  eval "$gate" 2>&1 | tee -a "$log"
  status="${PIPESTATUS[0]}"
  if (( first == 0 )); then printf ',\n' >> "$manifest"; fi
  printf '    {"gate": "%s", "command": "%s", "exit_status": %d}' "$gate" "$gate" "$status" >> "$manifest"
  first=0
  if (( status != 0 )); then
    printf '===== R0 gate failed: %s (exit %d) =====\n' "$gate" "$status" | tee -a "$log" >&2
    failed=1
  fi
done
printf '\n  ]\n}\n' >> "$manifest"
exit "$failed"
