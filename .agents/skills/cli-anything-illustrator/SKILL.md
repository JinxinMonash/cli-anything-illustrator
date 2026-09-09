---
name: cli-anything-illustrator
description: >
  Drive Adobe Illustrator on macOS to inspect, create, revise, assemble,
  reconstruct and export EDITABLE scientific figures via the
  cli-anything-illustrator CLI. Use when the user asks to edit an
  Illustrator/.ai document; combine R/Python plot exports (SVG/PDF/EPS) into a
  labelled multi-panel figure; reproduce or adapt a reference figure
  (PDF/SVG/AI or a raster image) as an editable, high-fidelity Illustrator
  master; standardise fonts, labels, alignment or layout; edit paths,
  gradients or styles; or export publication-ready PDF/SVG/PNG. Do NOT use for
  generic image generation, raster photo editing, data analysis or plotting
  itself, or conversions that do not require Illustrator.
---

# Illustrator scientific figures

One tool, five jobs: **inspect** documents as structured JSON, **create**
editable artwork (text, shapes, Bezier paths, gradients), **revise**
non-destructively, **reconstruct** reference figures with measured fidelity,
and **export** publication files. Figures remain fully editable — live text,
real vector paths, named layers. Scientific content is never altered by
formatting work.

Requires macOS + Adobe Illustrator + Automation permission
(`cli-anything-illustrator app doctor` walks through setup; see
`references/macos-permissions.md`). Reconstruction/comparison additionally
needs `pip install "cli-anything-illustrator[fidelity]"`.

Every command prints a JSON envelope on stdout: `{"ok": true, "result": ...}`
or `{"ok": false, "error": {"code", "message"}}`. Exit codes: 0 ok, 2 usage,
3 app missing, 4 automation denied, 5 document targeting, 6 operation failed,
7 timeout (inspect state before retrying mutations), 8 overwrite refused.

## Core principles

1. **Semantic equivalence is not visual fidelity.** A rebuilt figure that
   "means the same" is not the deliverable; measure likeness with
   `reference compare` instead of asserting it.
2. **Inspect before you touch.** `inspect document` / `inspect objects` /
   `inspect paths` / `inspect text` first; target items by name/uuid/layer
   selectors, never by guessing.
3. **Preserve before you redraw.** If the reference has native vector/text
   content, open it (`figure reconstruct` does this) rather than re-creating
   it. Redrawing is the last resort, and raster references are the only case
   where nothing can be preserved.
4. **Compare before you declare success.** Render, compare, read the ranked
   difference regions, fix, repeat. Report the final metrics and anything
   unrecoverable — never claim a match you have not measured.
5. **Non-destructive by default.** Ambiguous document targets are rejected;
   deletions need `--confirm`; existing files need `--overwrite`; aspect
   ratios are preserved; the reference file itself is never written to.

## Reference-figure reconstruction

```bash
# 1. preflight: what does the reference contain, what is recoverable?
cli-anything-illustrator reference analyze paper_fig3.pdf

# 2. reconstruct as an editable master (mode auto follows the preflight)
cli-anything-illustrator figure reconstruct --reference paper_fig3.pdf \
    --mode auto --output fig3_editable.ai --dpi 300

# 3. read the manifest: editability score, fidelity metrics, ranked
#    difference regions mapped to document objects, unrecoverable items
cat fig3_editable.ai.reconstruct.json
```

Modes: `preserve` (vector-native sources, minimal touch), `fidelity`
(match as closely as possible; raster references are placed as a locked
template layer — add `--trace` for deterministic vectorisation), `recreate`
(same structure, editable rebuild), `redesign` (reference as inspiration).
`preserve` refuses raster references rather than pretending.

Iterative correction loop (fidelity work):

```bash
cli-anything-illustrator export png --doc fig.ai --out cand.png --dpi 300 --overwrite
cli-anything-illustrator inspect objects --doc fig.ai > objects.json
cli-anything-illustrator reference compare ref.pdf cand.png --dpi 300 \
    --objects-json objects.json --heatmap diff_heat.png --overlay diff_ovl.png
# -> metrics {ssim, edge_similarity, color_delta}, largest_differences
#    (bbox_pt + probable_type geometry|color|text), region_objects naming the
#    document items under each region. Fix the top region with path edit /
#    style set / text update / object transform, re-export, re-compare.
```

Honesty requirements: report `unrecoverable` manifest entries verbatim to the
user; a raster reference never yields "recovered" text/vectors, only observed
geometry; if fonts are missing, say which (manifest lists them) and whether
`--allow-font-substitute` was used.

## Multi-panel assembly (plot exports -> figure)

```bash
cli-anything-illustrator figure init spec.json   # commented template
cli-anything-illustrator figure validate --spec spec.json
cli-anything-illustrator figure assemble --spec spec.json
cli-anything-illustrator figure verify --spec spec.json
```

Panels (SVG/PDF/EPS/AI) import as editable vector groups, scaled
uniformly (never stretched), labelled A/B/C..., with delivery exports
(PDF/SVG/300-dpi PNG) and a manifest. Export plots with live text
(matplotlib: `svg.fonttype='none'`; R: `svglite`).

## Precision editing (v0.10 object model)

```bash
cli-anything-illustrator path add --anchors '[[10,10],[60,20],[90,80]]' \
    --right-handles '[[30,5],null,null]' --closed --fill '#4477aa'
cli-anything-illustrator path edit --name curve1 \
    --points '[{"index":2,"anchor":[92,78],"point_type":"smooth"}]'
cli-anything-illustrator gradient add --gradient-name sky --type linear \
    --stops '[{"offset":0,"color":[34,68,170]},{"offset":100,"color":[255,255,255]}]'
cli-anything-illustrator gradient apply --gradient-name sky --name bg --angle 90
cli-anything-illustrator style set --name box --stroke none --fill '200,30,30' \
    --opacity 80 --dash '[4,2]' --cap round
cli-anything-illustrator object transform --name panelB --rotate 90 --about center
cli-anything-illustrator text update --contains "conc." --set-tracking 20 \
    --set-leading 14 --set-justify center
cli-anything-illustrator path clip --layer overlay   # topmost path clips
cli-anything-illustrator inspect editability --doc fig.ai   # PASS/WARN/FAIL
```

Coordinates: artboard top-left origin, y down, points (`--units pt|mm|cm|in`
where offered). Angles: degrees CCW (Illustrator convention).

## Command map

`app detect|doctor|info|launch` · `doc new|open|list|info|save-as|close|report`
(`project` = alias) · `layer list|add|remove|rename|show|hide|lock|unlock` ·
`text add|list|update` · `shape rect|ellipse|line|polygon|star|list` ·
`path add|edit|compound|clip` · `gradient add|apply|list` · `style set` ·
`object list|rename|move|scale|transform|group|align|distribute|delete` ·
`inspect document|objects|paths|text|gradients|colors|editability` ·
`reference analyze|render|compare` · `import` · `export png|svg|pdf|preview` ·
`fonts list` · `figure init|validate|assemble|verify|reconstruct`

Details: `references/commands.md`, `references/figure-spec.md`,
`references/reconstruction.md`. Global flags: `--doc`, `--app`, `--timeout`,
`--compact`. `--help` works offline for every command.
