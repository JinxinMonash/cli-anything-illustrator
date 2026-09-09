# Expanded object-model operations — parameter/result contract

Contract for the v0.10 object-model JSX templates. Each op is one template in
`src/cli_anything/illustrator/jsx/`, executed after `prelude.jsx`; parameters
arrive as one JSON document (`CAI.parse(__PARAMS_JSON)`), the result is the
standard envelope `{"ok": true, "result": {...}}` or
`{"ok": false, "error": {"code", "message", "details?"}}`. This file is the
wiring contract for the upstream CLI: field names below match the templates
exactly.

## Conventions shared by every op

- **Coordinates** are CANVAS coordinates: origin at the top-left of the target
  artboard (`artboard` param, default `0`), x right, **y down**, in points.
  Anchors, handles, origins, and reported bounds all use this frame.
  The single exception is **rotation angle**, which keeps Illustrator's
  convention: degrees **counter-clockwise** in the y-up document frame.
- **Common optional params** (every op): `doc` (string; open-document name or
  full path — required when >1 document is open), `artboard` (int, default 0).
- **Selector** object (`selector` param): `{uuid?, name?, layer?, type?,
  contains?, index?}` — all present criteria must match (see `commands.md`).
  Ops that accept multiple matches gate them behind `allow_multiple: bool`
  (default false → `SELECTOR_AMBIGUOUS` on >1 match). `SELECTOR_NO_MATCH`
  when nothing matches.
- **Colors** in params are `[r, g, b]` (0–255). Reported paint values are
  structured: `{"type":"rgb","rgb":[r,g,b]}`, `{"type":"cmyk","cmyk":[c,m,y,k]}`,
  `{"type":"gray","gray":g}`, `{"type":"none"}`,
  `{"type":"gradient","gradient":"<name>","angle":<deg>}`,
  `{"type":"spot","name":...}`, `{"type":"pattern"}`.
- **Item descriptor** (`CAI.describeItem`): `{uuid, name, type, layer, locked,
  hidden, bounds:{x,y,w,h}|null, parent_type, contents?}`.
- **Error codes** used below: `BAD_PARAMS`, `SELECTOR_NO_MATCH`,
  `SELECTOR_AMBIGUOUS`, `NO_DOCUMENT`, `AMBIGUOUS_DOCUMENT`, `DOC_NOT_FOUND`,
  `LAYER_NOT_FOUND`, `GRADIENT_EXISTS`, `GRADIENT_NOT_FOUND`, `FONT_NOT_FOUND`,
  `SCRIPT_ERROR` (unexpected exception).

### Deep path descriptor (returned by path/inspection ops)

`CAI.describePathDeep` = item descriptor plus:

| field | type | meaning |
|---|---|---|
| `closed` | bool | closed path |
| `anchor_count` | int | total anchors on the path |
| `anchors` | array | per anchor: `{anchor:[x,y], left:[x,y], right:[x,y], type:"smooth"\|"corner"}` — canvas coords, absolute handles |
| `anchors_truncated` | bool | true when `anchor_count` exceeded the `limit` |
| `fill`, `stroke` | color | structured paint (see above); `{"type":"none"}` when unpainted |
| `stroke_width` | number | pt |
| `opacity` | number | 0–100 |
| `cap` | `"butt"\|"round"\|"projecting"` | null if unavailable |
| `join` | `"miter"\|"round"\|"bevel"` | null if unavailable |
| `dash` | number[] | `[on, off, ...]` pt; `[]` = solid |
| `dash_offset` | number | pt |
| `miter_limit` | number | |
| `clipping` | bool | path is a clipping path |

---

## path_add

Add an arbitrary Bezier path.

**Params**

| name | type | default | notes |
|---|---|---|---|
| `anchors` | `[[x,y],...]` | required | ≥2 pairs, canvas coords → `BAD_PARAMS` otherwise |
| `left_handles` | `[[x,y]\|null,...]` | all null | absolute canvas coords; null/omitted ⇒ handle = anchor |
| `right_handles` | same | all null | |
| `closed` | bool | false | |
| `fill` | `[r,g,b]` | none | omitted/null ⇒ `filled=false` |
| `stroke` | `[r,g,b]` | none | omitted/null ⇒ `stroked=false` |
| `stroke_width` | number | 1 | applied only with `stroke` |
| `name` | string | — | |
| `layer`, `layer_create` | string, bool | — | move to layer (`LAYER_NOT_FOUND` unless `layer_create`) |
| `limit` | int | 1000 | anchor cap in the result |

A point whose left AND right handle are both given becomes
`PointType.SMOOTH`; otherwise `CORNER`.

**Result**: deep path descriptor of the new path.

## path_edit

Modify anchors/handles of ONE existing path (selector must resolve uniquely;
`selector.type` is forced to `"path"` when absent).

**Params**: `selector` (required), `closed?` (bool), `limit?`, and
`points: [{index, anchor?:[x,y], left?:[x,y], right?:[x,y],
point_type?:"smooth"|"corner"}, ...]`.

Rules: `index` out of range → `BAD_PARAMS`; moving `anchor` without `left`/
`right` translates both handles by the anchor delta; explicit `left`/`right`
are absolute canvas coords; bad `point_type` → `BAD_PARAMS`.

**Result**: deep path descriptor after edits.

## compound_make

Combine ≥2 selector-matched paths into one CompoundPathItem. Non-path matches
are ignored; <2 remaining paths → `BAD_PARAMS`.

**Params**: `selector` (required), `name?`, `layer?`, `layer_create?`
(default layer: first matched path's layer).

**Result**: item descriptor (`type:"compound"`) + `path_count` (int).

## clip_make

Group selector-matched items into a clipping mask. Matches are taken in
stacking order (front first); the **topmost match must be a path or compound
path** and becomes the clipping path (`group.clipped=true`,
`path.clipping=true`; for a compound path, `clipping` is set on its member
paths). <2 matches or non-path on top → `BAD_PARAMS`.

**Params**: `selector` (required), `name?`, `layer?`, `layer_create?`.

**Result**: group item descriptor + `member_count` (int), `clipped: true`,
`clip_bounds: {x,y,w,h}` (canvas bounds of the clipping path; also the
reported group bounds).

## gradient_add

Define (or with `replace:true` redefine) a named document gradient.

**Params**

| name | type | default | notes |
|---|---|---|---|
| `name` | string | required | duplicate without `replace` → `GRADIENT_EXISTS` |
| `type` | `"linear"\|"radial"` | linear | |
| `stops` | array | required | ≥2, each `{offset:0..100, color:[r,g,b], opacity?:0..100, midpoint?:0..100}`; bad offset/color → `BAD_PARAMS` |
| `replace` | bool | false | reuses the existing gradient object (paints keep pointing at it); reducing the stop count of an existing gradient raises `BAD_PARAMS` if the API refuses stop removal |

**Result**: `{name, type:"linear"|"radial", stops:[{offset, midpoint,
color, opacity}], replaced: bool, gradients_defined: int}`.

## gradient_apply

Apply a named gradient to selector-matched items as a `GradientColor`.
Groups/compounds descend to every reachable path; a match with no paintable
path → `BAD_PARAMS`.

**Params**: `gradient` (string, required; unknown → `GRADIENT_NOT_FOUND`),
`selector`, `allow_multiple?`, `target?: "fill"|"stroke"` (default fill),
`angle?` (deg, Illustrator CCW convention, default 0), `origin?: [x,y]`
(canvas coords), `length?` (pt).

**Result**: `{gradient, target, angle, origin, length, updated,
items:[descriptor + paths_painted]}` (`origin`/`length` echo the request,
null when omitted).

## style_set

Stroke/fill styling on selector-matched items (flat params, not nested under
`updates`). Path-level properties descend into groups/compound paths;
`opacity` applies to the matched item itself; `fill` also recolours matched
text frames.

**Params**: `selector`, `allow_multiple?`, plus any of:
`fill: [r,g,b]|"none"`, `stroke: [r,g,b]|"none"`, `stroke_width: number`,
`opacity: 0..100`, `cap: "butt"|"round"|"projecting"`,
`join: "miter"|"round"|"bevel"`, `miter_limit: number`,
`dash: [on,off,...]` (`[]` = solid), `dash_offset: number`.
Unknown cap/join → `BAD_PARAMS`.

**Result**: `{updated, items:[descriptor + paths_styled]}`.

## transform_apply

Scale → rotate → translate, in that order, on selector-matched items.

**Params**: `selector`, `allow_multiple?`, `scale_x?`/`scale_y?` (percent;
one given ⇒ the other defaults to it — pass both for non-uniform),
`rotate?` (deg CCW), `dx?`/`dy?` (canvas, y down),
`about?: "center"|"topleft"` (anchor for scale/rotate, default center;
other values → `BAD_PARAMS`), `preserve_strokes?` (bool, default false —
false scales stroke weights by the mean scale factor).

**Result**: `{updated, items:[{before, after}]}` (item descriptors).

## inspect_document

No params beyond `doc`. **Result**: `{doc: <docInfo>, layers:[{name,
visible, locked, printable, item_counts:{text,path,group,compound,placed,
raster,symbol,other,total}, sublayers:[...recursive...]}]}`.
`item_counts` covers all nested page items of the layer.

## inspect_paths

**Params**: `selector?` (default `{type:"path"}`; a `type` you set yourself
is respected but non-path matches are skipped), `limit?` (anchors per path,
default 1000), `max_paths?` (default 100).
**Result**: `{total_matches, returned, paths:[<deep path descriptor>]}`.

## inspect_text

**Params**: `selector?` (forced `type:"text"`), `limit?` (frames, default
200). **Result**: `{total_matches, returned, frames:[descriptor +
{contents_full, size, font:{name,family,style}|null, tracking, leading,
auto_leading, justification:"left"|"center"|"right"|null, fill,
kind:"point"|"area"}]}`.

## inspect_gradients

No params beyond `doc`. **Result**: `{gradients_defined,
gradients:[{name, type:"linear"|"radial", stop_count,
stops:[{offset, midpoint, color, opacity}]}]}`.

## inspect_colors

Unique paints across `doc.pathItems` (fill+stroke of painted paths) and
`doc.textFrames` (character fill). Gradient paints key by gradient name.
No params beyond `doc`.
**Result**: `{unique_colors, colors:[{color:<structured paint>, fill_count,
stroke_count, text_count}]}`.

## text_update (extended)

New keys inside the existing `updates` object:

| key | type | behaviour |
|---|---|---|
| `tracking` | number | thousandths of an em (Illustrator units) |
| `leading` | number (pt) | also sets `autoLeading=false` |
| `justification` | `"left"\|"center"\|"right"` | other values → `BAD_PARAMS` |
| `width`, `height` | number (pt) | AREA text frames only; on point text → `BAD_PARAMS` |

The per-item `after` snapshot is now the deep text descriptor (same shape as
`inspect_text` frames, superset of the old fields incl. `contents_full`).

## doc_report (extended)

New `editability` block in the report:

```json
"editability": {
  "text_frames": 0, "path_items": 0, "raster_items": 0, "placed_items": 0,
  "gradients_defined": 0, "clipping_groups": 0,
  "locked_items": 0, "hidden_items": 0
}
```

`clipping_groups` counts GroupItems with `clipped=true`; `locked_items` /
`hidden_items` count page items (not layers — locked/hidden layers stay in
`locked_layers`/`hidden_layers`).

---

## Mock-DOM approximations (portable tests only)

- Path bounds are the hull of anchors+handles, not true Bezier extremes.
- Rotation transforms real path points; other items rotate as bbox corners.
- `doc.pageItems` descends into compound paths (live AI exposes members via
  `doc.pathItems`), so selectors can match compound members in the mock.
- Live-Illustrator quirks NOT modelled: `GradientStop.remove()` availability
  varies by AI version; area-text `textPath` resize on rotated frames;
  `tracking` visual reflow. Verify on macOS via `tests/integration`.
