#!/usr/bin/env bash
# Representative workflow 2: TARGETED revision of an existing figure.
# Inspect first, edit by explicit selector, verify, save to a NEW file
# (the original is never overwritten).
set -euo pipefail
SRC="${1:?usage: workflow_2_revision.sh <existing.ai> [outdir]}"
OUT="${2:-revision_demo}"
mkdir -p "$OUT"

ai() { cli-anything-illustrator --compact "$@"; }

ai doc open "$SRC"
ai doc report                       # fonts, links, rasters -- review BEFORE editing
ai text list                        # find the frame to change (uuid/name)
# Example targeted edits (adjust selectors to the inspection output):
ai text update --contains "Synthetic demonstration" \
    --set-contents "Synthetic demonstration schematic (revised)" \
    --set-size 9
ai text update --name t_process --set-font Helvetica-Bold --allow-font-substitute
ai doc save-as "$OUT/$(basename "${SRC%.ai}")_rev1.ai"   # new file, source preserved
ai export preview
ai doc close --save
