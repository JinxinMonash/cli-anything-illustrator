"""Multi-panel figure assembly from a declarative JSON specification.

Design rules (scientific integrity):
- The whole spec is validated BEFORE any document is touched.
- Panels are imported as EDITABLE vector groups by default; linked placement
  must be requested explicitly and is reported as non-editable.
- Aspect ratios are always preserved ("contain" fit); panels are scaled,
  never stretched. Panel content is never redrawn or altered.
- Every run emits a manifest (source -> panel mapping, scale factors,
  warnings) and the assembly can be re-verified with `figure verify`.
- Repeated execution policy: `figure assemble` always builds a NEW document;
  it refuses to overwrite outputs unless --overwrite is passed (documented
  create-only policy; there is no in-place update).
"""
from __future__ import annotations

import datetime
import json
import os

from cli_anything.illustrator.errors import ValidationError
from cli_anything.illustrator.ops.common import prepare_output_path, to_pt

PANEL_LAYER = "Panels"
LABEL_LAYER = "Labels"

_DEF_LABEL = {"font": "Helvetica", "size_pt": 12.0, "color": [0, 0, 0],
              "offset": [2.0, 2.0]}
_ALLOWED_EXPORT = {"png", "svg", "pdf"}


def load_spec(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        try:
            return json.load(fh)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"Spec is not valid JSON: {exc}") from exc


def validate_spec(spec: dict, spec_dir: str) -> list[str]:
    """Return a list of validation errors (empty = valid). No mutation."""
    errs: list[str] = []

    def need(cond, msg):
        if not cond:
            errs.append(msg)

    need(isinstance(spec, dict), "Spec root must be a JSON object.")
    if not isinstance(spec, dict):
        return errs
    need(spec.get("version") == 1, "spec.version must be 1.")

    canvas = spec.get("canvas")
    need(isinstance(canvas, dict), "spec.canvas is required.")
    units = "mm"
    cw = ch = None
    if isinstance(canvas, dict):
        units = canvas.get("units", "mm")
        need(units in ("mm", "pt"), "canvas.units must be 'mm' or 'pt'.")
        cw, ch = canvas.get("width"), canvas.get("height")
        need(isinstance(cw, (int, float)) and cw > 0, "canvas.width must be > 0.")
        need(isinstance(ch, (int, float)) and ch > 0, "canvas.height must be > 0.")
        need(canvas.get("color_mode", "RGB") in ("RGB", "CMYK"),
             "canvas.color_mode must be RGB or CMYK.")

    panels = spec.get("panels")
    need(isinstance(panels, list) and len(panels) > 0,
         "spec.panels must be a non-empty list.")
    ids = set()
    if isinstance(panels, list):
        for i, p in enumerate(panels):
            tag = f"panels[{i}]"
            if not isinstance(p, dict):
                errs.append(f"{tag} must be an object.")
                continue
            pid = p.get("id")
            need(isinstance(pid, str) and pid, f"{tag}.id (string) is required.")
            if pid in ids:
                errs.append(f"{tag}.id duplicated: {pid}")
            ids.add(pid)
            src = p.get("source")
            need(isinstance(src, str) and src, f"{tag}.source is required.")
            if isinstance(src, str) and src:
                sp = src if os.path.isabs(src) else os.path.join(spec_dir, src)
                need(os.path.isfile(sp), f"{tag}.source not found: {sp}")
                ext = os.path.splitext(sp)[1].lower()
                need(ext in (".svg", ".ai", ".pdf", ".eps"),
                     f"{tag}.source must be .svg/.ai/.pdf/.eps (got {ext}).")
            need(p.get("mode", "editable") in ("editable", "linked"),
                 f"{tag}.mode must be 'editable' or 'linked'.")
            fr = p.get("frame")
            need(isinstance(fr, dict), f"{tag}.frame ({{x,y,w,h}}) is required.")
            if isinstance(fr, dict):
                for k in ("x", "y", "w", "h"):
                    need(isinstance(fr.get(k), (int, float)),
                         f"{tag}.frame.{k} must be a number.")
                if all(isinstance(fr.get(k), (int, float)) for k in ("x", "y", "w", "h")):
                    need(fr["w"] > 0 and fr["h"] > 0, f"{tag}.frame w/h must be > 0.")
                    if isinstance(cw, (int, float)) and isinstance(ch, (int, float)):
                        if fr["x"] < 0 or fr["y"] < 0 or fr["x"] + fr["w"] > cw + 1e-6 \
                           or fr["y"] + fr["h"] > ch + 1e-6:
                            errs.append(f"{tag}.frame exceeds the canvas bounds.")
            need(p.get("fit", "contain") == "contain",
                 f"{tag}.fit only supports 'contain' (aspect ratio is always preserved).")
            lab = p.get("label")
            if lab is not None:
                need(isinstance(lab, dict) and isinstance(lab.get("text"), str),
                     f"{tag}.label.text (string) is required when label is present.")

    out = spec.get("output")
    need(isinstance(out, dict), "spec.output is required.")
    if isinstance(out, dict):
        need(isinstance(out.get("ai"), str) and out.get("ai"),
             "output.ai (master .ai path) is required.")
        if isinstance(out.get("ai"), str):
            need(out["ai"].lower().endswith(".ai"), "output.ai must end in .ai")
        for j, ex in enumerate(out.get("exports", []) or []):
            if not isinstance(ex, dict):
                errs.append(f"output.exports[{j}] must be an object.")
                continue
            need(ex.get("format") in _ALLOWED_EXPORT,
                 f"output.exports[{j}].format must be one of {sorted(_ALLOWED_EXPORT)}.")
            need(isinstance(ex.get("path"), str) and ex.get("path"),
                 f"output.exports[{j}].path is required.")
    return errs


def _label_style(spec: dict, panel: dict) -> dict:
    style = dict(_DEF_LABEL)
    style.update((spec.get("defaults") or {}).get("label") or {})
    style.update({k: v for k, v in (panel.get("label") or {}).items()
                  if k != "text"})
    return style


def assemble(backend, spec: dict, spec_dir: str, overwrite: bool = False,
             timeout: float = 180.0, allow_font_substitute: bool = False) -> dict:
    """Execute a validated spec. Returns the manifest dict."""
    errs = validate_spec(spec, spec_dir)
    if errs:
        raise ValidationError("Spec validation failed:\n  - " + "\n  - ".join(errs),
                              details={"errors": errs})

    canvas = spec["canvas"]
    units = canvas.get("units", "mm")
    u = lambda v: to_pt(v, units)

    # resolve outputs FIRST so overwrite refusals happen before any mutation
    out = spec["output"]
    ai_path = prepare_output_path(
        out["ai"] if os.path.isabs(out["ai"]) else os.path.join(spec_dir, out["ai"]),
        overwrite)
    export_jobs = []
    for ex in out.get("exports", []) or []:
        p = ex["path"] if os.path.isabs(ex["path"]) else os.path.join(spec_dir, ex["path"])
        export_jobs.append({"format": ex["format"],
                            "path": prepare_output_path(p, overwrite),
                            "dpi": ex.get("dpi", 300),
                            "editable": ex.get("editable", True)})

    manifest = {
        "tool": "cli-anything-illustrator figure assemble",
        "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "spec": spec, "panels": [], "outputs": [], "warnings": [],
        "completed": False, "partial": False,
    }

    doc_info = backend.run_op("doc_new", {
        "width": u(canvas["width"]), "height": u(canvas["height"]),
        "color_mode": canvas.get("color_mode", "RGB"),
        "base_layer_name": PANEL_LAYER,
    }, timeout)
    doc_name = doc_info["name"]
    manifest["document"] = doc_name

    try:
        for panel in spec["panels"]:
            pid = panel["id"]
            src = panel["source"]
            src_abs = src if os.path.isabs(src) else os.path.join(spec_dir, src)
            fr = panel["frame"]
            fx, fy, fw, fh = u(fr["x"]), u(fr["y"]), u(fr["w"]), u(fr["h"])
            group_name = f"panel_{pid}"

            imp = backend.run_op("import_file", {
                "doc": doc_name, "source": os.path.abspath(src_abs),
                "mode": panel.get("mode", "editable"),
                "layer": PANEL_LAYER, "name": group_name,
                "x": fx, "y": fy, "artboard": 0,
            }, timeout)
            entry = {"id": pid, "source": src_abs, "group": group_name,
                     "uuid": imp.get("uuid"), "mode": panel.get("mode", "editable"),
                     "editable": imp.get("editable"),
                     "warnings": imp.get("warnings", []),
                     "source_fonts": imp.get("source_fonts", [])}
            manifest["warnings"].extend(
                [f"panel {pid}: {w}" for w in imp.get("warnings", [])])

            b = imp["bounds"]
            scale_pct = 100.0
            if b and b["w"] > 0 and b["h"] > 0:
                scale_pct = min(fw / b["w"], fh / b["h"]) * 100.0
            sel = ({"uuid": imp["uuid"]} if imp.get("uuid")
                   else {"name": group_name, "layer": PANEL_LAYER})
            if abs(scale_pct - 100.0) > 0.01:
                upd = backend.run_op("item_update", {
                    "doc": doc_name, "selector": sel,
                    "updates": {"scale_percent": scale_pct},
                }, timeout)
                b = upd["items"][0]["after"]["bounds"]
            # position top-left at frame origin after scaling
            upd = backend.run_op("item_update", {
                "doc": doc_name, "selector": sel,
                "updates": {"x": fx, "y": fy},
            }, timeout)
            entry["scale_percent"] = round(scale_pct, 3)
            entry["final_bounds_pt"] = upd["items"][0]["after"]["bounds"]

            lab = panel.get("label")
            if lab:
                style = _label_style(spec, panel)
                off = style.get("offset", [2.0, 2.0])
                txt = backend.run_op("text_add", {
                    "doc": doc_name, "contents": lab["text"],
                    "x": fx + u(off[0]), "y": fy + u(off[1]) + style.get("size_pt", 12.0),
                    "size": style.get("size_pt", 12.0),
                    "font": style.get("font"),
                    "allow_font_substitute": allow_font_substitute,
                    "color": style.get("color", [0, 0, 0]),
                    "layer": LABEL_LAYER, "layer_create": True,
                    "name": f"label_{pid}", "kind": "point",
                }, timeout)
                entry["label"] = {"text": lab["text"], "name": f"label_{pid}",
                                  "font": txt.get("font"),
                                  "substituted": txt.get("font_substituted", False)}
                if txt.get("font_substituted"):
                    manifest["warnings"].append(
                        f"panel {pid}: label font substituted "
                        f"({style.get('font')} unavailable).")
            manifest["panels"].append(entry)

        saved = backend.run_op("doc_saveas", {"doc": doc_name, "path": ai_path},
                               timeout)
        doc_name = saved["name"]  # name changes to the saved filename
        manifest["outputs"].append({"format": "AI", "path": ai_path,
                                    "size_bytes": os.path.getsize(ai_path)
                                    if os.path.exists(ai_path) else None})

        for job in export_jobs:
            op = {"png": "export_png", "svg": "export_svg", "pdf": "export_pdf"}[job["format"]]
            params = {"doc": doc_name, "path": job["path"]}
            if job["format"] == "png":
                params["dpi"] = job["dpi"]
            if job["format"] == "pdf":
                params["editable"] = job["editable"]
            res = backend.run_op(op, params, timeout)
            manifest["outputs"].append({
                "format": job["format"].upper(), "path": job["path"],
                "size_bytes": os.path.getsize(job["path"])
                if os.path.exists(job["path"]) else None,
                "detail": {k: v for k, v in res.items() if k != "path"}})

        manifest["completed"] = True
    except Exception:
        manifest["partial"] = len(manifest["panels"]) > 0
        manifest["completed"] = False
        _write_manifest(manifest, ai_path)
        raise
    finally:
        manifest["finished_utc"] = datetime.datetime.now(
            datetime.timezone.utc).isoformat()

    _write_manifest(manifest, ai_path)
    return manifest


def _write_manifest(manifest: dict, ai_path: str):
    mpath = ai_path + ".manifest.json"
    with open(mpath, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)
    manifest["manifest_path"] = mpath


def verify(backend, spec: dict, spec_dir: str, timeout: float = 180.0) -> dict:
    """Reopen the saved master and check the assembly against the spec."""
    errs = validate_spec(spec, spec_dir)
    if errs:
        raise ValidationError("Spec validation failed:\n  - " + "\n  - ".join(errs),
                              details={"errors": errs})
    out = spec["output"]
    ai_path = out["ai"] if os.path.isabs(out["ai"]) else os.path.join(spec_dir, out["ai"])
    ai_path = os.path.abspath(ai_path)
    checks = []

    def add(name, passed, detail):
        checks.append({"check": name, "pass": bool(passed), "detail": detail})

    add("master_exists", os.path.isfile(ai_path), ai_path)
    if not os.path.isfile(ai_path):
        return {"ok": False, "checks": checks}

    opened = backend.run_op("doc_open", {"path": ai_path}, timeout)
    doc_name = opened["name"]
    add("master_reopens", True,
        f"{doc_name}: {opened['page_items']} items, {opened['text_frames']} text frames")

    report = backend.run_op("doc_report", {"doc": doc_name}, timeout)
    add("no_missing_links", not any(l["missing"] for l in report["placed_links"]),
        report["placed_links"] or "no placed items")
    add("fonts_available", not report["fonts_unavailable"],
        report["fonts_unavailable"] or "all document fonts available")

    for panel in spec["panels"]:
        pid = panel["id"]
        group_name = f"panel_{pid}"
        res = backend.run_op("items_list", {
            "doc": doc_name,
            "selector": {"name": group_name, "type": "group"},
        }, timeout)
        n = res["total_matches"]
        add(f"panel_{pid}_group_present", n == 1,
            f"{n} group(s) named {group_name}")
        if panel.get("mode", "editable") == "editable" and n == 1:
            g = res["items"][0]
            add(f"panel_{pid}_is_vector_group", g["type"] == "group", g["type"])
        lab = panel.get("label")
        if lab:
            lres = backend.run_op("items_list", {
                "doc": doc_name,
                "selector": {"name": f"label_{pid}", "type": "text"},
            }, timeout)
            okl = (lres["total_matches"] == 1 and
                   lres["items"][0].get("contents", "").startswith(lab["text"]))
            add(f"panel_{pid}_label", okl,
                lres["items"][0].get("contents") if lres["total_matches"] else "missing")

    # editable-text check: master must retain live text frames when labels exist
    if any(p.get("label") for p in spec["panels"]):
        add("live_text_in_master", report["text_frames"] > 0,
            f"{report['text_frames']} text frames")

    for ex in out.get("exports", []) or []:
        p = ex["path"] if os.path.isabs(ex["path"]) else os.path.join(spec_dir, ex["path"])
        add(f"export_{ex['format']}_exists", os.path.isfile(p), os.path.abspath(p))

    backend.run_op("doc_close", {"doc": doc_name, "mode": "discard"}, timeout)
    ok = all(c["pass"] for c in checks)
    return {"ok": ok, "checks": checks, "master": ai_path,
            "document_report": report}
