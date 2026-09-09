# Reference-figure reconstruction — detailed guide

## Decision tree

```
reference analyze <file>
 ├─ classes.vector_native.present (PDF/AI/SVG/EPS with real vectors)
 │    └─ figure reconstruct --mode preserve|fidelity   (opens natively: P1/P2)
 ├─ text_outlined (vector file, text converted to paths)
 │    └─ preserve keeps outlines as-is; note in report that text is not live;
 │       to restore live text: text add over the outlines, then delete outlines
 ├─ raster only (PNG/JPEG/TIFF, or PDF that is one big image)
 │    └─ fidelity + --trace (deterministic Image Trace, live only)  (P3)
 │       or manual reconstruction over the locked template layer    (P4)
 └─ recreate / redesign: new canvas + locked reference template     (P4/P5)
```

## Reading `reference analyze` output

- `recovery_plan.recommended_mode` — what `--mode auto` will do.
- `classes.vector_native / text_live / text_outlined / raster_embedded /
  gradients / clipping` — each `{present, count?, notes}`.
- `fonts` (PDF/SVG): names referenced by the reference; check availability
  with `fonts list --contains <name>` BEFORE reconstructing.
- `warnings` — e.g. multi-page PDF, unsupported EPS preview.

## The manifest (`<output>.reconstruct.json`)

| key | meaning |
|---|---|
| `preflight` | full `reference analyze` result |
| `mode`, `route` | what was actually done (`native_open`, `raster_template`, `canvas_prep`) |
| `editability` | live_text / vector_objects / outlined_suspects counts + PASS/WARN/FAIL |
| `compare` | metrics + ranked `largest_differences` + `region_objects` (null when skipped) |
| `unrecoverable` | items that CANNOT be recovered — report these verbatim |
| `warnings` | substitutions and degradations |

## Fidelity thresholds (practical guidance)

- `ssim` > 0.97 and no `high` regions: visually faithful for review purposes.
- `ssim` 0.90-0.97: inspect `largest_differences`; usually fonts or colour
  profile shifts.
- `edge_similarity` low but ssim high: geometry subtly displaced (check
  `probable_type: geometry` regions first).
- `color_delta` (mean CIE76) > 5: systematic colour shift — check document
  colour mode (RGB vs CMYK) before touching individual objects.
- Regions are merged per discrepancy and mapped to objects via
  `--objects-json`; fix the top-ranked region, re-export, re-compare.

## Known Illustrator scripting limitations (documented fallbacks)

- **Opacity masks / blend modes** cannot be created via ExtendScript;
  reconstruct them manually in the UI (the manifest lists them as
  unrecoverable when detected in PDF references).
- **Image Trace presets** are not scriptable per-parameter; `--trace` uses
  the application default preset deterministically.
- **PDF text** can arrive fragmented (one frame per glyph run). The
  editability report counts frames; consolidate with text update only when
  needed — merging frames is a manual judgement call.
- **EPS previews** cannot be rendered for comparison without Illustrator;
  compare uses the reconstructed export only after opening.
