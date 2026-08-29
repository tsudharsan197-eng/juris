#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 /path/to/off-device-backup" >&2
  exit 2
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
output_dir="$1"
timestamp="$(date -u +%Y%m%d-%H%M%S)"
bundle_path="${output_dir%/}/juris-${timestamp}.bundle"

cd "$repo_root"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Warning: uncommitted and untracked files are not included in a Git bundle." >&2
  git status --short >&2
fi

mkdir -p "$output_dir"
git bundle create "$bundle_path" --branches --tags
git bundle verify "$bundle_path"
shasum -a 256 "$bundle_path" > "${bundle_path}.sha256"

echo "Recovery bundle: $bundle_path"
echo "Checksum: ${bundle_path}.sha256"
