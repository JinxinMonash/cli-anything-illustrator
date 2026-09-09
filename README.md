# cli-anything-illustrator (macOS)

Native command-line control of Adobe Illustrator for **editable scientific
figures**. Give it your R/Python plot exports and a small JSON template, and
it assembles a labelled multi-panel figure you can still edit in Illustrator —
live text, real vector paths, named layers — then delivers publication copies
(PDF, SVG, high-resolution PNG). It also makes targeted, non-destructive
revisions to existing `.ai` artwork and standardises typography and layout.

Confirmed working end-to-end on macOS with Adobe Illustrator, including when
driven by OpenAI Codex through the bundled skill.

## Use with Codex (fastest path)

Paste this into a Codex session on your Mac:

```
Clone https://github.com/JinxinMonash/cli-anything-illustrator.git, install
it with `python3 -m pip install -e .`, run
.agents/skills/cli-anything-illustrator/scripts/install.sh, then run
`cli-anything-illustrator app doctor` and show me the result.
```

Restart Codex so the skill is discovered (check with `/skills`), then work in
plain language:

```
$cli-anything-illustrator assemble panels/*.svg into a 2x2 figure with bold
A–D labels, 180 mm wide, and export a 300-dpi PNG and a PDF
```

Codex fills in a figure template (spec), validates it, assembles the editable
master, and reports the manifest, warnings and a preview. The first Illustrator
call triggers macOS's one-time Automation consent dialog — approve it once
(System Settings → Privacy & Security → Automation if you miss it).

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
- Every mutation is read back; subprocess success is never equated with
  document change.

## Requirements

- macOS with Adobe Illustrator (2020+ recommended) installed and licensed,
  in a logged-in desktop session
- Python ≥ 3.10
- Automation permission for your terminal (`app doctor` walks you through it)

## Manual install & quick start

```bash
git clone https://github.com/JinxinMonash/cli-anything-illustrator.git
cd cli-anything-illustrator
python3 -m pip install -e .
cli-anything-illustrator app doctor    # must be green before editing

cli-anything-illustrator doc new --width 180 --height 120 --units mm
cli-anything-illustrator text add "OD600 (µM)" --x 10 --y 10 --units mm \
    --size 10 --font Helvetica
cli-anything-illustrator doc save-as demo.ai
cli-anything-illustrator export pdf demo.pdf
```

Multi-panel figure from a template:

```bash
python3 examples/make_panels.py --outdir panels        # synthetic demo panels
cli-anything-illustrator figure init figure1_spec.json # template: edit panels/frames
cli-anything-illustrator figure validate --spec figure1_spec.json
cli-anything-illustrator figure assemble --spec figure1_spec.json
cli-anything-illustrator figure verify   --spec figure1_spec.json
```

`assemble` writes the editable `.ai` master, the delivery exports (e.g.
300-dpi PNG), and a manifest recording panel↔source mapping, scale factors
and warnings. Command reference:
[references/commands.md](.agents/skills/cli-anything-illustrator/references/commands.md);
worked examples in `examples/workflow_1_schematic.sh`, `workflow_2_revision.sh`,
`workflow_3_assembly.sh`.

## Reference-figure reconstruction (v0.10)

Reproduce an existing figure — a paper PDF panel, an old AI file, an SVG
export, even a raster scan — as an **editable** Illustrator master, with
measured fidelity instead of claimed fidelity:

```bash
cli-anything-illustrator reference analyze fig3.pdf          # what is recoverable?
cli-anything-illustrator figure reconstruct --reference fig3.pdf \
    --mode auto --output fig3_editable.ai --dpi 300
```

The manifest (`fig3_editable.ai.reconstruct.json`) records the preflight
analysis, an editability score (live text / vector objects / outlined-text
suspects), SSIM + edge + CIE76 colour metrics against the reference, ranked
difference regions mapped to document objects, and an explicit
`unrecoverable` list. Native vector content is opened and preserved, never
redrawn; raster references are placed as a locked template layer (optional
deterministic `--trace`). The iterative loop — export, `reference compare`
(heatmap + overlay), fix the top region with `path edit`/`style set`/
`text update`/`object transform`, repeat — turns "looks about right" into
numbers.

New in the v0.10 object model: `path add|edit|compound|clip` (full Bezier
control), `gradient add|apply|list`, `style set` (caps, joins, dashes,
opacity), `object transform` (rotate/scale/translate about a chosen origin),
`inspect document|objects|paths|text|gradients|colors|editability`, and
typography controls on `text update` (tracking, leading, justification).
Reconstruction needs the fidelity extra:
`pip install "cli-anything-illustrator[fidelity]"` (pymupdf, numpy, pillow).

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
  (`$CAI_LOG_FILE`); figure assembly writes a manifest.
- Machine-readable JSON on stdout, diagnostics on stderr; stable exit codes
  (0/2/3/4/5/6/7/8).

## Testing

```bash
python -m pytest tests/unit tests/e2e_mock         # portable, no Illustrator (92 tests)
python -m pytest tests/integration -m illustrator  # live, macOS + Illustrator
scripts/run_mac_validation.sh                      # one-command live evidence bundle
```

See [VALIDATION_REPORT.md](VALIDATION_REPORT.md) for the evidence trail.

## Design notes

- `export pdf` requires a saved `.ai` master and restores the document's file
  association to it afterwards (Illustrator's `saveAs` changes the association
  as a side effect).
- `figure assemble` is create-only by policy: it always builds a fresh
  document and refuses existing outputs without `--overwrite` — rerun to
  rebuild, so repeated runs are predictable.
- Item `uuid` targeting uses Illustrator's persistent `PageItem.uuid`
  (2020+); `--name` targeting is the fallback on older versions.
- A Windows COM backend is included (`pip install
  "cli-anything-illustrator[windows]"`): same commands, JSON envelope and exit
  codes over COM; it attaches to a running Illustrator before launching a new
  one. Experimental — not yet validated on a live Windows machine; macOS is
  the supported platform.

## License

MIT — see [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES).
