#!/usr/bin/env bash
# Representative workflow 1: a simple EDITABLE schematic built from scratch.
# Everything stays live vector + live text in the saved .ai master.
set -euo pipefail
OUT="${1:-schematic_demo}"
mkdir -p "$OUT"

ai() { cli-anything-illustrator --compact "$@"; }

ai doc new --width 120 --height 60 --units mm --base-layer Diagram
ai shape rect    --x 8  --y 18 --w 28 --h 16 --units mm --fill '#dbe9ff' --stroke 0,0,0 --item-name box_input
ai shape rect    --x 78 --y 18 --w 30 --h 16 --units mm --fill '#dfffe0' --stroke 0,0,0 --item-name box_output
ai shape ellipse --x 44 --y 16 --w 26 --h 20 --units mm --fill '#fff3c4' --stroke 0,0,0 --item-name node_process
ai shape line --x1 36 --y1 26 --x2 44 --y2 26 --units mm --stroke 0,0,0 --stroke-width 1.2
ai shape line --x1 70 --y1 26 --x2 78 --y2 26 --units mm --stroke 0,0,0 --stroke-width 1.2
ai text add "Input"   --x 12 --y 27 --units mm --size 10 --font Helvetica --item-name t_input
ai text add "Process" --x 49 --y 27 --units mm --size 10 --font Helvetica --item-name t_process
ai text add "Output"  --x 83 --y 27 --units mm --size 10 --font Helvetica --item-name t_output
ai text add "Synthetic demonstration schematic" --x 8 --y 8 --units mm --size 8 --item-name t_note
ai doc save-as "$OUT/schematic.ai"
ai export pdf "$OUT/schematic.pdf" --overwrite
ai export preview
ai doc report
