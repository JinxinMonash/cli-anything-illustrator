# Figure specification schema (version 1)

Paths are resolved relative to the spec file's directory. The whole spec is
validated before any document is created; errors are reported all at once.

```jsonc
{
  "version": 1,
  "canvas": {
    "width": 180, "height": 122,     // required, > 0
    "units": "mm",                    // "mm" | "pt"
    "color_mode": "RGB",              // "RGB" | "CMYK"
    "title": "figure1"                // optional, informational
  },
  "defaults": {
    "label": { "font": "Helvetica-Bold", "size_pt": 12,
                "color": [0,0,0], "offset": [1,1] }   // offset in canvas units
  },
  "panels": [                         // >= 1; ids must be unique
    {
      "id": "A",                      // group becomes panel_A, label label_A
      "source": "panels/panel_A.svg", // .svg/.ai/.pdf/.eps, must exist
      "mode": "editable",             // "editable" (default) | "linked"
      "frame": { "x": 0, "y": 0, "w": 88, "h": 58 },  // canvas units, in-bounds
      "fit": "contain",               // only "contain": aspect always preserved
      "label": { "text": "A" }        // optional; style keys override defaults
    }
  ],
  "output": {
    "ai": "figure1.ai",               // required master (.ai)
    "exports": [                      // optional delivery copies
      { "format": "pdf", "path": "figure1.pdf" },
      { "format": "png", "path": "figure1_300dpi.png", "dpi": 300 },
      { "format": "svg", "path": "figure1.svg" }
    ]
  }
}
```

Behaviour:
- Document layout: panels as groups `panel_<id>` on layer `Panels`; labels as
  text `label_<id>` on layer `Labels`.
- Panels are scaled uniformly to fit the frame (never stretched) and placed
  with the frame's top-left corner.
- Repeat-execution policy: `assemble` always creates a NEW document and
  refuses existing output files without `--overwrite`. There is no in-place
  update; re-run to rebuild.
- The manifest (`<master>.ai.manifest.json`) records panel→source mapping,
  scale percentages, fonts seen in sources, warnings (rasters, linked items,
  substituted fonts) and output file sizes. `partial: true` marks aborted runs.
- Generating source panels from matplotlib: set `svg.fonttype = 'none'` so
  text stays editable; otherwise text arrives pre-outlined (reported as
  "no live text frames" warning).
