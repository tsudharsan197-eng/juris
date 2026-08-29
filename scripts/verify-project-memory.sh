#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

required_files=(
  "AGENTS.md"
  "MEMORY.md"
  "docs/DECISIONS.md"
  "docs/PROJECT_RECOVERY.md"
)

for file in "${required_files[@]}"; do
  if [[ ! -s "$file" ]]; then
    echo "Missing or empty project-memory file: $file" >&2
    exit 1
  fi
done

tracked_sensitive_files="$(
  git ls-files \
    | grep -E '(^|/)(\.env($|\.)|credentials?($|\.)|secrets?($|\.))' \
    | grep -Ev '\.(example|sample|template)$' \
    || true
)"
if [[ -n "$tracked_sensitive_files" ]]; then
  echo "Potential sensitive files are tracked:" >&2
  echo "$tracked_sensitive_files" >&2
  exit 1
fi

if ! git remote get-url origin >/dev/null 2>&1; then
  echo "No origin remote is configured; local Git history is not an off-device backup." >&2
  exit 1
fi

echo "Project memory files are present, no obvious secret files are tracked, and origin is configured."
