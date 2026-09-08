---
name: cli-anything-illustrator
description: >
  Control Adobe Illustrator on macOS to inspect, create, revise, assemble and
  export EDITABLE scientific figures via the cli-anything-illustrator CLI.
  Use when the user asks to edit an Illustrator/.ai document, assemble R/Python
  plot panels (SVG/PDF) into a multi-panel figure, standardise figure fonts,
  labels or layout, add annotations, or export publication PDF/SVG/PNG from
  Illustrator artwork. Do NOT use for generic image generation, raster photo
  editing, data analysis/plotting itself, or file conversion that does not
  require Illustrator.
---

# cli-anything-illustrator

Drive Adobe Illustrator natively (AppleScript → ExtendScript) through the
`cli-anything-illustrator` command. Every command prints a JSON envelope on
stdout: `{"ok": true, "command": ..., "result": ...}` or
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
   Illustrator under the terminal/host app), no usable session, or scripting
   errors. Never proceed while doctor fails; never try to bypass permissions.

## Core workflow: inspect → plan → edit → verify → export

1. **Inspect.** `doc list` (reject ambiguity: pass `--doc <name>` everywhere
   when >1 document is open), `doc info`, `doc report` (fonts, missing links,
   rasters, locked layers), `object list`/`text list` to get item `uuid`s and
   names.
2. **Plan.** State the intended operations to the user before mutating
   someone's existing artwork. All commands are logged to
   `cai_illustrator_log.jsonl` (or `$CAI_LOG_FILE`) as the operation record.
3. **Edit within scope.** Target items by `--uuid` (preferred, persistent) or
   `--name`; ambiguous selectors are rejected — never loosen a selector just
   to make a command pass, and only add `--all` when the user asked for a
   bulk change. Deletion needs `--confirm`; non-empty layer removal needs
   `--force`; closing unsaved work needs `--discard-changes` or `--save`.
4. **Verify.** Read back: `text list`, `object list`, `doc report`. Do not
   report success from exit code alone for multi-step edits.
5. **Export.** `doc save-as new.ai` (master, stays editable; overwriting any
   existing file requires `--overwrite`), then `export pdf/svg/png`.
   `export preview` renders a temporary PNG for the user to review.

## Scientific-figure rules (non-negotiable)

- Formatting requests are NOT permission to alter results: never change
  numbers, axis scales, error bars, statistical annotations or data marks.
  If a request would require redrawing data, refuse and explain.
- Keep text live and vectors editable; `--mode linked` placements and raster
  content are reported as NOT editable — say so. Text outlining only on
  explicit request (`export svg --text-handling outline` affects only the
  exported copy).
- Aspect ratios are preserved (`fit: contain`); never stretch a panel.
- Fonts: a missing font is an error unless the user approves substitution
  (`--allow-font-substitute`); report any substitution.
- Default to NEW output files; never overwrite the user's source without
  explicit instruction. Journal requirements only when the user supplies them.
- A figure is "submission-ready" only after human review of the preview.

## Multi-panel assembly

```bash
cli-anything-illustrator figure init figure1_spec.json   # template spec
# edit the spec: canvas (mm), panels[{id, source, frame{x,y,w,h}, label}], output
cli-anything-illustrator figure validate --spec figure1_spec.json
cli-anything-illustrator figure assemble --spec figure1_spec.json
cli-anything-illustrator doc close --doc figure1.ai --discard-changes
cli-anything-illustrator figure verify --spec figure1_spec.json
```

`assemble` builds a new document (never updates in place), imports each panel
as an editable group `panel_<id>` on layer `Panels`, adds labels on layer
`Labels`, saves the `.ai` master, writes delivery exports, and emits
`<master>.ai.manifest.json` (source→panel mapping, scale factors, warnings).
Read the manifest and report warnings (rasters, substituted fonts, linked
content) to the user. `verify` reopens the master and checks panels, labels,
live text, fonts and export files.

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
