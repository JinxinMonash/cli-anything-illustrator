#!/usr/bin/env bash
# Remove the user-scope skill and (optionally) the Python package.
set -euo pipefail
DEST="$HOME/.agents/skills/cli-anything-illustrator"
if [[ -e "$DEST" ]]; then rm -rf "$DEST"; echo "Removed $DEST"; else echo "No skill at $DEST"; fi
read -r -p "Also uninstall the Python package cli-anything-illustrator? [y/N] " a
[[ "$a" == "y" || "$a" == "Y" ]] && python3 -m pip uninstall -y cli-anything-illustrator || true
