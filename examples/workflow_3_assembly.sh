#!/usr/bin/env bash
# Representative workflow 3 (principal acceptance demo):
# 4 synthetic SVG panels -> editable multi-panel figure -> AI master +
# PDF/SVG/PNG delivery copies -> reopen + verification report.
set -euo pipefail
OUT="${1:-figure_demo}"
mkdir -p "$OUT/panels"
HERE="$(cd "$(dirname "$0")" && pwd)"

python3 "$HERE/make_panels.py" --outdir "$OUT/panels"
cp "$HERE/figure1_spec.json" "$OUT/"
cd "$OUT"

cli-anything-illustrator figure validate --spec figure1_spec.json
cli-anything-illustrator figure assemble --spec figure1_spec.json
cli-anything-illustrator doc close --doc figure1.ai --discard-changes
cli-anything-illustrator figure verify --spec figure1_spec.json
echo "Master, exports and manifest are in: $(pwd)"
