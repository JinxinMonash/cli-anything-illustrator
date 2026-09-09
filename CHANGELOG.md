# Changelog

## 0.10.0 (2026-09-09)

High-fidelity reference-figure reconstruction.

- New `figure reconstruct`: rebuild a reference figure (PDF/AI/SVG/EPS or
  raster) as an editable .ai master. Preservation-first routing: vector-native
  references are opened by Illustrator, never redrawn; raster references are
  placed as a locked template layer with optional deterministic Image Trace
  (`--trace`). Modes: auto/preserve/fidelity/recreate/redesign. Writes a full
  manifest (preflight, editability, fidelity metrics, unrecoverable list).
- New `reference` group: `analyze` (preflight recovery plan), `render`
  (deterministic rasteriser), `compare` (SSIM + Sobel edge F1 + CIE76 colour
  delta; per-discrepancy merged difference regions typed geometry/color/text,
  with heatmap and overlay outputs, optionally mapped to document objects).
- New `inspect` group: document/objects/paths/text/gradients/colors/
  editability (structural PASS/WARN/FAIL with outlined-text detection).
- Expanded object model: `path add|edit|compound|clip` (anchors + Bezier
  handles), `gradient add|apply|list`, `style set` (fill/stroke/none, caps,
  joins, miter, dashes, opacity), `object transform` (scale/rotate/translate
  about center or top-left), text typography updates (tracking, leading,
  justification, area-frame sizing).
- `doc report` now includes gradients, clipping masks, symbols, and
  outlined-text suspects.
- Comparison engine improvements found by benchmarking: colour-aware region
  triggering (isoluminant recolours are SSIM-invisible) and same-type
  connected-tile merging (one discrepancy = one region).
- New optional extra: `pip install "cli-anything-illustrator[fidelity]"`.
- Portable suite: 190 tests (object-model mock coverage, fidelity engine
  units, reconstruct end-to-end); live suite extended with reconstruct and
  path round-trip tests.


## 0.9.4 (2026-09-09)

- Windows COM backend rewritten and improved: attaches to a running
  Illustrator session before launching a new one (preserves open documents),
  interprets `--app` as a COM ProgID, maps HRESULTs to the same typed error
  hierarchy as macOS, and reports (rather than hides) the fact that COM calls
  cannot honour hard timeouts. New `windows` install extra
  (`pip install "cli-anything-illustrator[windows]"`). Still experimental:
  not yet validated against a live Windows Illustrator.
- Licensing files consolidated: project licence in `LICENSE`; third-party
  notices in `THIRD_PARTY_NOTICES`.

## 0.9.3 (2026-09-09)

- Live-Mac status upgraded: end-to-end figure generation via Codex confirmed
  on macOS/Illustrator. Validation report and README updated; README gains a
  "Use with Codex" fast path. No behavioural change.

## 0.9.2 (2026-09-09)

- Refined the Codex skill description and workflow statements; rewrote
  README/package descriptions. No behavioural change.

## 0.9.1 (2026-09-09)

- Fixed the AppleScript runner: the application name is now baked into the
  generated script as a compile-time literal so Illustrator's scripting
  dictionary resolves `do javascript`. Regression tests added (portable
  literal/escaping checks + live osacompile check).

## 0.9.0 (2026-09-08)

- Initial release: native macOS control of Adobe Illustrator
  (AppleScript → ExtendScript), editable multi-panel figure assembly from a
  JSON template, selector-based non-destructive editing, publication exports,
  Codex skill packaging, and a portable test suite with a Node-based mock of
  Illustrator's scripting DOM.
