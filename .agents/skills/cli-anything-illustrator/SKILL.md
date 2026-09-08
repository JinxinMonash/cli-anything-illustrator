---
name: cli-anything-illustrator
description: >
  Inspect, create, revise, assemble and export EDITABLE scientific figures in
  Adobe Illustrator on macOS through the cli-anything-illustrator CLI. Use for
  requests to edit an Illustrator/.ai document, combine R/Python plot exports
  (SVG/PDF/EPS) into a labelled multi-panel figure from a JSON template
  (figure spec), standardise figure fonts, labels, alignment or layout, add
  approved annotations, or deliver publication-ready PDF/SVG and
  high-resolution PNG from Illustrator artwork. Do NOT use for generic image
  generation, raster photo editing, data analysis or plotting itself, or file
  conversion that does not require Illustrator.
---

# cli-anything-illustrator

Drive Adobe Illustrator natively on macOS (AppleScript → ExtendScript)
through the `cli-anything-illustrator` command. Given a figure template
(spec) and the user's plot exports, it produces an editable,
high-resolution multi-panel figure in one pass. The guiding principle:
figures remain fully editable — live text, real vector paths, named layers —
and the scientific content of a figure is never altered by formatting work.

Every command prints a JSON envelope on stdout:
`{"ok": true, "command": ..., "result": ...}` or
`{"ok": false, "error": {"code", "message", "details"}}`. Exit codes:
0 ok · 2 usage · 3 app missing/platform · 4 automation permission denied ·
5 document targeting · 6 operation failed · 7 timeout · 8 overwrite refused.

## Prerequisites (check before any editing)

1. macOS with Adobe Illustrator installed, licensed, and a logged-in desktop
   session. This cannot run on Linux/CI or control a remote Mac.
2. Package installed: `pip install -e <repo>` → `cli-anything-illustrator --help`.
3. Run `cli-anything-illustrator app doctor` FIRST. It distinguishes:
   app not installed (exit 3), Automation permission denied (exit 4 — tell the
   user: System Settings → Privacy & Security → Automation → enable Adobe
   Illustrator under the terminal/host app), no usable session, and scripting
   errors. Never proceed while doctor fails; never try to bypass permissions.

## Core workflow: inspect → plan → edit → verify → export

1. **Inspect.** `doc list` (with more than one document open, pass
   `--doc <name>` on every command — ambiguous targets are rejected, never
   guessed), `doc info`, `doc report` (fonts, missing links, rasters, locked
   layers), and `object list`/`text list` to obtain item `uuid`s and names.
2. **Plan.** Before mutating existing artwork, state the intended operations
   to the user. Every command is appended to the operation record
   (`cai_illustrator_log.jsonl` / `$CAI_LOG_FILE`) for later review.
3. **Edit within the requested scope.** Target items by `--uuid` (preferred,
   persistent) or `--name`; an ambiguous selector is an error — refine it
   rather than loosening it, and add `--all` only for user-requested bulk
   changes. Destructive steps are gated: deletion requires `--confirm`,
   removing a non-empty layer requires `--force`, closing unsaved work
   requires `--discard-changes` or `--save`.
4. **Verify.** Read the result back (`text list`, `object list`,
   `doc report`); exit code alone is not evidence for a multi-step edit.
5. **Export.** `doc save-as new.ai` for the editable master (overwriting any
   existing file needs `--overwrite`), then `export pdf/svg/png` for delivery
   copies. `export preview` renders a temporary PNG for the user to review.

## Scientific-figure rules (non-negotiable)

- A formatting request is NOT permission to alter results: never change
  numbers, axis scales, error bars, statistical annotations, or the identity
  of data marks. If a request would require redrawing data, decline and
  explain what would be needed instead.
- Keep content editable: text stays live and vectors stay paths. Linked
  placements (`--mode linked`) and raster content are reported as not
  editable — pass that on. Outlining text happens only on explicit request,
  and `export svg --text-handling outline` affects the exported copy only.
- Aspect ratios are always preserved (`fit: contain`); panels are scaled,
  never stretched.
- A missing font is an error unless the user approves substitution
  (`--allow-font-substitute`); every substitution is reported.
- Default to new output files; never overwrite a source file without an
  explicit instruction. Apply journal requirements only when the user
  supplies or confirms them.
- A figure is "submission-ready" only after the user has reviewed a preview.

## Multi-panel assembly

```bash
cli-anything-illustrator figure init figure1_spec.json   # template spec
# edit the spec: canvas (mm), panels[{id, source, frame{x,y,w,h}, label}], output
cli-anything-illustrator figure validate --spec figure1_spec.json
cli-anything-illustrator figure assemble --spec figure1_spec.json
cli-anything-illustrator doc close --doc figure1.ai --discard-changes
cli-anything-illustrator figure verify --spec figure1_spec.json
```

`assemble` validates the whole spec before touching Illustrator, then builds
a new document (never edits in place): each panel is imported as an editable
group `panel_<id>` on layer `Panels`, labels go on layer `Labels`, the `.ai`
master is saved, delivery exports are written, and
`<master>.ai.manifest.json` records the source→panel mapping, scale factors
and warnings. Read the manifest and report warnings (rasters, substituted
fonts, linked content) to the user. `verify` reopens the master and checks
panels, labels, live text, fonts and export files.

## Command survey (details: references/commands.md)

- `app detect|doctor|info|launch` — diagnostics
- `doc new|open|list|info|save-as|close|report` (`project` = alias)
- `layer list|add|remove|rename|show|hide|lock|unlock` (by name)
- `text add|list|update` · `shape rect|ellipse|line|polygon|star|list`
- `object list|rename|move|scale|group|align|distribute|delete`
- `import SRC --mode editable|linked` · `export png|svg|pdf|preview`
- `fonts list` · `figure init|validate|assemble|verify`

Coordinates: origin at the target artboard's TOP-LEFT, y downward; `--units
pt|mm|cm|in` (default pt). Global flags: `--doc`, `--app`, `--timeout`,
`--compact`. After a timeout (exit 7), inspect `doc list`/`doc info` before
retrying any mutation.
