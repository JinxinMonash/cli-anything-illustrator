# Fidelity engine API contract

Pure-Python subpackage `cli_anything.illustrator.fidelity` (v0.10.0 track).
No Illustrator interaction; every function is a pure function over file
paths and plain dicts. This document is the upstream CLI-wiring contract
and matches the code exactly.

## Dependencies

| package | tested version | needed by |
|---|---|---|
| pymupdf | 1.28.2 | `analyze` (PDF/AI), `render` (PDF/AI/SVG) |
| numpy   | 2.4.6  | `compare` |
| pillow  | 12.3.0 | `analyze` (raster), `render` (raster), `compare` (I/O) |

`editability` and SVG/EPS analysis are stdlib-only. Imports are lazy:
`import cli_anything.illustrator.fidelity` always succeeds; a missing
dependency raises `ImportError` at first use with the message naming
`pip install "cli-anything-illustrator[fidelity]"` (the `[fidelity]`
extra itself must be added to `pyproject.toml` upstream:
`fidelity = ["pymupdf>=1.24", "numpy>=1.24", "pillow>=10"]`).

Determinism: no randomness anywhere; identical inputs give identical
outputs (SSIM/Sobel/CIE76 are closed-form numpy).

## Public API (lazy, PEP 562)

```python
from cli_anything.illustrator import fidelity
fidelity.analyze_reference(path)
fidelity.render_reference(path, dpi, out_png, page=0)
fidelity.compare_images(ref_png, candidate_png, tile=64, dpi=96.0,
                        heatmap_png=None, overlay_png=None)
fidelity.map_regions_to_objects(regions, objects_json, dpi=96.0)
fidelity.score_editability(doc_report)
fidelity.require(module_name)   # helper: import-or-actionable-error
```

---

## `analyze_reference(path) -> dict`

Preflight analysis of a reference figure. Format is chosen by extension:
`.pdf`/`.ai` (PyMuPDF), `.svg` (xml.etree), `.eps` (DSC header only),
`.png`/`.jpg`/`.jpeg`/`.tif`/`.tiff` (Pillow).

Errors: `FileNotFoundError` (missing path), `ValueError` (unsupported
extension), `ImportError` (missing optional dependency).

### Common keys (all formats)

| key | type | meaning |
|---|---|---|
| `format` | str | `"pdf" \| "ai" \| "svg" \| "eps" \| "raster"` |
| `path` | str | input path |
| `width_pt`, `height_pt` | float\|None | canvas size in points (first page for PDF; None when EPS lacks a BoundingBox) |
| `page_count` | int | 1 for non-PDF |
| `fonts` | list | per-format shape, see below |
| `totals` | dict | `{vector_drawings, fills, strokes, gradients, text_spans, images}`; `None` where not measurable (SVG fills/strokes, all EPS totals) |
| `transparency` | bool | opacity < 1, image soft masks, alpha channel, or (SVG) clipPath/rgba() present |
| `warnings` | list[str] | human-readable preflight warnings |
| `recovery_plan` | dict | see below |

### `recovery_plan`

```
{
  "classes": {
    "vector_native": {"present": bool, "detail": str},
    "text_live":     {"present": bool, "count": int, "warnings": [str]},
    "raster_only":   {"present": bool, "count": int, "warnings": [str]}
  },
  "primary_class":    "vector_native" | "raster_only",
  "recommended_mode": "preserve" | "fidelity",
  "trace_route":      null | "image_trace",
  "warnings":         [str]           # union of per-class warnings
}
```

Rules: vector formats (pdf/ai/svg/eps) are `vector_native.present=true`
and get `recommended_mode="preserve"`, `trace_route=null` — **unless** the
container holds only raster content (images > 0, vector drawings == 0,
live text == 0; scan-style PDF), which flips to
`primary_class="raster_only"`, `recommended_mode="fidelity"`,
`trace_route="image_trace"` with an explanatory warning. Raster formats
always get the fidelity/trace route. `raster_only.count` is the embedded
image count (1 for a raster file). Per-class warnings include: fonts not
embedded (text_live), low-resolution raster < 150 dpi and scan-style
containers (raster_only).

### PDF/AI extras

`pages`: list of per-page dicts:

```
{
  "index": int, "width_pt": float, "height_pt": float,
  "vector": {"drawings": int,   # page.get_drawings() paths
             "fills": int,      # drawings whose type contains "f"
             "strokes": int,    # drawings whose type contains "s"
             "gradients": int}, # `sh` operators + /Pattern cs in content
                                # streams (detectable subset)
  "text_spans": [{"text": str, "font": str, "size": float,
                  "bbox": [x0,y0,x1,y1] (pt, PDF page space),
                  "color": "#rrggbb"}],
  "fonts":  [{"name": str, "type": str, "embedded": bool}],
  "images": [{"xref": int, "width_px": int, "height_px": int,
              "has_alpha": bool,  # soft mask present
              "dpi_estimate": float|None}]  # px / (placed pt / 72)
}
```

Document-level `fonts` is the per-page union (embedded = true if embedded
anywhere), sorted by name. `.ai` files are analyzed as PDF (works for
PDF-compatible AI saves; a non-PDF-compatible AI raises pymupdf's open
error).

### SVG extras

- `viewbox`: `[minx, miny, w, h]` floats or None.
- `elements`: counts for `path, rect, circle, ellipse, line, polygon,
  polyline, text, image, linearGradient, radialGradient, clipPath`.
- `colors`: sorted unique values of `fill`/`stroke`/`stop-color`
  attributes and the same properties inside `style="..."` (excluding
  `none/inherit/currentColor`), verbatim strings.
- `text_spans`: `[{text, font, size}]` (font/size from presentation
  attributes or inline style; size converted to pt).
- `fonts`: sorted unique font-family strings.
- Unit conversion: 1px = 0.75pt (96 dpi convention); unitless = px;
  `%` yields None; missing width/height falls back to viewBox * 0.75.

### EPS extras (header-only)

`bounding_box` (`[llx,lly,urx,ury]` from `%%HiResBoundingBox` or
`%%BoundingBox`, else None), `creator`, `fonts` = `[{"name": str}]` from
`%%DocumentFonts`/`%%DocumentNeededFonts`. Always warns that EPS
preflight is header-only.

### Raster extras

```
"raster": {"width_px": int, "height_px": int, "mode": str,
           "dpi": (x, y)|None, "has_alpha": bool,
           "channel_means": [r, g, b],
           "approx_unique_colors": int|None}   # on a <=64x64 thumbnail
```

`width_pt`/`height_pt` use metadata dpi (assume 72 when absent, with a
warning). Resolution below 150 dpi adds a low-resolution warning.

---

## `render_reference(path, dpi, out_png, page=0) -> dict`

Renders PDF/AI/SVG via PyMuPDF (`Matrix(dpi/72, dpi/72)`, no alpha) and
raster inputs via Pillow resize-to-dpi passthrough (Lanczos; source dpi
from metadata, 72 assumed when absent; re-encoded as RGB PNG with target
dpi metadata). Parent directories of `out_png` are created.

Returns `{out_png: str, width_px: int, height_px: int, dpi: float,
source_format: "pdf"|"ai"|"svg"|"raster", page: int}` — width/height are
the exact pixel dimensions of the written PNG.

Errors: `FileNotFoundError`; `ValueError` for dpi <= 0, page out of
range, or unsupported extension (**EPS is not renderable** without
Illustrator/Ghostscript); `ImportError` for missing deps.

---

## `compare_images(ref_png, candidate_png, tile=64, dpi=96.0, heatmap_png=None, overlay_png=None) -> dict`

Registration: if candidate dims differ from reference by <= 2% per axis,
candidate is Lanczos-resized to reference dims (`candidate.resized:
true`); a larger mismatch raises `ValueError`. All metrics are then
computed at reference dimensions.

Return value:

```
{
  "reference": {"path": str, "width_px": int, "height_px": int},
  "candidate": {"path": str, "width_px": int, "height_px": int,
                "resized": bool},           # original candidate dims
  "dpi": float, "tile_size": int,
  "metrics": {
    "pixel_mae": float,        # mean |ref-cand| over RGB, 0-255 scale
    "rmse": float,             # root mean square error, 0-255 scale
    "ssim": float,             # mean SSIM map; 11x11 gaussian window
                               # sigma=1.5, K1=0.01, K2=0.03, L=255,
                               # on 0.299/0.587/0.114 grayscale
    "edge_similarity": float,  # F1 between Sobel edge maps thresholded
                               # at gradient magnitude 96 (0-255 gray);
                               # 1.0 when both maps are empty
    "color_delta": float       # mean CIE76 delta-E (sRGB->D65 Lab)
  },
  "largest_differences": [     # <= 10, ranked by score desc
    {"rank": int,                        # 1-based
     "tiles": int,                       # flagged tiles merged into region
     "bbox_px": [x1, y1, x2, y2],        # reference pixels; bounding box of
                                          # an 8-connected group of flagged
                                          # tiles (one region per discrepancy)
     "bbox_pt": [x1, y1, x2, y2],        # = px * 72 / dpi
     "score": float,                     # mean (1 - SSIM) in tile
     "severity": "high"|"med"|"low",     # >0.5 / >0.2 / otherwise
     "color_delta": float,               # tile mean CIE76
     "edge_density": float,              # union edge fraction in tile
     "probable_type": "color"|"text"|"geometry"}
  ],
  "artifacts": {"heatmap_png": str, "overlay_png": str}
}
```

A tile becomes a region when mean (1-SSIM) > 0.02 OR mean CIE76
delta-E > 6.0 (catches isoluminant recolours that SSIM cannot see);
`score` = max(mean 1-SSIM, mean delta-E / 50, capped at 1). Identical
images give an empty list. `probable_type` heuristic, in order: **color** when the
two edge maps disagree on < 1% of tile pixels but tile mean delta-E > 8
(same geometry, different colour); **text** when union edge density >
0.14 (dense strokes); else **geometry**.

Artifacts (default paths `<candidate stem>_heatmap.png` /
`_overlay.png`): the heatmap is the per-tile 1-SSIM grid (normalized to
its max) under a viridis-like ramp, upscaled to full size and
alpha-blended over the reference (alpha 0.15–0.75 scaling with severity);
the overlay renders reference ink in magenta and candidate ink in green
(overlap = black, background = white) for alignment checking.

Errors: `FileNotFoundError`, `ValueError` (registration failure or
tile <= 0), `ImportError`.

---

## `map_regions_to_objects(regions, objects_json, dpi=96.0) -> list`

Maps discrepancy regions to Illustrator item descriptors.

- `regions`: list of dicts; each needs `bbox_pt` `[x1,y1,x2,y2]` in
  points (as produced by `compare_images`) or `bbox_px` (converted with
  `dpi`). A region with neither raises `ValueError`.
- `objects_json`: the CLI's items_list shape — a list of
  `{"name": str, "uuid": str, "type": str,
    "bounds": {"x", "y", "w", "h"}}` with bounds in POINTS (canvas
  coords, top-left origin, y down — same space as `bbox_pt`), or a dict
  whose `items` (or `results`) key holds that list. Items without
  `bounds` are skipped.

Returns one entry per region, in input order:

```
[{"region_index": int,                 # 0-based input position
  "bbox_pt": [x1, y1, x2, y2],
  "probable_type": str|None,           # copied through from the region
  "candidates": [                      # <= 5, overlap > 0 only
    {"uuid": str|None, "name": str, "type": str|None,
     "overlap_fraction": float}        # intersection area / region area
  ]}]                                  # ranked: overlap desc, then
                                       # smaller item area, then name
```

---

## `score_editability(doc_report) -> dict`

Stdlib-only. Input: the JSON returned by the CLI `doc report` operation
(`jsx/doc_report.jsx`): `text_frames`, `raster_items`, `placed_items`,
`page_items`, `layers` (int), `legacy_text_items`, `clipping_paths`,
`fonts_unavailable[]`, `placed_links[{name,missing,file}]`,
`locked_layers[]`, `hidden_layers[]` — every key optional; `None`/`{}`
tolerated. An optional `editability` counts block
(`{live_text, vector_objects | path_items, gradients, clipping_groups,
rasterized_regions | raster_items}`) takes precedence for the counts it
carries.

Returns:

```
{
  "live_text": int|None,            # live (non-legacy) text frames
  "text_objects": int|None,         # live + legacy
  "vector_objects": int|None,       # from editability block, else
                                    # page_items - text - legacy -
                                    # raster - placed (floor 0);
                                    # None when underivable
  "rasterized_regions": int|None,
  "gradients": int|None,            # None unless the report carries it
  "layers": {"count": int|None, "locked": [str], "hidden": [str]},
  "clipping_groups": int|None,      # editability block or clipping_paths
  "editability_status": "PASS"|"WARN"|"FAIL",
  "reasons": [str]                  # "WARN: ..."/"FAIL: ..." per finding;
                                    # empty for a clean PASS
}
```

Status: **FAIL** — `page_items == 0`; or live_text == 0 and
vector_objects == 0 with no legacy text (nothing editable); or text
exists but ALL of it is legacy. **WARN** — rasterized regions present;
unavailable fonts; legacy text alongside live text; missing placed
links; locked or hidden layers; empty report or report lacking item
counts. **PASS** otherwise. Highest severity wins; all findings are
listed in `reasons`.

---

## Tests

`tests/unit/test_fidelity_analyze.py` (15), `test_fidelity_compare.py`
(14), `test_fidelity_editability.py` (13) — 42 tests, all synthetic
fixtures built at test time (PyMuPDF-generated PDF with rects, a bezier,
two fonts and an embedded PNG; Pillow-generated rasters; inline SVG).
Suites skip cleanly when pymupdf is not installed
(`pytest.importorskip`), so the base test matrix is unaffected.
Verified: 95 baseline tests + 42 new = 137 passed (python 3.x, pymupdf
1.28.2, numpy 2.4.6, pillow 12.3.0, node v18).
