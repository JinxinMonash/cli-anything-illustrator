# -*- coding: utf-8 -*-
"""cli-anything-illustrator -- command-line control of Adobe Illustrator.

Machine-readable JSON goes to stdout; diagnostics go to stderr.
`--help` works everywhere without contacting Illustrator.
"""
from __future__ import annotations

import datetime
import json
import os
import sys
import tempfile

import click

from cli_anything.illustrator import __version__
from cli_anything.illustrator.backend import select_backend
from cli_anything.illustrator.errors import CAIError, EXIT_USAGE, ValidationError
from cli_anything.illustrator.ops import diagnose as diag_ops
from cli_anything.illustrator.ops import figure as figure_ops
from cli_anything.illustrator.ops.common import (
    build_selector, prepare_output_path, require_input_path, rgb_triplet, to_pt,
)

LOG_ENV = "CAI_LOG_FILE"
DEFAULT_LOG = "cai_illustrator_log.jsonl"


# ---------------------------------------------------------------- helpers
def _log(ctx, command: str, ok: bool, error_code: str | None = None):
    if ctx.obj.get("no_log"):
        return
    path = os.environ.get(LOG_ENV, DEFAULT_LOG)
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "command": command,
                "argv": sys.argv[1:],
                "ok": ok,
                "error_code": error_code,
            }, ensure_ascii=False) + "\n")
    except OSError:
        pass  # logging must never break an operation


def _emit(ctx, command: str, result):
    envelope = {"ok": True, "command": command, "result": result}
    indent = None if ctx.obj.get("compact") else 2
    click.echo(json.dumps(envelope, indent=indent, ensure_ascii=False,
                          default=str))
    _log(ctx, command, ok=True)


def _backend(ctx):
    if "backend" not in ctx.obj:
        ctx.obj["backend"] = select_backend(
            ctx.obj.get("app"), platform=os.environ.get("CAI_PLATFORM"))
    return ctx.obj["backend"]


def _run(ctx, command: str, op_name: str, params: dict):
    result = _backend(ctx).run_op(op_name, params, timeout=ctx.obj["timeout"])
    _emit(ctx, command, result)


def _doc_params(doc):
    return {"doc": doc} if doc else {}


def doc_option(f):
    return click.option(
        "--doc", default=None,
        help="Target document name or full path. Required when more than one "
             "document is open (ambiguous targets are rejected).")(f)


def units_option(f):
    return click.option("--units", default="pt",
                        type=click.Choice(["pt", "mm", "cm", "in"]),
                        show_default=True,
                        help="Units for coordinates/sizes in this command.")(f)


def selector_options(f):
    for deco in (
        click.option("--index", type=int, default=None,
                     help="Pick the Nth match (0-based) AFTER other filters."),
        click.option("--contains", default=None,
                     help="Match text frames whose contents contain this string."),
        click.option("--type", "item_type", default=None,
                     type=click.Choice(["text", "path", "group", "placed",
                                        "raster", "compound", "symbol"]),
                     help="Match item type."),
        click.option("--layer", default=None, help="Match layer name."),
        click.option("--name", default=None, help="Match exact item name."),
        click.option("--uuid", default=None,
                     help="Match persistent item UUID (from object list)."),
    ):
        f = deco(f)
    return f


# ---------------------------------------------------------------- root
@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="cli-anything-illustrator")
@click.option("--app", default=None,
              help="Illustrator application name or .app path "
                   "(default: auto-discover; env CAI_ILLUSTRATOR_APP).")
@click.option("--timeout", type=float, default=120.0, show_default=True,
              help="Per-operation timeout in seconds.")
@click.option("--compact", is_flag=True, help="Compact single-line JSON output.")
@click.option("--no-log", is_flag=True,
              help="Do not append to the operation record "
                   f"({DEFAULT_LOG} / ${LOG_ENV}).")
@click.pass_context
def cli(ctx, app, timeout, compact, no_log):
    """Control Adobe Illustrator from the command line (macOS-native).

    Machine-readable JSON on stdout; diagnostics on stderr. Non-destructive
    by default: overwrites, deletions and closing unsaved documents all
    require explicit flags.
    """
    ctx.ensure_object(dict)
    ctx.obj.update({"app": app, "timeout": timeout, "compact": compact,
                    "no_log": no_log})


# ---------------------------------------------------------------- app
@cli.group(name="app")
def app_grp():
    """Application diagnostics: detect, doctor, info, launch."""


@app_grp.command("detect")
@click.pass_context
def app_detect(ctx):
    """Locate the installed Illustrator application (no launch)."""
    if sys.platform != "darwin" and not os.environ.get("CAI_PLATFORM"):
        raise CAIError("Detection requires macOS.", code="UNSUPPORTED_PLATFORM")
    from cli_anything.illustrator.backend.mac import discover_illustrator
    _emit(ctx, "app detect", discover_illustrator(ctx.obj.get("app")))


@app_grp.command("doctor")
@click.pass_context
def app_doctor(ctx):
    """Full diagnostic: platform, install, permissions, scripting round trip."""
    _emit(ctx, "app doctor", diag_ops.doctor(ctx.obj.get("app")))


@app_grp.command("info")
@click.pass_context
def app_info(ctx):
    """Version, path, locale, open documents (launches Illustrator)."""
    _run(ctx, "app info", "app_info", {})


@app_grp.command("launch")
@click.pass_context
def app_launch(ctx):
    """Launch Illustrator and verify scripting works."""
    _run(ctx, "app launch", "ping", {"echo": "launch"})


# ---------------------------------------------------------------- doc
@cli.group(name="doc")
def doc_grp():
    """Document management: new, open, list, info, save-as, close, report."""


@doc_grp.command("new")
@click.option("--width", type=float, default=612.0, show_default=True)
@click.option("--height", type=float, default=792.0, show_default=True)
@units_option
@click.option("--color-mode", default="RGB", type=click.Choice(["RGB", "CMYK"]),
              show_default=True)
@click.option("--base-layer", default=None, help="Rename the initial layer.")
@click.pass_context
def doc_new(ctx, width, height, units, color_mode, base_layer):
    """Create a new document (unsaved until doc save-as)."""
    _run(ctx, "doc new", "doc_new", {
        "width": to_pt(width, units), "height": to_pt(height, units),
        "color_mode": color_mode, "base_layer_name": base_layer})


@doc_grp.command("open")
@click.argument("path")
@click.pass_context
def doc_open(ctx, path):
    """Open an existing document (.ai/.svg/.pdf/.eps)."""
    _run(ctx, "doc open", "doc_open", {"path": require_input_path(path)})


@doc_grp.command("list")
@click.pass_context
def doc_list(ctx):
    """List open documents."""
    _run(ctx, "doc list", "doc_list", {})


@doc_grp.command("info")
@doc_option
@click.pass_context
def doc_info(ctx, doc):
    """Properties and object counts of a document."""
    _run(ctx, "doc info", "doc_info", _doc_params(doc))


@doc_grp.command("save-as")
@click.argument("path")
@doc_option
@click.option("--overwrite", is_flag=True, help="Allow replacing an existing file.")
@click.pass_context
def doc_save_as(ctx, path, doc, overwrite):
    """Save the document as a native .ai file (new file by default)."""
    if not path.lower().endswith(".ai"):
        raise ValidationError("doc save-as writes native .ai files; "
                              "use the export group for PDF/SVG/PNG.")
    out = prepare_output_path(path, overwrite)
    params = _doc_params(doc)
    params["path"] = out
    _run(ctx, "doc save-as", "doc_saveas", params)


@doc_grp.command("close")
@doc_option
@click.option("--save", "mode", flag_value="save",
              help="Save changes to the existing file, then close.")
@click.option("--discard-changes", "mode", flag_value="discard",
              help="Close WITHOUT saving (explicit authorisation).")
@click.pass_context
def doc_close(ctx, doc, mode):
    """Close a document. Refuses to drop unsaved changes without a flag."""
    params = _doc_params(doc)
    params["mode"] = mode or "refuse"
    _run(ctx, "doc close", "doc_close", params)


@doc_grp.command("report")
@doc_option
@click.pass_context
def doc_report(ctx, doc):
    """Integrity report: fonts, links, rasters, clipping, locked/hidden layers."""
    _run(ctx, "doc report", "doc_report", _doc_params(doc))


# ---------------------------------------------------------------- layer
@cli.group(name="layer")
def layer_grp():
    """Layer management (by NAME, not by mutable index)."""


@layer_grp.command("list")
@doc_option
@click.pass_context
def layer_list(ctx, doc):
    """List layers."""
    _run(ctx, "layer list", "layer_list", _doc_params(doc))


@layer_grp.command("add")
@click.argument("name")
@doc_option
@click.option("--existing-ok", is_flag=True, help="No error if it already exists.")
@click.pass_context
def layer_add(ctx, name, doc, existing_ok):
    """Add a new top layer."""
    params = _doc_params(doc)
    params.update({"name": name, "existing_ok": existing_ok})
    _run(ctx, "layer add", "layer_add", params)


@layer_grp.command("remove")
@click.argument("name")
@doc_option
@click.option("--force", is_flag=True,
              help="Required when the layer still contains items (destructive).")
@click.pass_context
def layer_remove(ctx, name, doc, force):
    """Remove a layer by name (refuses non-empty layers without --force)."""
    params = _doc_params(doc)
    params.update({"name": name, "force": force})
    _run(ctx, "layer remove", "layer_remove", params)


def _layer_set(ctx, doc, name, updates, command):
    params = _doc_params(doc)
    params.update({"name": name, "updates": updates})
    _run(ctx, command, "layer_set", params)


@layer_grp.command("show")
@click.argument("name")
@doc_option
@click.pass_context
def layer_show(ctx, name, doc):
    """Make a layer visible."""
    _layer_set(ctx, doc, name, {"visible": True}, "layer show")


@layer_grp.command("hide")
@click.argument("name")
@doc_option
@click.pass_context
def layer_hide(ctx, name, doc):
    """Hide a layer."""
    _layer_set(ctx, doc, name, {"visible": False}, "layer hide")


@layer_grp.command("lock")
@click.argument("name")
@doc_option
@click.pass_context
def layer_lock(ctx, name, doc):
    """Lock a layer against edits."""
    _layer_set(ctx, doc, name, {"locked": True}, "layer lock")


@layer_grp.command("unlock")
@click.argument("name")
@doc_option
@click.pass_context
def layer_unlock(ctx, name, doc):
    """Unlock a layer."""
    _layer_set(ctx, doc, name, {"locked": False}, "layer unlock")


@layer_grp.command("rename")
@click.argument("name")
@click.argument("new_name")
@doc_option
@click.pass_context
def layer_rename(ctx, name, new_name, doc):
    """Rename a layer."""
    _layer_set(ctx, doc, name, {"new_name": new_name}, "layer rename")


# ---------------------------------------------------------------- text
@cli.group(name="text")
def text_grp():
    """Text operations: add, list, update (text stays live/editable)."""


@text_grp.command("add")
@click.argument("contents")
@click.option("--x", type=float, required=True,
              help="Canvas x (from artboard top-left, y down).")
@click.option("--y", type=float, required=True, help="Canvas y.")
@units_option
@click.option("--size", type=float, default=12.0, show_default=True,
              help="Font size in pt.")
@click.option("--font", default=None,
              help="PostScript or family name; errors if unavailable unless "
                   "--allow-font-substitute.")
@click.option("--allow-font-substitute", is_flag=True,
              help="Keep the application default if --font is unavailable "
                   "(substitution is reported).")
@click.option("--color", default="0,0,0", show_default=True,
              help="Fill colour 'r,g,b' or '#rrggbb'.")
@click.option("--layer", default=None, help="Place on this layer.")
@click.option("--layer-create", is_flag=True, help="Create --layer if missing.")
@click.option("--item-name", default=None, help="Persistent item name.")
@click.option("--area", nargs=2, type=float, default=None,
              help="W H: create area text in a box instead of point text.")
@click.option("--justify", default=None,
              type=click.Choice(["left", "center", "right"]))
@doc_option
@click.pass_context
def text_add(ctx, contents, x, y, units, size, font, allow_font_substitute,
             color, layer, layer_create, item_name, area, justify, doc):
    """Add live (editable) point or area text."""
    params = _doc_params(doc)
    params.update({
        "contents": contents, "x": to_pt(x, units), "y": to_pt(y, units),
        "size": size, "font": font,
        "allow_font_substitute": allow_font_substitute,
        "color": rgb_triplet(color), "layer": layer,
        "layer_create": layer_create, "name": item_name,
        "kind": "area" if area else "point",
        "justification": justify,
    })
    if area:
        params["box_w"] = to_pt(area[0], units)
        params["box_h"] = to_pt(area[1], units)
    _run(ctx, "text add", "text_add", params)


@text_grp.command("list")
@doc_option
@click.pass_context
def text_list(ctx, doc):
    """List all text frames (uuid, name, contents, layer, bounds)."""
    params = _doc_params(doc)
    params["selector"] = {"type": "text"}
    _run(ctx, "text list", "items_list", params)


@text_grp.command("update")
@selector_options
@doc_option
@click.option("--all", "allow_multiple", is_flag=True,
              help="Apply to ALL matches (default: exactly one match required).")
@click.option("--set-contents", default=None, help="Replace text contents.")
@click.option("--set-size", type=float, default=None)
@click.option("--set-tracking", type=float, default=None,
              help="Thousandths of an em.")
@click.option("--set-leading", type=float, default=None, help="Points.")
@click.option("--set-justify", type=click.Choice(["left", "center", "right"]),
              default=None)
@click.option("--set-width", type=float, default=None,
              help="Area text frames only (pt).")
@click.option("--set-height", type=float, default=None,
              help="Area text frames only (pt).")
@click.option("--set-font", default=None)
@click.option("--allow-font-substitute", is_flag=True)
@click.option("--set-color", default=None, help="'r,g,b' or '#rrggbb'.")
@click.option("--set-name", default=None)
@click.option("--move-to", nargs=2, type=float, default=None,
              help="X Y: new canvas position.")
@units_option
@click.pass_context
def text_update(ctx, uuid, name, layer, item_type, contains, index, doc,
                allow_multiple, set_contents, set_size, set_tracking,
                set_leading, set_justify, set_width, set_height, set_font,
                allow_font_substitute, set_color, set_name, move_to, units):
    """Update matched text frames (selector must resolve uniquely, or --all)."""
    updates = {}
    if set_contents is not None:
        updates["contents"] = set_contents
    if set_size is not None:
        updates["size"] = set_size
    if set_tracking is not None:
        updates["tracking"] = set_tracking
    if set_leading is not None:
        updates["leading"] = set_leading
    if set_justify is not None:
        updates["justification"] = set_justify
    if set_width is not None:
        updates["width"] = set_width
    if set_height is not None:
        updates["height"] = set_height
    if set_font is not None:
        updates["font"] = set_font
        updates["allow_font_substitute"] = allow_font_substitute
    if set_color is not None:
        updates["color"] = rgb_triplet(set_color)
    if set_name is not None:
        updates["new_name"] = set_name
    if move_to is not None:
        updates["x"] = to_pt(move_to[0], units)
        updates["y"] = to_pt(move_to[1], units)
    if not updates:
        raise ValidationError("Nothing to update: pass at least one --set-*/--move-to.")
    params = _doc_params(doc)
    params.update({
        "selector": build_selector(uuid, name, layer, item_type, contains, index),
        "updates": updates, "allow_multiple": allow_multiple})
    _run(ctx, "text update", "text_update", params)


# ---------------------------------------------------------------- shape
@cli.group(name="shape")
def shape_grp():
    """Vector shapes: rect, ellipse, line, polygon, star, list."""


def _shape_common(f):
    for deco in (
        click.option("--stroke-width", type=float, default=1.0, show_default=True),
        click.option("--stroke", default=None, help="'r,g,b' / '#rrggbb' / 'none'."),
        click.option("--fill", default="128,128,128", show_default=True,
                     help="'r,g,b' / '#rrggbb' / 'none'."),
        click.option("--item-name", default=None),
        click.option("--layer", default=None),
        click.option("--layer-create", is_flag=True),
    ):
        f = deco(f)
    return doc_option(f)


def _color_or_none(value):
    if value is None or str(value).lower() == "none":
        return None
    return rgb_triplet(value)


def _shape_params(ctx, doc, kind, units, fill, stroke, stroke_width,
                  item_name, layer, layer_create, **geom):
    params = _doc_params(doc)
    params.update({
        "kind": kind,
        "fill": _color_or_none(fill), "stroke": _color_or_none(stroke),
        "stroke_width": stroke_width, "name": item_name,
        "layer": layer, "layer_create": layer_create,
    })
    for k, v in geom.items():
        params[k] = to_pt(v, units) if v is not None else None
    return params


@shape_grp.command("rect")
@click.option("--x", type=float, required=True)
@click.option("--y", type=float, required=True)
@click.option("--w", type=float, required=True)
@click.option("--h", type=float, required=True)
@click.option("--corner-radius", type=float, default=0.0, show_default=True)
@units_option
@_shape_common
@click.pass_context
def shape_rect(ctx, x, y, w, h, corner_radius, units, doc, fill, stroke,
               stroke_width, item_name, layer, layer_create):
    """Rectangle at canvas (x, y) with width/height."""
    _run(ctx, "shape rect", "shape_add", _shape_params(
        ctx, doc, "rect", units, fill, stroke, stroke_width, item_name,
        layer, layer_create, x=x, y=y, w=w, h=h, corner_radius=corner_radius))


@shape_grp.command("ellipse")
@click.option("--x", type=float, required=True, help="Bounding-box left.")
@click.option("--y", type=float, required=True, help="Bounding-box top.")
@click.option("--w", type=float, required=True)
@click.option("--h", type=float, required=True)
@units_option
@_shape_common
@click.pass_context
def shape_ellipse(ctx, x, y, w, h, units, doc, fill, stroke, stroke_width,
                  item_name, layer, layer_create):
    """Ellipse inside the given bounding box."""
    _run(ctx, "shape ellipse", "shape_add", _shape_params(
        ctx, doc, "ellipse", units, fill, stroke, stroke_width, item_name,
        layer, layer_create, x=x, y=y, w=w, h=h))


@shape_grp.command("line")
@click.option("--x1", type=float, required=True)
@click.option("--y1", type=float, required=True)
@click.option("--x2", type=float, required=True)
@click.option("--y2", type=float, required=True)
@units_option
@_shape_common
@click.pass_context
def shape_line(ctx, x1, y1, x2, y2, units, doc, fill, stroke, stroke_width,
               item_name, layer, layer_create):
    """Straight line segment (stroked, unfilled)."""
    params = _shape_params(ctx, doc, "line", units, None, stroke or "0,0,0",
                           stroke_width, item_name, layer, layer_create,
                           x1=x1, y1=y1, x2=x2, y2=y2)
    _run(ctx, "shape line", "shape_add", params)


@shape_grp.command("polygon")
@click.option("--cx", type=float, required=True)
@click.option("--cy", type=float, required=True)
@click.option("--radius", type=float, required=True)
@click.option("--sides", type=int, default=6, show_default=True)
@units_option
@_shape_common
@click.pass_context
def shape_polygon(ctx, cx, cy, radius, sides, units, doc, fill, stroke,
                  stroke_width, item_name, layer, layer_create):
    """Regular polygon centred at (cx, cy)."""
    params = _shape_params(ctx, doc, "polygon", units, fill, stroke,
                           stroke_width, item_name, layer, layer_create,
                           cx=cx, cy=cy, radius=radius)
    params["sides"] = sides
    _run(ctx, "shape polygon", "shape_add", params)


@shape_grp.command("star")
@click.option("--cx", type=float, required=True)
@click.option("--cy", type=float, required=True)
@click.option("--radius", type=float, required=True, help="Outer radius.")
@click.option("--inner-radius", type=float, required=True)
@click.option("--points", type=int, default=5, show_default=True)
@units_option
@_shape_common
@click.pass_context
def shape_star(ctx, cx, cy, radius, inner_radius, points, units, doc, fill,
               stroke, stroke_width, item_name, layer, layer_create):
    """Star centred at (cx, cy)."""
    params = _shape_params(ctx, doc, "star", units, fill, stroke, stroke_width,
                           item_name, layer, layer_create,
                           cx=cx, cy=cy, radius=radius, inner_radius=inner_radius)
    params["points"] = points
    _run(ctx, "shape star", "shape_add", params)


@shape_grp.command("list")
@doc_option
@click.pass_context
def shape_list(ctx, doc):
    """List path items."""
    params = _doc_params(doc)
    params["selector"] = {"type": "path"}
    _run(ctx, "shape list", "items_list", params)


# ---------------------------------------------------------------- object
@cli.group(name="object")
def object_grp():
    """Object discovery and non-destructive editing (uuid/name targeting)."""


@object_grp.command("list")
@selector_options
@doc_option
@click.option("--limit", type=int, default=200, show_default=True)
@click.pass_context
def object_list(ctx, uuid, name, layer, item_type, contains, index, doc, limit):
    """List/find page items (persistent uuid where the API provides one)."""
    params = _doc_params(doc)
    params["selector"] = build_selector(uuid, name, layer, item_type,
                                        contains, index, required=False)
    params["limit"] = limit
    _run(ctx, "object list", "items_list", params)


@object_grp.command("rename")
@click.argument("new_name")
@selector_options
@doc_option
@click.pass_context
def object_rename(ctx, new_name, uuid, name, layer, item_type, contains,
                  index, doc):
    """Give the matched item a persistent name (unique match required)."""
    params = _doc_params(doc)
    params.update({"selector": build_selector(uuid, name, layer, item_type,
                                              contains, index),
                   "updates": {"new_name": new_name}})
    _run(ctx, "object rename", "item_update", params)


@object_grp.command("move")
@selector_options
@doc_option
@click.option("--to", "to_xy", nargs=2, type=float, default=None,
              help="X Y: absolute canvas position of the top-left corner.")
@click.option("--by", "by_xy", nargs=2, type=float, default=None,
              help="DX DY: relative move (y down).")
@units_option
@click.option("--all", "allow_multiple", is_flag=True)
@click.pass_context
def object_move(ctx, uuid, name, layer, item_type, contains, index, doc,
                to_xy, by_xy, units, allow_multiple):
    """Move matched item(s)."""
    if (to_xy is None) == (by_xy is None):
        raise ValidationError("Pass exactly one of --to X Y or --by DX DY.")
    updates = {}
    if to_xy:
        updates["x"] = to_pt(to_xy[0], units)
        updates["y"] = to_pt(to_xy[1], units)
    else:
        updates["dx"] = to_pt(by_xy[0], units)
        updates["dy"] = to_pt(by_xy[1], units)
    params = _doc_params(doc)
    params.update({"selector": build_selector(uuid, name, layer, item_type,
                                              contains, index),
                   "updates": updates, "allow_multiple": allow_multiple})
    _run(ctx, "object move", "item_update", params)


@object_grp.command("scale")
@click.argument("percent", type=float)
@selector_options
@doc_option
@click.option("--all", "allow_multiple", is_flag=True)
@click.pass_context
def object_scale(ctx, percent, uuid, name, layer, item_type, contains, index,
                 doc, allow_multiple):
    """Uniform scale (aspect ratio preserved; strokes scaled) about top-left."""
    if percent <= 0:
        raise ValidationError("Scale percent must be > 0.")
    params = _doc_params(doc)
    params.update({"selector": build_selector(uuid, name, layer, item_type,
                                              contains, index),
                   "updates": {"scale_percent": percent},
                   "allow_multiple": allow_multiple})
    _run(ctx, "object scale", "item_update", params)


@object_grp.command("group")
@selector_options
@doc_option
@click.option("--group-name", default=None)
@click.option("--target-layer", default=None)
@click.pass_context
def object_group(ctx, uuid, name, layer, item_type, contains, index, doc,
                 group_name, target_layer):
    """Group all matched items into a named group."""
    params = _doc_params(doc)
    params.update({"selector": build_selector(uuid, name, layer, item_type,
                                              contains, index),
                   "name": group_name, "layer": target_layer})
    _run(ctx, "object group", "group_make", params)


@object_grp.command("delete")
@selector_options
@doc_option
@click.option("--all", "allow_multiple", is_flag=True)
@click.option("--confirm", is_flag=True,
              help="REQUIRED: deletion is destructive.")
@click.pass_context
def object_delete(ctx, uuid, name, layer, item_type, contains, index, doc,
                  allow_multiple, confirm):
    """Delete matched item(s). Requires --confirm."""
    params = _doc_params(doc)
    params.update({"selector": build_selector(uuid, name, layer, item_type,
                                              contains, index),
                   "allow_multiple": allow_multiple, "confirm": confirm})
    _run(ctx, "object delete", "item_delete", params)


@object_grp.command("align")
@click.argument("mode", type=click.Choice(["left", "hcenter", "right", "top",
                                           "vcenter", "bottom"]))
@selector_options
@doc_option
@click.option("--to", "reference", default="selection",
              type=click.Choice(["selection", "artboard"]), show_default=True)
@click.pass_context
def object_align(ctx, mode, uuid, name, layer, item_type, contains, index,
                 doc, reference):
    """Align matched items to the selection bbox or the artboard."""
    params = _doc_params(doc)
    params.update({"selector": build_selector(uuid, name, layer, item_type,
                                              contains, index),
                   "mode": mode, "reference": reference})
    _run(ctx, "object align", "align_items", params)


@object_grp.command("distribute")
@click.argument("mode", type=click.Choice(["hdist", "vdist"]))
@selector_options
@doc_option
@click.option("--to", "reference", default="selection",
              type=click.Choice(["selection", "artboard"]), show_default=True)
@click.pass_context
def object_distribute(ctx, mode, uuid, name, layer, item_type, contains,
                      index, doc, reference):
    """Distribute matched items with equal gaps."""
    params = _doc_params(doc)
    params.update({"selector": build_selector(uuid, name, layer, item_type,
                                              contains, index),
                   "mode": mode, "reference": reference})
    _run(ctx, "object distribute", "align_items", params)


# ---------------------------------------------------------------- import
@cli.command(name="import")
@click.argument("source")
@doc_option
@click.option("--mode", default="editable",
              type=click.Choice(["editable", "linked"]), show_default=True,
              help="'editable' opens and copies real vector content; "
                   "'linked' only places a reference (not editable).")
@click.option("--layer", default=None, help="Target layer (created if needed).")
@click.option("--group-name", default=None, help="Name for the imported group.")
@click.option("--at", "at_xy", nargs=2, type=float, default=None,
              help="X Y: place the content's top-left here.")
@units_option
@click.pass_context
def import_cmd(ctx, source, doc, mode, layer, group_name, at_xy, units):
    """Import SVG/AI/PDF/EPS artwork into a document."""
    params = _doc_params(doc)
    params.update({"source": require_input_path(source), "mode": mode,
                   "layer": layer, "name": group_name})
    if at_xy:
        params["x"] = to_pt(at_xy[0], units)
        params["y"] = to_pt(at_xy[1], units)
    _run(ctx, "import", "import_file", params)


# ---------------------------------------------------------------- export
@cli.group(name="export")
def export_grp():
    """Delivery copies: png, svg, pdf, preview. The .ai master stays editable."""


@export_grp.command("png")
@click.argument("path")
@doc_option
@click.option("--dpi", type=float, default=300.0, show_default=True)
@click.option("--artboard", type=int, default=0, show_default=True)
@click.option("--no-transparency", is_flag=True)
@click.option("--overwrite", is_flag=True)
@click.pass_context
def export_png(ctx, path, doc, dpi, artboard, no_transparency, overwrite):
    """Export an artboard as PNG."""
    out = prepare_output_path(path, overwrite)
    params = _doc_params(doc)
    params.update({"path": out, "dpi": dpi, "artboard": artboard,
                   "transparent": not no_transparency})
    _run(ctx, "export png", "export_png", params)


@export_grp.command("svg")
@click.argument("path")
@doc_option
@click.option("--text-handling", default="keep",
              type=click.Choice(["keep", "outline"]), show_default=True,
              help="'outline' outlines text ONLY in the exported file.")
@click.option("--no-embed-raster", is_flag=True)
@click.option("--overwrite", is_flag=True)
@click.pass_context
def export_svg(ctx, path, doc, text_handling, no_embed_raster, overwrite):
    """Export as SVG (live text kept by default)."""
    out = prepare_output_path(path, overwrite)
    params = _doc_params(doc)
    params.update({"path": out, "text_handling": text_handling,
                   "embed_raster": not no_embed_raster})
    _run(ctx, "export svg", "export_svg", params)


@export_grp.command("pdf")
@click.argument("path")
@doc_option
@click.option("--no-editability", is_flag=True,
              help="Drop Illustrator editing data from the PDF.")
@click.option("--overwrite", is_flag=True)
@click.pass_context
def export_pdf(ctx, path, doc, no_editability, overwrite):
    """Export as PDF (requires a saved .ai master; association is restored)."""
    out = prepare_output_path(path, overwrite)
    params = _doc_params(doc)
    params.update({"path": out, "editable": not no_editability})
    _run(ctx, "export pdf", "export_pdf", params)


@export_grp.command("preview")
@doc_option
@click.option("--dpi", type=float, default=96.0, show_default=True)
@click.option("--artboard", type=int, default=0, show_default=True)
@click.pass_context
def export_preview(ctx, doc, dpi, artboard):
    """Quick PNG preview to a temporary file (path reported for review)."""
    out = os.path.join(tempfile.mkdtemp(prefix="cai-preview-"), "preview.png")
    params = _doc_params(doc)
    params.update({"path": out, "dpi": dpi, "artboard": artboard,
                   "transparent": False})
    _run(ctx, "export preview", "export_png", params)


# ---------------------------------------------------------------- fonts
@cli.group(name="fonts")
def fonts_grp():
    """Font inventory in the running Illustrator."""


@fonts_grp.command("list")
@click.option("--contains", default=None, help="Filter by name/family substring.")
@click.option("--limit", type=int, default=100, show_default=True)
@click.pass_context
def fonts_list(ctx, contains, limit):
    """List installed fonts visible to Illustrator."""
    _run(ctx, "fonts list", "fonts_list", {"contains": contains, "limit": limit})


# ---------------------------------------------------------------- figure
@cli.group(name="figure")
def figure_grp():
    """Multi-panel scientific figure assembly from a JSON spec."""


@figure_grp.command("validate")
@click.option("--spec", "spec_path", required=True, type=click.Path(exists=True))
@click.pass_context
def figure_validate(ctx, spec_path):
    """Validate a figure spec without touching Illustrator."""
    spec = figure_ops.load_spec(spec_path)
    errs = figure_ops.validate_spec(spec, os.path.dirname(os.path.abspath(spec_path)))
    if errs:
        raise ValidationError(
            "Spec validation failed:\n  - " + "\n  - ".join(errs),
            details={"spec": os.path.abspath(spec_path), "errors": errs})
    _emit(ctx, "figure validate",
          {"spec": os.path.abspath(spec_path), "valid": True, "errors": []})


@figure_grp.command("assemble")
@click.option("--spec", "spec_path", required=True, type=click.Path(exists=True))
@click.option("--overwrite", is_flag=True,
              help="Allow replacing existing output files.")
@click.option("--allow-font-substitute", is_flag=True)
@click.pass_context
def figure_assemble(ctx, spec_path, overwrite, allow_font_substitute):
    """Assemble panels into an editable master figure + delivery exports."""
    spec = figure_ops.load_spec(spec_path)
    manifest = figure_ops.assemble(
        _backend(ctx), spec, os.path.dirname(os.path.abspath(spec_path)),
        overwrite=overwrite, timeout=ctx.obj["timeout"],
        allow_font_substitute=allow_font_substitute)
    _emit(ctx, "figure assemble", manifest)


@figure_grp.command("verify")
@click.option("--spec", "spec_path", required=True, type=click.Path(exists=True))
@click.pass_context
def figure_verify(ctx, spec_path):
    """Reopen the saved master and verify the assembly against the spec."""
    spec = figure_ops.load_spec(spec_path)
    result = figure_ops.verify(_backend(ctx), spec,
                               os.path.dirname(os.path.abspath(spec_path)),
                               timeout=ctx.obj["timeout"])
    _emit(ctx, "figure verify", result)


@figure_grp.command("init")
@click.argument("path")
@click.option("--overwrite", is_flag=True)
@click.pass_context
def figure_init(ctx, path, overwrite):
    """Write a commented example figure spec to PATH."""
    out = prepare_output_path(path, overwrite)
    example = {
        "version": 1,
        "canvas": {"width": 180, "height": 120, "units": "mm",
                   "color_mode": "RGB", "title": "figure1"},
        "defaults": {"label": {"font": "Helvetica", "size_pt": 12,
                               "color": [0, 0, 0], "offset": [2, 2]}},
        "panels": [
            {"id": "A", "source": "panels/panel_A.svg", "mode": "editable",
             "frame": {"x": 0, "y": 0, "w": 88, "h": 58},
             "fit": "contain", "label": {"text": "A"}},
            {"id": "B", "source": "panels/panel_B.svg", "mode": "editable",
             "frame": {"x": 92, "y": 0, "w": 88, "h": 58},
             "fit": "contain", "label": {"text": "B"}}
        ],
        "output": {"ai": "figure1.ai",
                   "exports": [
                       {"format": "pdf", "path": "figure1.pdf"},
                       {"format": "png", "path": "figure1_300dpi.png", "dpi": 300},
                       {"format": "svg", "path": "figure1.svg"}]}
    }
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(example, fh, indent=2)
    _emit(ctx, "figure init", {"written": out})



# ---------------------------------------------------------------- helpers (v0.10)
def _json_opt(value, what, expect=list):
    """Parse a JSON-valued CLI option with a typed error."""
    if value is None:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"--{what} is not valid JSON: {exc}")
    if expect and not isinstance(parsed, expect):
        raise ValidationError(f"--{what} must be a JSON {expect.__name__}.")
    return parsed


def _color_or_none(value):
    if value is None:
        return None
    if value.strip().lower() == "none":
        return "none"
    return rgb_triplet(value)


def _fidelity_mod():
    try:
        from cli_anything.illustrator import fidelity
        return fidelity
    except ImportError as exc:
        raise ValidationError(str(exc))


# ---------------------------------------------------------------- path group
@cli.group("path")
def path_grp():
    """Arbitrary Bezier paths (anchors + handles)."""


@path_grp.command("add")
@doc_option
@click.option("--anchors", required=True,
              help='JSON [[x,y],...] canvas coords (top-left origin, y down).')
@click.option("--left-handles", default=None, help="JSON [[x,y]|null,...] absolute.")
@click.option("--right-handles", default=None, help="JSON [[x,y]|null,...] absolute.")
@click.option("--closed", is_flag=True)
@click.option("--fill", default=None, help="'r,g,b' or '#rrggbb'")
@click.option("--stroke", default=None)
@click.option("--stroke-width", type=float, default=None)
@click.option("--item-name", default=None)
@click.option("--layer", default=None)
@click.option("--layer-create", is_flag=True)
@click.option("--artboard", type=int, default=0, show_default=True)
@click.pass_context
def path_add(ctx, doc, anchors, left_handles, right_handles, closed, fill,
             stroke, stroke_width, item_name, layer, layer_create, artboard):
    """Add a Bezier path with explicit anchors and handles."""
    params = {**_doc_params(doc), "artboard": artboard,
              "anchors": _json_opt(anchors, "anchors"),
              "closed": closed}
    if left_handles:
        params["left_handles"] = _json_opt(left_handles, "left-handles")
    if right_handles:
        params["right_handles"] = _json_opt(right_handles, "right-handles")
    if fill:
        params["fill"] = rgb_triplet(fill)
    if stroke:
        params["stroke"] = rgb_triplet(stroke)
    if stroke_width is not None:
        params["stroke_width"] = stroke_width
    if item_name:
        params["name"] = item_name
    if layer:
        params["layer"] = layer
        params["layer_create"] = layer_create
    _run(ctx, "path add", "path_add", params)


@path_grp.command("edit")
@doc_option
@selector_options
@click.option("--points", required=True,
              help='JSON [{"index":i,"anchor":[x,y]?,"left":[x,y]?,'
                   '"right":[x,y]?,"point_type":"smooth"|"corner"?},...]')
@click.option("--set-closed", type=bool, default=None)
@click.option("--artboard", type=int, default=0)
@click.pass_context
def path_edit(ctx, doc, uuid, name, layer, item_type, contains, index, points,
              set_closed, artboard):
    """Edit anchors/handles of one existing path."""
    params = {**_doc_params(doc), "artboard": artboard,
              "selector": build_selector(uuid, name, layer, item_type, contains, index),
              "points": _json_opt(points, "points")}
    if set_closed is not None:
        params["closed"] = set_closed
    _run(ctx, "path edit", "path_edit", params)


@path_grp.command("compound")
@doc_option
@selector_options
@click.option("--item-name", default=None)
@click.pass_context
def path_compound(ctx, doc, uuid, name, layer, item_type, contains, index, item_name):
    """Combine matched paths into a compound path."""
    params = {**_doc_params(doc),
              "selector": build_selector(uuid, name, layer, item_type, contains, index)}
    if item_name:
        params["name"] = item_name
    _run(ctx, "path compound", "compound_make", params)


@path_grp.command("clip")
@doc_option
@selector_options
@click.option("--item-name", default=None)
@click.pass_context
def path_clip(ctx, doc, uuid, name, layer, item_type, contains, index, item_name):
    """Make a clipping mask from matched items (topmost path clips)."""
    params = {**_doc_params(doc),
              "selector": build_selector(uuid, name, layer, item_type, contains, index)}
    if item_name:
        params["name"] = item_name
    _run(ctx, "path clip", "clip_make", params)


# ---------------------------------------------------------------- gradients
@cli.group("gradient")
def gradient_grp():
    """Document gradients: define, apply, list."""


@gradient_grp.command("add")
@doc_option
@click.option("--gradient-name", "gname", required=True)
@click.option("--type", "gtype", type=click.Choice(["linear", "radial"]),
              default="linear", show_default=True)
@click.option("--stops", required=True,
              help='JSON [{"offset":0-100,"color":[r,g,b],"opacity":0-100?,'
                   '"midpoint":0-100?},...] (>=2 stops)')
@click.option("--replace", is_flag=True, help="Redefine if the name exists.")
@click.pass_context
def gradient_add(ctx, doc, gname, gtype, stops, replace):
    """Define a named gradient on the document."""
    _run(ctx, "gradient add", "gradient_add", {
        **_doc_params(doc), "name": gname, "type": gtype,
        "stops": _json_opt(stops, "stops"), "replace": replace})


@gradient_grp.command("apply")
@doc_option
@selector_options
@click.option("--gradient-name", "gname", required=True)
@click.option("--target", type=click.Choice(["fill", "stroke"]), default="fill",
              show_default=True)
@click.option("--angle", type=float, default=0.0, show_default=True,
              help="Degrees, Illustrator CCW convention.")
@click.option("--origin", default=None, help="JSON [x,y] canvas coords.")
@click.option("--length", type=float, default=None)
@click.option("--all", "allow_multiple", is_flag=True)
@click.pass_context
def gradient_apply(ctx, doc, uuid, name, layer, item_type, contains, index,
                   gname, target, angle, origin, length, allow_multiple):
    """Apply a named gradient to matched items."""
    params = {**_doc_params(doc), "gradient": gname, "target": target,
              "angle": angle, "allow_multiple": allow_multiple,
              "selector": build_selector(uuid, name, layer, item_type, contains, index)}
    if origin:
        params["origin"] = _json_opt(origin, "origin")
    if length is not None:
        params["length"] = length
    _run(ctx, "gradient apply", "gradient_apply", params)


@gradient_grp.command("list")
@doc_option
@click.pass_context
def gradient_list(ctx, doc):
    """List document gradients with stops."""
    _run(ctx, "gradient list", "inspect_gradients", _doc_params(doc))


# ---------------------------------------------------------------- style/transform
@cli.group("style")
def style_grp():
    """Fill/stroke styling (caps, joins, dashes, opacity)."""


@style_grp.command("set")
@doc_option
@selector_options
@click.option("--fill", default=None, help="'r,g,b', '#rrggbb' or 'none'")
@click.option("--stroke", default=None, help="'r,g,b', '#rrggbb' or 'none'")
@click.option("--stroke-width", type=float, default=None)
@click.option("--opacity", type=float, default=None)
@click.option("--cap", type=click.Choice(["butt", "round", "projecting"]), default=None)
@click.option("--join", type=click.Choice(["miter", "round", "bevel"]), default=None)
@click.option("--miter-limit", type=float, default=None)
@click.option("--dash", default=None, help='JSON [on,off,...] pt; "[]" = solid')
@click.option("--dash-offset", type=float, default=None)
@click.option("--all", "allow_multiple", is_flag=True)
@click.pass_context
def style_set(ctx, doc, uuid, name, layer, item_type, contains, index, fill,
              stroke, stroke_width, opacity, cap, join, miter_limit, dash,
              dash_offset, allow_multiple):
    """Set stroke/fill style properties on matched items."""
    params = {**_doc_params(doc), "allow_multiple": allow_multiple,
              "selector": build_selector(uuid, name, layer, item_type, contains, index)}
    if fill is not None:
        params["fill"] = _color_or_none(fill)
    if stroke is not None:
        params["stroke"] = _color_or_none(stroke)
    for key, val in (("stroke_width", stroke_width), ("opacity", opacity),
                     ("cap", cap), ("join", join), ("miter_limit", miter_limit),
                     ("dash_offset", dash_offset)):
        if val is not None:
            params[key] = val
    if dash is not None:
        params["dash"] = _json_opt(dash, "dash")
    _run(ctx, "style set", "style_set", params)


@object_grp.command("transform")
@doc_option
@selector_options
@click.option("--scale-x", type=float, default=None, help="Percent.")
@click.option("--scale-y", type=float, default=None, help="Percent.")
@click.option("--rotate", type=float, default=None, help="Degrees CCW.")
@click.option("--dx", type=float, default=None)
@click.option("--dy", type=float, default=None, help="Canvas y-down.")
@click.option("--about", type=click.Choice(["center", "topleft"]), default="center",
              show_default=True)
@click.option("--preserve-strokes", is_flag=True)
@click.option("--all", "allow_multiple", is_flag=True)
@click.pass_context
def object_transform(ctx, doc, uuid, name, layer, item_type, contains, index,
                     scale_x, scale_y, rotate, dx, dy, about, preserve_strokes,
                     allow_multiple):
    """Scale, rotate and translate matched items (in that order)."""
    params = {**_doc_params(doc), "about": about,
              "preserve_strokes": preserve_strokes,
              "allow_multiple": allow_multiple,
              "selector": build_selector(uuid, name, layer, item_type, contains, index)}
    for key, val in (("scale_x", scale_x), ("scale_y", scale_y),
                     ("rotate", rotate), ("dx", dx), ("dy", dy)):
        if val is not None:
            params[key] = val
    _run(ctx, "object transform", "transform_apply", params)


# ---------------------------------------------------------------- inspect group
@cli.group("inspect")
def inspect_grp():
    """Structured document/object inspection (JSON)."""


@inspect_grp.command("document")
@doc_option
@click.pass_context
def inspect_document(ctx, doc):
    """Document summary + full layer tree with item counts."""
    _run(ctx, "inspect document", "inspect_document", _doc_params(doc))


@inspect_grp.command("objects")
@doc_option
@selector_options
@click.option("--limit", type=int, default=200, show_default=True)
@click.pass_context
def inspect_objects(ctx, doc, uuid, name, layer, item_type, contains, index, limit):
    """List matched items (all items when no selector)."""
    _run(ctx, "inspect objects", "items_list", {
        **_doc_params(doc), "limit": limit,
        "selector": build_selector(uuid, name, layer, item_type, contains,
                                   index, required=False)})


@inspect_grp.command("paths")
@doc_option
@selector_options
@click.option("--anchor-limit", type=int, default=1000, show_default=True)
@click.option("--max-paths", type=int, default=100, show_default=True)
@click.pass_context
def inspect_paths(ctx, doc, uuid, name, layer, item_type, contains, index,
                  anchor_limit, max_paths):
    """Deep path geometry: anchors, handles, paint, stroke style."""
    _run(ctx, "inspect paths", "inspect_paths", {
        **_doc_params(doc), "limit": anchor_limit, "max_paths": max_paths,
        "selector": build_selector(uuid, name, layer, item_type, contains,
                                   index, required=False)})


@inspect_grp.command("text")
@doc_option
@selector_options
@click.option("--limit", type=int, default=200, show_default=True)
@click.pass_context
def inspect_text(ctx, doc, uuid, name, layer, item_type, contains, index, limit):
    """Deep text attributes: font, size, tracking, leading, justification."""
    _run(ctx, "inspect text", "inspect_text", {
        **_doc_params(doc), "limit": limit,
        "selector": build_selector(uuid, name, layer, item_type, contains,
                                   index, required=False)})


@inspect_grp.command("gradients")
@doc_option
@click.pass_context
def inspect_gradients(ctx, doc):
    """Gradient inventory with stops."""
    _run(ctx, "inspect gradients", "inspect_gradients", _doc_params(doc))


@inspect_grp.command("colors")
@doc_option
@click.pass_context
def inspect_colors(ctx, doc):
    """Unique paints used across paths and text."""
    _run(ctx, "inspect colors", "inspect_colors", _doc_params(doc))


@inspect_grp.command("editability")
@doc_option
@click.pass_context
def inspect_editability(ctx, doc):
    """Structural editability report (PASS/WARN/FAIL) for the document."""
    fid = _fidelity_mod()
    report = _backend(ctx).run_op("doc_report", _doc_params(doc),
                                  timeout=ctx.obj["timeout"])
    _emit(ctx, "inspect editability",
          {"editability": fid.score_editability(report), "document_report": report})


# ---------------------------------------------------------------- reference group
@cli.group("reference")
def reference_grp():
    """Reference-figure analysis, rendering and comparison."""


@reference_grp.command("analyze")
@click.argument("src", type=click.Path(exists=True))
@click.pass_context
def reference_analyze(ctx, src):
    """Preflight: what can be preserved/recovered from a reference figure."""
    fid = _fidelity_mod()
    _emit(ctx, "reference analyze", fid.analyze_reference(src))


@reference_grp.command("render")
@click.argument("src", type=click.Path(exists=True))
@click.argument("out_png")
@click.option("--dpi", type=float, default=300.0, show_default=True)
@click.option("--page", type=int, default=0, show_default=True)
@click.option("--overwrite", is_flag=True)
@click.pass_context
def reference_render(ctx, src, out_png, dpi, page, overwrite):
    """Rasterise a reference (PDF/AI/SVG/raster) to PNG for comparison."""
    fid = _fidelity_mod()
    out = prepare_output_path(out_png, overwrite)
    _emit(ctx, "reference render", fid.render_reference(src, dpi, out, page=page))


@reference_grp.command("compare")
@click.argument("reference", type=click.Path(exists=True))
@click.argument("candidate", type=click.Path(exists=True))
@click.option("--dpi", type=float, default=300.0, show_default=True,
              help="Render dpi for vector references; also scales bbox_pt.")
@click.option("--tile", type=int, default=64, show_default=True)
@click.option("--objects-json", type=click.Path(exists=True), default=None,
              help="items_list JSON to map difference regions to objects.")
@click.option("--heatmap", default=None, help="Heatmap PNG path.")
@click.option("--overlay", default=None, help="Overlay PNG path.")
@click.pass_context
def reference_compare(ctx, reference, candidate, dpi, tile, objects_json,
                      heatmap, overlay):
    """Compare a rendered candidate PNG against a reference figure.

    REFERENCE may be PDF/AI/SVG (rendered at --dpi) or an image;
    CANDIDATE must be a rendered PNG of the Illustrator artwork
    (`export png --dpi` at the same dpi).
    """
    fid = _fidelity_mod()
    ref_png = reference
    if not reference.lower().endswith((".png", ".jpg", ".jpeg", ".tif", ".tiff")):
        ref_png = os.path.splitext(candidate)[0] + ".reference.png"
        fid.render_reference(reference, dpi, ref_png)
    result = fid.compare_images(ref_png, candidate, tile=tile, dpi=dpi,
                                heatmap_png=heatmap, overlay_png=overlay)
    if objects_json:
        with open(objects_json, "r", encoding="utf-8") as fh:
            objs = json.load(fh)
        result["region_objects"] = fid.map_regions_to_objects(
            result["largest_differences"], objs, dpi=dpi)
    _emit(ctx, "reference compare", result)



@figure_grp.command("reconstruct")
@click.option("--reference", "reference_path", required=True,
              type=click.Path(exists=True),
              help="Reference figure: PDF/AI/SVG/EPS or PNG/JPEG/TIFF.")
@click.option("--mode", type=click.Choice(["auto", "preserve", "fidelity",
                                           "recreate", "redesign"]),
              default="auto", show_default=True,
              help="auto follows the preflight recommendation.")
@click.option("--output", "output_ai", required=True, help="Output .ai master.")
@click.option("--dpi", type=float, default=300.0, show_default=True)
@click.option("--no-compare", is_flag=True,
              help="Skip the render+compare postflight.")
@click.option("--trace", is_flag=True,
              help="Raster references: deterministic Image Trace (live only).")
@click.option("--overwrite", is_flag=True)
@click.pass_context
def figure_reconstruct(ctx, reference_path, mode, output_ai, dpi, no_compare,
                       trace, overwrite):
    """Reconstruct a reference figure as an editable .ai master.

    Preserves native vectors/text when the reference contains them (the
    document is opened by Illustrator, not redrawn); raster references are
    placed as a locked template layer (optionally vector-traced). Writes a
    manifest with preflight, editability and visual-fidelity results.
    """
    from cli_anything.illustrator.ops import reconstruct as recon_ops
    manifest = recon_ops.reconstruct(
        _backend(ctx), reference_path, mode, output_ai, dpi=dpi,
        overwrite=overwrite, compare_enabled=not no_compare, trace=trace,
        timeout=ctx.obj["timeout"])
    _emit(ctx, "figure reconstruct", manifest)


# upstream-compatible alias: `project` == `doc`
cli.add_command(doc_grp, name="project")


def main():
    try:
        cli(standalone_mode=False)
    except click.exceptions.Abort:
        sys.exit(130)
    except click.ClickException as exc:
        sys.stderr.write(f"usage error: {exc.format_message()}\n")
        print(json.dumps({"ok": False,
                          "error": {"code": "USAGE", "message": exc.format_message()}}))
        sys.exit(EXIT_USAGE)
    except CAIError as exc:
        print(json.dumps({"ok": False, "error": exc.to_json()},
                         indent=2, ensure_ascii=False, default=str))
        sys.stderr.write(f"[{exc.code}] {exc}\n")
        sys.exit(exc.exit_code)


if __name__ == "__main__":
    main()
