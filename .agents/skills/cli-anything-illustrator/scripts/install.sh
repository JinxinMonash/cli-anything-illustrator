#!/usr/bin/env bash
# Install the cli-anything-illustrator skill for the current user
# (~/.agents/skills/cli-anything-illustrator) and the Python CLI.
# Refuses to overwrite an existing installation unless --force is given.
set -euo pipefail

FORCE=0
[[ "${1:-}" == "--force" ]] && FORCE=1
SKILL_SRC="$(cd "$(dirname "$0")/.." && pwd)"
REPO_ROOT="$(cd "$SKILL_SRC/../../.." && pwd)"
DEST="$HOME/.agents/skills/cli-anything-illustrator"

if [[ -e "$DEST" && $FORCE -eq 0 ]]; then
    echo "Refusing to overwrite existing $DEST (re-run with --force)." >&2
    exit 8
fi

echo "Installing Python package from $REPO_ROOT ..."
python3 -m pip install -e "$REPO_ROOT"

mkdir -p "$(dirname "$DEST")"
rm -rf "${DEST:?}.tmp"
cp -R "$SKILL_SRC" "$DEST.tmp"
[[ -e "$DEST" ]] && rm -rf "$DEST"
mv "$DEST.tmp" "$DEST"
echo "Skill installed at $DEST"
echo "Next: cli-anything-illustrator app doctor"
