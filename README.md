# cli-anything-illustrator (macOS)

Command-line control of Adobe Illustrator for **editable scientific figures**:
assemble R/Python plot exports into multi-panel figures, standardise
typography and layout, make targeted revisions to existing artwork, and export
publication files — while keeping text live and vectors editable.

Adapted from the Windows COM Illustrator harness in
[yb2460/harness-anything](https://github.com/yb2460/harness-anything)
(commit `dcb3e51`, MIT); see [PROVENANCE.md](PROVENANCE.md) for the audit and
reuse matrix.

## Architecture

```
Codex skill (.agents/skills/cli-anything-illustrator)
    -> cli-anything-illustrator (Python / Click)
    -> macOS backend: osascript runner (AppleScript)
    -> "do javascript": parameterised ExtendScript templates inside Illustrator
    -> JSON result envelope on stdout + native .ai/.pdf/.svg/.png artifacts
```

- Operation logic lives in static JSX templates (`src/.../jsx/`); parameters
  travel as an ASCII JSON literal — user text is never spliced into code.
- Windows COM support survives as an isolated, **experimental** backend
  (`backend/win.py`) sharing the same templates.
- Every mutation is read back; subprocess success is never equated with
  document change.

## Requirements

- macOS with Adobe Illustrator (2020+ recommended) installed and licensed,
  in a logged-in desktop session
- Python ≥ 3.10
- Automation permission for your terminal (System Settings → Privacy &
  Security → Automation → enable Adobe Illustrator); `app doctor` walks you
  through it

## Install

```bash
git clone <this repo> && cd cli-anything-illustrator
python3 -m pip install -e .            # or: pip install -e ".[dev]" for tests
cli-anything-illustrator app doctor    # must be all green before editing
```

Codex skill (user scope, refuses silent overwrite):

```bash
.agents/skills/cli-anything-illustrator/scripts/install.sh
```

## Quick start

```bash
cli-anything-illustrator doc new --width 180 --height 120 --units mm
cli-anything-illustrator text add "OD600 (µM)" --x 10 --y 10 --units mm \
    --size 10 --font Helvetica
cli-anything-illustrator doc save-as demo.ai
cli-anything-illustrator export pdf demo.pdf
```

Multi-panel figure from plot exports:

```bash
python3 examples/make_panels.py --outdir panels     # synthetic demo panels
cli-anything-illustrator figure init figure1_spec.json
cli-anything-illustrator figure validate --spec figure1_spec.json
cli-anything-illustrator figure assemble --spec figure1_spec.json
cli-anything-illustrator figure verify   --spec figure1_spec.json
```

Full command reference:
[.agents/skills/cli-anything-illustrator/references/commands.md](.agents/skills/cli-anything-illustrator/references/commands.md).
Example end-to-end workflows: `examples/workflow_1_schematic.sh`,
`workflow_2_revision.sh`, `workflow_3_assembly.sh`.

## Conventions & safety model

- **Coordinates:** origin at the target artboard's top-left, x right,
  **y down**, points by default (`--units pt|mm|cm|in`).
- **Targeting:** explicit `--doc` required when several documents are open;
  items addressed by persistent `uuid` or `name`; ambiguous selectors are
  rejected (never "whichever is active").
- **Non-destructive defaults:** existing files are never overwritten without
  `--overwrite`; deletion needs `--confirm`; non-empty layer removal needs
  `--force`; closing unsaved changes needs `--discard-changes`/`--save`;
  missing fonts error unless substitution is explicitly allowed (and is then
  reported).
- **Editability:** imports default to real editable vector/text content;
  linked placements and rasters are flagged as not editable; SVG export keeps
  live text unless `--text-handling outline` is requested.
- **Record:** every command appends to `cai_illustrator_log.jsonl`
  (`$CAI_LOG_FILE`); figure assembly writes a manifest with panel↔source
  mapping, scale factors and warnings.
- Machine-readable JSON on stdout, diagnostics on stderr; stable exit codes
  (0/2/3/4/5/6/7/8 — see `errors.py`).

## Testing

```bash
python -m pytest tests/unit tests/e2e_mock         # portable (no Illustrator)
python -m pytest tests/integration -m illustrator  # LIVE, macOS + Illustrator
scripts/run_mac_validation.sh                      # one-command live evidence
```

The portable suite includes a Node-based mock of Illustrator's scripting DOM
that executes the real ExtendScript templates; see
[VALIDATION_REPORT.md](VALIDATION_REPORT.md) for exactly what has and has not
been proven, and on which platform.

## Known limitations

- PDF export re-saves the master to restore its file association (Illustrator
  `saveAs` side effect); requires a saved `.ai` first.
- `figure assemble` is create-only (documented policy) — re-run with
  `--overwrite` to rebuild; there is no in-place panel update.
- Item `uuid` targeting depends on the installed Illustrator exposing
  `PageItem.uuid` (2020+); name-based targeting is the fallback.
- Windows backend is untested here and marked experimental.
