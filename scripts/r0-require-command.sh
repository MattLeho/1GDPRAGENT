#!/usr/bin/env bash
# Shared guard for R0 CI entry points.  A missing dependency must be a visible
# infrastructure failure, never a passing/skipped acceptance check.
set -euo pipefail

require_command() {
  local command_name="$1"
  local install_hint="$2"
  if ! command -v "$command_name" >/dev/null 2>&1; then
    printf 'R0 prerequisite missing: %s. %s\n' "$command_name" "$install_hint" >&2
    exit 2
  fi
}

require_file() {
  local file_path="$1"
  local create_hint="$2"
  if [[ ! -f "$file_path" ]]; then
    printf 'R0 prerequisite missing: %s. %s\n' "$file_path" "$create_hint" >&2
    exit 2
  fi
}
