"""Reference preflight analysis.

``analyze_reference(path)`` inspects a reference figure file (PDF, AI,
SVG, EPS, PNG, JPEG, TIFF) WITHOUT Illustrator and returns a
machine-readable preflight report including a ``recovery_plan`` that
classifies the content (vector_native / text_live / raster_only) and
recommends a reconstruction mode ("preserve" for vector-native input,
"fidelity" with an image-trace route for raster input).

Dependencies (lazy): pymupdf (PDF/AI), pillow (raster).  SVG and EPS
analysis is stdlib-only (xml.etree / DSC header parsing).
"""

import os
import re
import xml.etree.ElementTree as ET

from cli_anything.illustrator.fidelity import require

VECTOR_NATIVE_EXTS = (".pdf", ".ai", ".svg", ".eps")
RASTER_EXTS = (".png", ".jpg", ".jpeg", ".tif", ".tiff")

# SVG unit -> points (1 px = 1/96 in = 0.75 pt; unitless = user units = px).
_PT_PER_UNIT = {
    "": 0.75, "px": 0.75, "pt": 1.0, "pc": 12.0,
    "in": 72.0, "mm": 72.0 / 25.4, "cm": 72.0 / 2.54,
}

_SVG_COUNTED = (
    "path", "rect", "circle", "ellipse", "line", "polygon", "polyline",
    "text", "image", "linearGradient", "radialGradient", "clipPath",
)

LOW_RES_DPI = 150.0


def analyze_reference(path):
    """Preflight-analyze a reference file.

    Parameters:
        path (str): file path; format chosen by extension
            (.pdf/.ai via PyMuPDF, .svg via xml.etree, .eps header-only,
            .png/.jpg/.jpeg/.tif/.tiff via Pillow).

    Returns:
        dict with keys:
            format (str): "pdf" | "ai" | "svg" | "eps" | "raster"
            path (str)
            width_pt, height_pt (float|None): page/canvas size in points
                (first page for multi-page PDF)
            page_count (int): 1 for non-PDF
            pages (list[dict], PDF/AI only): per-page
                {index, width_pt, height_pt,
                 vector: {drawings, fills, strokes, gradients},
                 text_spans: [{text, font, size, bbox [pt], color "#rrggbb"}],
                 fonts: [{name, type, embedded}],
                 images: [{xref, width_px, height_px, has_alpha,
                           dpi_estimate}]}
            elements (dict, SVG only): element tag -> count
            colors (list[str], SVG only): inline colour inventory
            viewbox (list[float]|None, SVG only)
            text_spans (list[dict], SVG only): {text, font, size}
            raster (dict, raster only): {width_px, height_px, mode,
                dpi (tuple|None), has_alpha, channel_means,
                approx_unique_colors}
            bounding_box (list[float]|None, EPS only)
            creator (str|None, EPS only)
            fonts (list): PDF/AI: [{name, type, embedded}];
                SVG: [str]; EPS: [{name}]; raster: []
            totals (dict): {vector_drawings, fills, strokes, gradients,
                text_spans, images} (None where not measurable)
            transparency (bool)
            warnings (list[str])
            recovery_plan (dict): see _recovery_plan()

    Raises:
        FileNotFoundError: path does not exist.
        ValueError: unsupported extension.
        ImportError: missing optional dependency (message names
            ``pip install "cli-anything-illustrator[fidelity]"``).
    """
    if not os.path.isfile(path):
        raise FileNotFoundError("reference file not found: %s" % path)
    ext = os.path.splitext(path)[1].lower()
    if ext in (".pdf", ".ai"):
        return _analyze_pdf(path, "ai" if ext == ".ai" else "pdf")
    if ext == ".svg":
        return _analyze_svg(path)
    if ext == ".eps":
        return _analyze_eps(path)
    if ext in RASTER_EXTS:
        return _analyze_raster(path)
    raise ValueError(
        "unsupported reference format %r (supported: %s)"
        % (ext, ", ".join(VECTOR_NATIVE_EXTS + RASTER_EXTS))
    )


def _recovery_plan(fmt, vector_native, live_text_count, vector_count,
                   raster_count, text_warnings, raster_warnings):
    """Build the recovery-plan block.

    Returns dict:
        classes (dict):
            vector_native: {present (bool), detail (str)}
            text_live:     {present (bool), count (int), warnings [str]}
            raster_only:   {present (bool), count (int), warnings [str]}
        primary_class (str): "vector_native" | "raster_only"
        recommended_mode (str): "preserve" | "fidelity"
        trace_route (str|None): "image_trace" when recommended_mode is
            "fidelity", else None
        warnings (list[str]): union of per-class warnings
    """
    effectively_raster = (
        raster_count and raster_count > 0
        and not vector_count and not live_text_count
    )
    raster_only_present = (not vector_native) or bool(effectively_raster)
    raster_warnings = list(raster_warnings)
    if vector_native and effectively_raster:
        raster_warnings.append(
            "vector container holds only raster content (scan-style %s); "
            "opening it in Illustrator yields no editable vectors" % fmt)
    classes = {
        "vector_native": {
            "present": bool(vector_native),
            "detail": (
                "%s opens natively in Illustrator" % fmt
                if vector_native else
                "raster format; no native vector content"
            ),
        },
        "text_live": {
            "present": bool(live_text_count),
            "count": int(live_text_count or 0),
            "warnings": list(text_warnings),
        },
        "raster_only": {
            "present": bool(raster_only_present),
            "count": int(raster_count or 0),
            "warnings": raster_warnings,
        },
    }
    if vector_native and not effectively_raster:
        primary, mode, trace = "vector_native", "preserve", None
    else:
        primary, mode, trace = "raster_only", "fidelity", "image_trace"
    return {
        "classes": classes,
        "primary_class": primary,
        "recommended_mode": mode,
        "trace_route": trace,
        "warnings": list(text_warnings) + raster_warnings,
    }


# ---------------------------------------------------------------- PDF / AI

def _analyze_pdf(path, fmt):
    fitz = require("fitz")  # pymupdf
    doc = fitz.open(path)
    try:
        pages = []
        fonts_doc = {}
        transparency = False
        totals = {"vector_drawings": 0, "fills": 0, "strokes": 0,
                  "gradients": 0, "text_spans": 0, "images": 0}
        warnings = []
        for pno in range(doc.page_count):
            page = doc[pno]
            drawings = page.get_drawings()
            n_fill = 0
            n_stroke = 0
            for d in drawings:
                t = d.get("type") or ""
                if "f" in t:
                    n_fill += 1
                if "s" in t:
                    n_stroke += 1
                fo = d.get("fill_opacity")
                so = d.get("stroke_opacity")
                if (fo is not None and fo < 1.0) or \
                   (so is not None and so < 1.0):
                    transparency = True
            gradients = 0
            try:
                contents = page.read_contents() or b""
                # PDF gradients are shading dicts painted with `sh`
                # (detectable where used as an operator); pattern-fill
                # colour spaces are counted with them.
                gradients = len(
                    re.findall(rb"/[^\s/<>\[\]()]+\s+sh(?![a-zA-Z])",
                               contents))
                gradients += len(re.findall(rb"/Pattern\s+(?:cs|CS)",
                                            contents))
            except Exception:
                pass

            spans = []
            for block in page.get_text("dict").get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    for sp in line.get("spans", []):
                        txt = sp.get("text", "")
                        if not txt.strip():
                            continue
                        spans.append({
                            "text": txt,
                            "font": sp.get("font"),
                            "size": round(float(sp.get("size", 0.0)), 2),
                            "bbox": [round(float(v), 2)
                                     for v in sp.get("bbox", (0, 0, 0, 0))],
                            "color": "#%06x"
                                     % (int(sp.get("color", 0)) & 0xFFFFFF),
                        })

            fonts = []
            for f in page.get_fonts(full=False):
                fext, ftype, basefont = str(f[1]), str(f[2]), str(f[3])
                embedded = bool(fext) and fext not in ("n/a", "")
                fonts.append({"name": basefont, "type": ftype,
                              "embedded": embedded})
                prev = fonts_doc.get(basefont)
                fonts_doc[basefont] = {
                    "name": basefont, "type": ftype,
                    "embedded": embedded or bool(prev and prev["embedded"]),
                }

            images = []
            for img in page.get_images(full=True):
                xref, smask, w, h = img[0], img[1], img[2], img[3]
                if smask:
                    transparency = True
                dpi_est = None
                try:
                    rects = page.get_image_rects(xref)
                    if rects and rects[0].width > 0:
                        dpi_est = round(w / (rects[0].width / 72.0), 1)
                except Exception:
                    pass
                images.append({"xref": int(xref), "width_px": int(w),
                               "height_px": int(h),
                               "has_alpha": bool(smask),
                               "dpi_estimate": dpi_est})
                if dpi_est is not None and dpi_est < LOW_RES_DPI:
                    warnings.append(
                        "page %d: embedded raster at ~%.0f dpi is below "
                        "%.0f dpi (low resolution)"
                        % (pno, dpi_est, LOW_RES_DPI))

            pages.append({
                "index": pno,
                "width_pt": round(float(page.rect.width), 2),
                "height_pt": round(float(page.rect.height), 2),
                "vector": {"drawings": len(drawings), "fills": n_fill,
                           "strokes": n_stroke, "gradients": gradients},
                "text_spans": spans,
                "fonts": fonts,
                "images": images,
            })
            totals["vector_drawings"] += len(drawings)
            totals["fills"] += n_fill
            totals["strokes"] += n_stroke
            totals["gradients"] += gradients
            totals["text_spans"] += len(spans)
            totals["images"] += len(images)

        text_warnings = []
        not_embedded = sorted(n for n, f in fonts_doc.items()
                              if not f["embedded"])
        if totals["text_spans"] > 0 and not_embedded:
            text_warnings.append(
                "fonts not embedded (glyph outlines not extractable from "
                "the file; must be available locally): %s"
                % ", ".join(not_embedded))
        raster_warnings = [w for w in warnings if "low resolution" in w]

        plan = _recovery_plan(
            fmt, True, totals["text_spans"],
            totals["vector_drawings"], totals["images"],
            text_warnings, raster_warnings)
        return {
            "format": fmt,
            "path": path,
            "width_pt": pages[0]["width_pt"] if pages else 0.0,
            "height_pt": pages[0]["height_pt"] if pages else 0.0,
            "page_count": doc.page_count,
            "pages": pages,
            "fonts": [fonts_doc[k] for k in sorted(fonts_doc)],
            "totals": totals,
            "transparency": transparency,
            "warnings": warnings + text_warnings,
            "recovery_plan": plan,
        }
    finally:
        doc.close()


# --------------------------------------------------------------------- SVG

_STYLE_COLOR_RE = re.compile(r"(?:fill|stroke|stop-color)\s*:\s*([^;]+)")


def _svg_len_to_pt(value):
    if value is None:
        return None
    m = re.match(r"\s*([0-9.+\-eE]+)\s*([a-z%]*)\s*$", str(value))
    if not m:
        return None
    try:
        num = float(m.group(1))
    except ValueError:
        return None
    unit = m.group(2).lower()
    if unit == "%":
        return None
    return round(num * _PT_PER_UNIT.get(unit, 0.75), 2)


def _analyze_svg(path):
    tree = ET.parse(path)
    root = tree.getroot()

    def local(tag):
        return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""

    counts = dict((k, 0) for k in _SVG_COUNTED)
    colors = set()
    text_spans = []
    for el in root.iter():
        tag = local(el.tag)
        if tag in counts:
            counts[tag] += 1
        for attr in ("fill", "stroke", "stop-color"):
            v = el.get(attr)
            if v and v.strip().lower() not in ("none", "inherit",
                                               "currentcolor"):
                colors.add(v.strip())
        style = el.get("style")
        if style:
            for v in _STYLE_COLOR_RE.findall(style):
                v = v.strip()
                if v.lower() not in ("none", "inherit", "currentcolor"):
                    colors.add(v)
        if tag == "text":
            txt = "".join(el.itertext()).strip()
            if txt:
                st = el.get("style") or ""
                fm = re.search(r"font-family\s*:\s*([^;]+)", st)
                sm = re.search(r"font-size\s*:\s*([^;]+)", st)
                text_spans.append({
                    "text": txt,
                    "font": (el.get("font-family")
                             or (fm.group(1).strip() if fm else None)),
                    "size": _svg_len_to_pt(
                        el.get("font-size")
                        or (sm.group(1).strip() if sm else None)),
                })

    width_pt = _svg_len_to_pt(root.get("width"))
    height_pt = _svg_len_to_pt(root.get("height"))
    viewbox = None
    vb = root.get("viewBox")
    if vb:
        try:
            viewbox = [float(v) for v in re.split(r"[\s,]+", vb.strip())]
        except ValueError:
            viewbox = None
    if width_pt is None and viewbox:
        width_pt = round(viewbox[2] * 0.75, 2)
    if height_pt is None and viewbox:
        height_pt = round(viewbox[3] * 0.75, 2)

    n_vector = sum(counts[k] for k in
                   ("path", "rect", "circle", "ellipse", "line",
                    "polygon", "polyline"))
    gradients = counts["linearGradient"] + counts["radialGradient"]
    text_warnings = []
    if text_spans:
        text_warnings.append(
            "SVG text uses system fonts; ensure the font families are "
            "installed before opening in Illustrator")
    raster_warnings = []
    if counts["image"] > 0:
        raster_warnings.append(
            "%d embedded/linked raster image element(s) in SVG"
            % counts["image"])

    plan = _recovery_plan("svg", True, len(text_spans), n_vector,
                          counts["image"], text_warnings, raster_warnings)
    return {
        "format": "svg",
        "path": path,
        "width_pt": width_pt,
        "height_pt": height_pt,
        "viewbox": viewbox,
        "page_count": 1,
        "elements": counts,
        "colors": sorted(colors),
        "text_spans": text_spans,
        "fonts": sorted(set(t["font"] for t in text_spans if t["font"])),
        "totals": {"vector_drawings": n_vector, "fills": None,
                   "strokes": None, "gradients": gradients,
                   "text_spans": len(text_spans),
                   "images": counts["image"]},
        "transparency": counts["clipPath"] > 0
                        or any("rgba" in c for c in colors),
        "warnings": text_warnings + raster_warnings,
        "recovery_plan": plan,
    }


# --------------------------------------------------------------------- EPS

def _analyze_eps(path):
    bbox = None
    fonts = []
    creator = None
    with open(path, "rb") as fh:
        head = fh.read(65536).decode("latin-1", "replace")
    m = re.search(r"^%%HiResBoundingBox:\s*([\d.\s\-]+)$", head, re.M)
    if not m:
        m = re.search(r"^%%BoundingBox:\s*([\d.\s\-]+)$", head, re.M)
    if m:
        try:
            vals = [float(v) for v in m.group(1).split()]
            if len(vals) == 4:
                bbox = vals
        except ValueError:
            pass
    fm = re.search(r"^%%DocumentFonts:\s*(.+)$", head, re.M)
    if not fm:
        fm = re.search(r"^%%DocumentNeededFonts:\s*(.+)$", head, re.M)
    if fm and fm.group(1).strip().lower() != "(atend)":
        fonts = [f for f in re.split(r"\s+", fm.group(1).strip()) if f]
    cm = re.search(r"^%%Creator:\s*(.+)$", head, re.M)
    if cm:
        creator = cm.group(1).strip()

    warnings = ["EPS preflight is header-only (DSC comments); open the "
                "file in Illustrator for a full inventory"]
    plan = _recovery_plan("eps", True, 0, 1, 0, [], [])
    plan["warnings"] = list(warnings)
    return {
        "format": "eps",
        "path": path,
        "width_pt": round(bbox[2] - bbox[0], 2) if bbox else None,
        "height_pt": round(bbox[3] - bbox[1], 2) if bbox else None,
        "bounding_box": bbox,
        "page_count": 1,
        "creator": creator,
        "fonts": [{"name": f} for f in fonts],
        "totals": {"vector_drawings": None, "fills": None, "strokes": None,
                   "gradients": None, "text_spans": None, "images": None},
        "transparency": False,
        "warnings": warnings,
        "recovery_plan": plan,
    }


# ------------------------------------------------------------------ raster

def _analyze_raster(path):
    Image = require("PIL.Image")
    ImageStat = require("PIL.ImageStat")
    with Image.open(path) as im:
        width, height = im.size
        mode = im.mode
        dpi = im.info.get("dpi")
        if dpi is not None:
            dpi = (round(float(dpi[0]), 2), round(float(dpi[1]), 2))
        has_alpha = (mode in ("RGBA", "LA", "PA")
                     or "transparency" in im.info)
        rgb = im.convert("RGB")
        stat = ImageStat.Stat(rgb)
        thumb = rgb.copy()
        thumb.thumbnail((64, 64))
        got = thumb.getcolors(64 * 64)
        approx_unique = len(got) if got else None

    warnings = []
    eff_dpi = dpi[0] if dpi else 72.0
    if not dpi:
        warnings.append("no dpi metadata; assuming 72 dpi")
    if eff_dpi < LOW_RES_DPI:
        warnings.append(
            "raster resolution ~%.0f dpi is below %.0f dpi; tracing or "
            "print output will be low quality" % (eff_dpi, LOW_RES_DPI))

    plan = _recovery_plan("raster", False, 0, 0, 1, [], list(warnings))
    return {
        "format": "raster",
        "path": path,
        "width_pt": round(width / eff_dpi * 72.0, 2),
        "height_pt": round(height / eff_dpi * 72.0, 2),
        "page_count": 1,
        "raster": {
            "width_px": width,
            "height_px": height,
            "mode": mode,
            "dpi": dpi,
            "has_alpha": bool(has_alpha),
            "channel_means": [round(v, 2) for v in stat.mean],
            "approx_unique_colors": approx_unique,
        },
        "fonts": [],
        "totals": {"vector_drawings": 0, "fills": 0, "strokes": 0,
                   "gradients": 0, "text_spans": 0, "images": 1},
        "transparency": bool(has_alpha),
        "warnings": warnings,
        "recovery_plan": plan,
    }
