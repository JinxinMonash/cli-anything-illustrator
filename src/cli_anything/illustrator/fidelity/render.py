"""Reference rasterisation.

``render_reference(path, dpi, out_png)`` renders a reference file to a PNG
at a requested resolution so it can be compared pixel-wise against an
Illustrator export.  PDF/AI/SVG go through PyMuPDF; raster inputs are a
Pillow resize-to-dpi passthrough.
"""

import os

from cli_anything.illustrator.fidelity import require

_FITZ_EXTS = (".pdf", ".ai", ".svg")
_RASTER_EXTS = (".png", ".jpg", ".jpeg", ".tif", ".tiff")


def render_reference(path, dpi, out_png, page=0):
    """Render a reference file to PNG at the given dpi.

    Parameters:
        path (str): input file (.pdf/.ai/.svg via PyMuPDF;
            .png/.jpg/.jpeg/.tif/.tiff via Pillow).
        dpi (float): target resolution in dots per inch (> 0).
        out_png (str): output PNG path (parent directories are created).
        page (int): 0-based page index for multi-page PDF (default 0).

    Returns:
        dict:
            out_png (str): path written
            width_px, height_px (int): exact pixel dimensions of the PNG
            dpi (float): requested dpi
            source_format (str): "pdf" | "ai" | "svg" | "raster"
            page (int): page index rendered (0 for non-PDF)

    Raises:
        FileNotFoundError: input missing.
        ValueError: unsupported extension (.eps is not renderable without
            Illustrator/Ghostscript), non-positive dpi, or page out of
            range.
        ImportError: missing optional dependency (message names
            ``pip install "cli-anything-illustrator[fidelity]"``).
    """
    if not os.path.isfile(path):
        raise FileNotFoundError("reference file not found: %s" % path)
    if not dpi or dpi <= 0:
        raise ValueError("dpi must be > 0, got %r" % (dpi,))
    ext = os.path.splitext(path)[1].lower()
    parent = os.path.dirname(os.path.abspath(out_png))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)

    if ext in _FITZ_EXTS:
        fitz = require("fitz")
        doc = fitz.open(path)
        try:
            if page < 0 or page >= doc.page_count:
                raise ValueError(
                    "page %d out of range (document has %d page(s))"
                    % (page, doc.page_count))
            zoom = float(dpi) / 72.0
            pm = doc[page].get_pixmap(matrix=fitz.Matrix(zoom, zoom),
                                      alpha=False)
            pm.save(out_png)
            source_format = {".pdf": "pdf", ".ai": "ai", ".svg": "svg"}[ext]
            return {"out_png": out_png, "width_px": int(pm.width),
                    "height_px": int(pm.height), "dpi": float(dpi),
                    "source_format": source_format, "page": int(page)}
        finally:
            doc.close()

    if ext in _RASTER_EXTS:
        Image = require("PIL.Image")
        with Image.open(path) as im:
            src_dpi = im.info.get("dpi")
            src_dpi = float(src_dpi[0]) if src_dpi else 72.0
            scale = float(dpi) / src_dpi
            w = max(1, int(round(im.width * scale)))
            h = max(1, int(round(im.height * scale)))
            out = im.convert("RGB")
            if (w, h) != im.size:
                out = out.resize((w, h), Image.LANCZOS)
            out.save(out_png, format="PNG", dpi=(float(dpi), float(dpi)))
        return {"out_png": out_png, "width_px": w, "height_px": h,
                "dpi": float(dpi), "source_format": "raster", "page": 0}

    raise ValueError(
        "cannot render %r (supported: %s; EPS requires Illustrator)"
        % (ext, ", ".join(_FITZ_EXTS + _RASTER_EXTS)))
