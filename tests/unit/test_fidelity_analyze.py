"""Unit tests for the fidelity preflight analyzer and reference renderer.

Synthetic references are built AT TEST TIME with PyMuPDF (PDF containing
rects, a bezier curve, text in two fonts and an embedded PNG) and Pillow
(raster references).  Tests are skipped when pymupdf is unavailable.
"""

import io
import os

import pytest

fitz = pytest.importorskip("fitz")
PIL_Image = pytest.importorskip("PIL.Image")

from cli_anything.illustrator import fidelity
from cli_anything.illustrator.fidelity.analyze import analyze_reference
from cli_anything.illustrator.fidelity.render import render_reference


def _png_bytes(w=100, h=80, color=(200, 40, 40)):
    im = PIL_Image.new("RGB", (w, h), color)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(scope="module")
def synthetic_pdf(tmp_path_factory):
    """Letter page: 2 filled/stroked rects, a bezier, text in two fonts,
    one embedded 100x80 PNG placed in a 100x80 pt rect (=> ~72 dpi)."""
    path = str(tmp_path_factory.mktemp("ref") / "ref.pdf")
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.draw_rect(fitz.Rect(72, 72, 272, 172),
                   color=(0, 0, 0), fill=(0.8, 0.1, 0.1))
    page.draw_rect(fitz.Rect(300, 72, 500, 172), color=(0, 0, 1))
    page.draw_bezier(fitz.Point(72, 300), fitz.Point(150, 200),
                     fitz.Point(250, 400), fitz.Point(330, 300),
                     color=(0, 0.5, 0))
    page.insert_text(fitz.Point(72, 220), "Hello Figure",
                     fontname="helv", fontsize=14)
    page.insert_text(fitz.Point(72, 250), "Panel A",
                     fontname="cour", fontsize=10)
    page.insert_image(fitz.Rect(400, 300, 500, 380), stream=_png_bytes())
    doc.save(path)
    doc.close()
    return path


@pytest.fixture(scope="module")
def synthetic_png(tmp_path_factory):
    path = str(tmp_path_factory.mktemp("ref") / "ref.png")
    im = PIL_Image.new("RGB", (400, 300), (255, 255, 255))
    for x in range(100, 300):
        for y in range(100, 200):
            im.putpixel((x, y), (10, 60, 200))
    im.save(path, dpi=(72, 72))
    return path


@pytest.fixture(scope="module")
def synthetic_svg(tmp_path_factory):
    path = str(tmp_path_factory.mktemp("ref") / "ref.svg")
    svg = """<svg xmlns="http://www.w3.org/2000/svg" width="360pt"
  height="240pt" viewBox="0 0 480 320">
  <defs>
    <linearGradient id="g1">
      <stop offset="0" stop-color="#112233"/>
      <stop offset="1" stop-color="#445566"/>
    </linearGradient>
  </defs>
  <rect x="10" y="10" width="100" height="50" fill="#ff0000"/>
  <rect x="120" y="10" width="100" height="50" fill="url(#g1)"/>
  <circle cx="60" cy="150" r="40" fill="rgb(0,128,0)" stroke="#000000"/>
  <path d="M 200 100 C 250 50 300 150 350 100" stroke="#0000ff"
        fill="none"/>
  <text x="20" y="220" font-family="Helvetica"
        font-size="14">Panel B</text>
  <text x="20" y="240" style="font-family: Courier; font-size: 10px">n =
  12</text>
</svg>
"""
    with open(path, "w") as fh:
        fh.write(svg)
    return path


# ------------------------------------------------------------------ PDF

def test_pdf_is_vector_native_preserve(synthetic_pdf):
    rep = analyze_reference(synthetic_pdf)
    assert rep["format"] == "pdf"
    assert rep["page_count"] == 1
    assert rep["width_pt"] == pytest.approx(612, abs=1)
    assert rep["height_pt"] == pytest.approx(792, abs=1)
    plan = rep["recovery_plan"]
    assert plan["classes"]["vector_native"]["present"] is True
    assert plan["primary_class"] == "vector_native"
    assert plan["recommended_mode"] == "preserve"
    assert plan["trace_route"] is None


def test_pdf_live_text_two_fonts(synthetic_pdf):
    rep = analyze_reference(synthetic_pdf)
    assert rep["recovery_plan"]["classes"]["text_live"]["present"] is True
    spans = rep["pages"][0]["text_spans"]
    texts = " ".join(s["text"] for s in spans)
    assert "Hello Figure" in texts
    assert "Panel A" in texts
    fonts = set(s["font"] for s in spans)
    assert len(fonts) >= 2
    sizes = sorted(s["size"] for s in spans)
    assert sizes[0] == pytest.approx(10, abs=0.5)
    assert sizes[-1] == pytest.approx(14, abs=0.5)
    for s in spans:
        assert len(s["bbox"]) == 4
        assert s["color"].startswith("#")


def test_pdf_vector_counts(synthetic_pdf):
    rep = analyze_reference(synthetic_pdf)
    vec = rep["pages"][0]["vector"]
    assert vec["drawings"] >= 3
    assert vec["fills"] >= 1
    assert vec["strokes"] >= 2
    assert rep["totals"]["vector_drawings"] == vec["drawings"]


def test_pdf_embedded_raster_detected(synthetic_pdf):
    rep = analyze_reference(synthetic_pdf)
    imgs = rep["pages"][0]["images"]
    assert len(imgs) == 1
    assert imgs[0]["width_px"] == 100
    assert imgs[0]["height_px"] == 80
    assert imgs[0]["dpi_estimate"] == pytest.approx(72, abs=2)
    # 72 dpi < 150 dpi threshold -> low-resolution warning
    assert any("low resolution" in w for w in rep["warnings"])


def test_pdf_fonts_listed_with_embedding_flag(synthetic_pdf):
    rep = analyze_reference(synthetic_pdf)
    names = [f["name"] for f in rep["fonts"]]
    assert len(names) >= 2
    assert all("embedded" in f for f in rep["fonts"])
    # Base-14 fonts are not embedded -> extraction warning is surfaced.
    if any(not f["embedded"] for f in rep["fonts"]):
        tw = rep["recovery_plan"]["classes"]["text_live"]["warnings"]
        assert any("not embedded" in w for w in tw)


# --------------------------------------------------------------- raster

def test_raster_png_classified_for_trace(synthetic_png):
    rep = analyze_reference(synthetic_png)
    assert rep["format"] == "raster"
    assert rep["raster"]["width_px"] == 400
    assert rep["raster"]["height_px"] == 300
    assert rep["raster"]["has_alpha"] is False
    plan = rep["recovery_plan"]
    assert plan["classes"]["vector_native"]["present"] is False
    assert plan["classes"]["raster_only"]["present"] is True
    assert plan["primary_class"] == "raster_only"
    assert plan["recommended_mode"] == "fidelity"
    assert plan["trace_route"] == "image_trace"
    # 72 dpi -> low-resolution warning
    assert any("low" in w for w in rep["warnings"])


# ------------------------------------------------------------------ SVG

def test_svg_counts_dims_colors(synthetic_svg):
    rep = analyze_reference(synthetic_svg)
    assert rep["format"] == "svg"
    assert rep["width_pt"] == pytest.approx(360, abs=0.5)
    assert rep["height_pt"] == pytest.approx(240, abs=0.5)
    assert rep["viewbox"] == [0.0, 0.0, 480.0, 320.0]
    el = rep["elements"]
    assert el["rect"] == 2
    assert el["circle"] == 1
    assert el["path"] == 1
    assert el["text"] == 2
    assert el["linearGradient"] == 1
    assert rep["totals"]["gradients"] == 1
    assert "#ff0000" in rep["colors"]
    assert "rgb(0,128,0)" in rep["colors"]
    assert "#112233" in rep["colors"]


def test_svg_vector_native_with_live_text(synthetic_svg):
    rep = analyze_reference(synthetic_svg)
    plan = rep["recovery_plan"]
    assert plan["primary_class"] == "vector_native"
    assert plan["recommended_mode"] == "preserve"
    assert plan["classes"]["text_live"]["present"] is True
    assert plan["classes"]["text_live"]["count"] == 2
    fonts = rep["fonts"]
    assert "Helvetica" in fonts and "Courier" in fonts
    texts = [t["text"] for t in rep["text_spans"]]
    assert "Panel B" in texts


# --------------------------------------------------------------- errors

def test_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        analyze_reference("/nonexistent/figure.pdf")


def test_unsupported_extension_raises(tmp_path):
    p = tmp_path / "figure.docx"
    p.write_text("not a figure")
    with pytest.raises(ValueError):
        analyze_reference(str(p))


def test_require_missing_dependency_names_extra():
    with pytest.raises(ImportError) as exc:
        fidelity.require("nonexistent_module_xyz_12345")
    msg = str(exc.value)
    assert 'pip install "cli-anything-illustrator[fidelity]"' in msg


def test_lazy_public_api():
    assert callable(fidelity.analyze_reference)
    assert callable(fidelity.compare_images)
    assert callable(fidelity.score_editability)
    with pytest.raises(AttributeError):
        fidelity.not_a_function  # noqa: B018


# --------------------------------------------------------------- render

def test_render_pdf_exact_dims(synthetic_pdf, tmp_path):
    out = str(tmp_path / "ref144.png")
    info = render_reference(synthetic_pdf, 144, out)
    assert os.path.isfile(out)
    assert info["width_px"] == 1224   # 612 pt * 144/72
    assert info["height_px"] == 1584  # 792 pt * 144/72
    assert info["source_format"] == "pdf"
    with PIL_Image.open(out) as im:
        assert im.size == (1224, 1584)


def test_render_raster_resize_to_dpi(synthetic_png, tmp_path):
    out = str(tmp_path / "ref144.png")
    info = render_reference(synthetic_png, 144, out)
    # 72 dpi source scaled to 144 dpi -> dimensions double
    assert (info["width_px"], info["height_px"]) == (800, 600)
    assert info["source_format"] == "raster"


def test_render_rejects_bad_page_and_dpi(synthetic_pdf, tmp_path):
    with pytest.raises(ValueError):
        render_reference(synthetic_pdf, 144, str(tmp_path / "x.png"),
                         page=5)
    with pytest.raises(ValueError):
        render_reference(synthetic_pdf, 0, str(tmp_path / "x.png"))
