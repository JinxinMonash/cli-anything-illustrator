"""Reference-figure reconstruction orchestrator.

Implements the reconstruction priority hierarchy:
  P1 preserve native vectors/text  (Illustrator opens PDF/SVG/EPS/AI directly)
  P2 recover geometry from vector containers (same route; Illustrator parses)
  P3 deterministic vector trace of raster references (live Illustrator only)
  P4/P5 manual/semantic reconstruction -- agent-driven on a prepared canvas.

Modes
  preserve  vector-native sources; open natively, keep everything, minimal touch
  fidelity  match the reference as closely as possible; preservation first,
            reconstruction only where impossible; compare loop drives fixes
  recreate  editable figure with approximately the same structure
  redesign  reference used as inspiration; layout/style changes allowed

The orchestrator never guesses silently: every unrecoverable element and every
substitution lands in the manifest (`<output>.reconstruct.json`).
"""
from __future__ import annotations

import datetime
import json
import os

from cli_anything.illustrator.errors import ValidationError
from cli_anything.illustrator.ops.common import prepare_output_path

MODES = ("auto", "preserve", "fidelity", "recreate", "redesign")
VECTOR_FORMATS = {"pdf", "ai", "svg", "eps"}
REFERENCE_LAYER = "Reference (template)"


def _fidelity():
    from cli_anything.illustrator import fidelity
    return fidelity


def reconstruct(backend, reference: str, mode: str, output_ai: str,
                dpi: float = 300.0, overwrite: bool = False,
                compare_enabled: bool = True, trace: bool = False,
                timeout: float = 300.0) -> dict:
    if mode not in MODES:
        raise ValidationError(f"Unknown mode: {mode} (use {'/'.join(MODES)})")
    reference = os.path.abspath(os.path.expanduser(reference))
    if not os.path.isfile(reference):
        raise ValidationError(f"Reference not found: {reference}")
    out_path = prepare_output_path(output_ai, overwrite)
    if not out_path.lower().endswith(".ai"):
        raise ValidationError("Output must be a .ai master (delivery copies "
                              "come from `export` afterwards).")
    fid = _fidelity()

    manifest = {
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "reference": reference,
        "requested_mode": mode,
        "output_ai": out_path,
        "warnings": [],
        "unrecoverable": [],
    }

    # ---- preflight -------------------------------------------------------
    analysis = fid.analyze_reference(reference)
    manifest["preflight"] = analysis
    plan = analysis["recovery_plan"]
    if mode == "auto":
        mode = plan["recommended_mode"]
    manifest["mode"] = mode
    manifest["warnings"].extend(plan.get("warnings", []))

    fmt = analysis["format"]
    vector_native = plan["classes"]["vector_native"]["present"] and \
        plan["primary_class"] == "vector_native"

    # ---- route -----------------------------------------------------------
    if mode in ("preserve", "fidelity") and vector_native:
        route = "native_open"       # P1/P2: Illustrator parses the source
    elif mode in ("preserve",) and not vector_native:
        raise ValidationError(
            "preserve mode needs recoverable vector content; this reference "
            f"is {plan['primary_class']} — use --mode fidelity (trace route) "
            "or recreate.")
    elif mode == "fidelity":
        route = "raster_template"   # P3: template layer + optional trace
    else:
        route = "canvas_prep"       # recreate/redesign: agent builds on top
    manifest["route"] = route

    # ---- build the document ---------------------------------------------
    if route == "native_open":
        opened = backend.run_op("doc_open", {"path": reference}, timeout)
        doc_name = opened["name"]
        manifest["opened"] = opened
        if fmt == "pdf" and analysis.get("page_count", 1) > 1:
            manifest["warnings"].append(
                f"Reference has {analysis['page_count']} pages; page 1 opened.")
    else:
        w = analysis.get("width_pt") or 595.0
        h = analysis.get("height_pt") or 842.0
        if not analysis.get("width_pt"):
            manifest["warnings"].append(
                "Reference dimensions unknown; A4 canvas used.")
        newdoc = backend.run_op("doc_new", {"width": w, "height": h,
                                            "color_mode": "RGB"}, timeout)
        doc_name = newdoc["name"]
        placed = backend.run_op("import_file", {
            "doc": doc_name, "source": reference, "mode": "linked",
            "layer": REFERENCE_LAYER, "layer_create": True,
            "x": 0, "y": 0, "name": "reference_template",
        }, timeout)
        manifest["reference_template"] = placed
        backend.run_op("layer_set", {"doc": doc_name, "name": REFERENCE_LAYER,
                                     "updates": {"locked": True}}, timeout)
        if route == "raster_template":
            if trace:
                traced = backend.run_op("trace", {
                    "doc": doc_name,
                    "selector": {"name": "reference_template"},
                }, timeout)
                manifest["trace"] = traced
                manifest["warnings"].append(
                    "Raster reference vector-traced (deterministic Image "
                    "Trace); geometry is the traced observation, colours "
                    "sampled by Illustrator.")
            else:
                manifest["warnings"].append(
                    "Raster reference placed as a locked template layer; run "
                    "with --trace for deterministic vectorisation, or "
                    "reconstruct manually on layers above it.")
            manifest["unrecoverable"].append(
                "Raster source: original vector geometry and live text are "
                "not present in the file; only observed geometry can be "
                "recovered.")
        else:
            manifest["warnings"].append(
                f"{mode} mode: reference placed as locked template; build "
                "the new artwork on layers above it, then delete the "
                "template layer before delivery.")

    # ---- save master -----------------------------------------------------
    saved = backend.run_op("doc_saveas", {
        "doc": doc_name, "path": out_path, "overwrite": True,
    }, timeout)
    manifest["saved"] = saved
    doc_name = saved.get("name", os.path.basename(out_path))

    # ---- postflight: report + editability -------------------------------
    report = backend.run_op("doc_report", {"doc": doc_name}, timeout)
    manifest["document_report"] = report
    manifest["editability"] = fid.score_editability(report)
    for f in report.get("fonts_unavailable") or []:
        manifest["unrecoverable"].append(
            f"Font not available on this machine: {f} (Illustrator will "
            "substitute on screen; install the font or restyle).")

    # ---- postflight: visual comparison ----------------------------------
    manifest["compare"] = None
    if compare_enabled and fmt != "eps":
        base = os.path.splitext(out_path)[0]
        ref_png = base + ".reference.png"
        out_png = base + ".render.png"
        try:
            fid.render_reference(reference, dpi, ref_png)
            backend.run_op("export_png", {"doc": doc_name, "path": out_png,
                                          "dpi": dpi, "overwrite": True,
                                          "artboard": 0}, timeout)
            cmp_res = fid.compare_images(ref_png, out_png, dpi=dpi,
                                         heatmap_png=base + ".heatmap.png",
                                         overlay_png=base + ".overlay.png")
            objs = backend.run_op("items_list", {"doc": doc_name,
                                                 "selector": {}}, timeout)
            cmp_res["region_objects"] = fid.map_regions_to_objects(
                cmp_res["largest_differences"], objs, dpi=dpi)
            manifest["compare"] = cmp_res
        except Exception as exc:  # noqa: BLE001 -- comparison is advisory
            manifest["warnings"].append(
                f"Visual comparison unavailable: {exc}")
    elif fmt == "eps":
        manifest["warnings"].append(
            "EPS references cannot be rendered for comparison without "
            "Illustrator/Ghostscript; compare skipped.")

    mpath = out_path + ".reconstruct.json"
    with open(mpath, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False, default=str)
    manifest["manifest_path"] = mpath
    return manifest
