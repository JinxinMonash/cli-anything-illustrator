# Tested command reference

All examples below are exercised by the repository test suite (portable mock
suite; live integration tests mirror them on macOS). JSON envelope on stdout;
add `--compact` for single-line output. `--help` works offline for every
command.

## Diagnostics
```bash
cli-anything-illustrator app detect          # locate app, no launch
cli-anything-illustrator app doctor          # install/permission/session/scripting checks
cli-anything-illustrator app info            # version, path, open docs (launches AI)
```

## Documents
```bash
cli-anything-illustrator doc new --width 180 --height 120 --units mm --color-mode RGB
cli-anything-illustrator doc open /path/fig.ai
cli-anything-illustrator doc list
cli-anything-illustrator doc info --doc figure1.ai
cli-anything-illustrator doc save-as out/master.ai            # refuses existing files
cli-anything-illustrator doc save-as out/master.ai --overwrite
cli-anything-illustrator doc close --doc Untitled-1 --discard-changes
cli-anything-illustrator doc report          # fonts/links/rasters/clipping audit
```
With more than one open document every command requires `--doc <name>`
(error `AMBIGUOUS_DOCUMENT`, exit 5, lists open documents).

## Layers (by name; index-free)
```bash
cli-anything-illustrator layer add Annotations
cli-anything-illustrator layer list
cli-anything-illustrator layer rename "Layer 1" Base
cli-anything-illustrator layer hide Base ; cli-anything-illustrator layer lock Base
cli-anything-illustrator layer remove Annotations          # refuses non-empty
cli-anything-illustrator layer remove Annotations --force  # destructive
```

## Text (live, editable)
```bash
cli-anything-illustrator text add "OD600 (µM) αβγ" --x 10 --y 20 --units mm \
    --size 10 --font Helvetica --color 0,0,0 --layer Labels --layer-create \
    --item-name axis_label
cli-anything-illustrator text list
cli-anything-illustrator text update --name axis_label --set-size 12
cli-anything-illustrator text update --contains "OD600" --set-font Helvetica-Bold
cli-anything-illustrator text update --uuid 12345 --set-contents "new text"
```
Missing fonts are an ERROR (`FONT_NOT_FOUND`) unless `--allow-font-substitute`
is passed; substitution is flagged in the result (`font_substituted: true`).

## Shapes
```bash
cli-anything-illustrator shape rect --x 8 --y 18 --w 28 --h 16 --units mm \
    --fill '#dbe9ff' --stroke 0,0,0 --item-name box1
cli-anything-illustrator shape ellipse --x 44 --y 16 --w 26 --h 20 --units mm
cli-anything-illustrator shape line --x1 36 --y1 26 --x2 44 --y2 26 --units mm
cli-anything-illustrator shape polygon --cx 60 --cy 30 --radius 10 --sides 6
cli-anything-illustrator shape star --cx 60 --cy 30 --radius 10 --inner-radius 5
```
Colours: `r,g,b` (0-255), `#rrggbb`, or `none`.

## Objects (selector-based, persistent uuid targeting)
```bash
cli-anything-illustrator object list --type text --layer Labels
cli-anything-illustrator object rename panel_A_new --uuid 4711
cli-anything-illustrator object move --name panel_A --to 92 0 --units mm
cli-anything-illustrator object scale 50 --name panel_A       # uniform, aspect kept
cli-anything-illustrator object group --layer Panels --group-name all_panels
cli-anything-illustrator object align top --layer grid
cli-anything-illustrator object distribute hdist --layer grid --to artboard
cli-anything-illustrator object delete --name scrap --confirm
```
Selectors: `--uuid --name --layer --type --contains --index`; several may be
combined. A selector matching more than one item is rejected unless `--all`.

## Import & export
```bash
cli-anything-illustrator import panels/panel_A.svg --layer Panels \
    --group-name panel_A --at 0 0 --units mm            # EDITABLE vector import
cli-anything-illustrator import logo.pdf --mode linked   # placed reference only
cli-anything-illustrator export png fig.png --dpi 300 --artboard 0
cli-anything-illustrator export svg fig.svg              # live text kept
cli-anything-illustrator export svg fig_outlined.svg --text-handling outline
cli-anything-illustrator export pdf fig.pdf              # needs saved .ai master
cli-anything-illustrator export preview                  # temp PNG for review
```
Editable import reports `items_copied`, `source_fonts`, and warnings for
raster/linked/legacy-text content. PDF export restores the document's
association with its .ai master afterwards (`reassociated_to`).

## Figures
```bash
cli-anything-illustrator figure init spec.json
cli-anything-illustrator figure validate --spec spec.json
cli-anything-illustrator figure assemble --spec spec.json [--overwrite]
cli-anything-illustrator figure verify --spec spec.json
```
See figure-spec.md for the schema; `assemble` writes
`<master>.ai.manifest.json`.

## Exit codes
0 ok · 2 usage/validation · 3 app missing/platform · 4 automation denied ·
5 document targeting · 6 operation failed · 7 timeout · 8 overwrite refused
