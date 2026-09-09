"""End-to-end tests for v0.10 CLI wiring: inspect/path/gradient/style groups,
reference analysis/compare, and figure reconstruct against the mock DOM."""
import json
import os
import shutil

import pytest

node_missing = shutil.which("node") is None
pytestmark = pytest.mark.skipif(node_missing, reason="node required for mock")
pytest.importorskip("fitz")  # pymupdf, for fidelity engine paths

SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="300pt" height="200pt">
<rect x="10" y="10" width="280" height="180" fill="#dbe9ff" stroke="black"/>
<path d="M20 180 L280 30" stroke="blue" fill="none"/>
<text x="150" y="195" font-family="Helvetica" font-size="10">Synthetic axis</text>
</svg>"""


# ------------------------------------------------------------ object model CLI
def test_path_add_edit_inspect_roundtrip(mock_cli):
    mock_cli.run("doc", "new", "--width", "200", "--height", "200")
    _, out = mock_cli.run("path", "add",
                          "--anchors", "[[10,10],[100,10],[100,100]]",
                          "--right-handles", "[[40,10],null,null]",
                          "--closed", "--fill", "200,0,0",
                          "--item-name", "tri")
    r = out["result"]
    assert r["closed"] is True and r["anchor_count"] == 3
    assert r["anchors"][0]["right"] == [40, 10]
    _, out = mock_cli.run("path", "edit", "--name", "tri",
                          "--points", '[{"index":2,"anchor":[120,120]}]')
    assert out["result"]["anchors"][2]["anchor"] == [120, 120]
    _, out = mock_cli.run("inspect", "paths", "--name", "tri")
    assert out["result"]["paths"][0]["fill"]["rgb"] == [200, 0, 0]


def test_gradient_define_apply_inspect(mock_cli):
    mock_cli.run("doc", "new")
    mock_cli.run("shape", "rect", "--x", "0", "--y", "0", "--w", "50",
                 "--h", "50", "--item-name", "box")
    _, out = mock_cli.run("gradient", "add", "--gradient-name", "sky",
                          "--type", "linear",
                          "--stops",
                          '[{"offset":0,"color":[0,0,255]},'
                          '{"offset":100,"color":[255,255,255],"opacity":50}]')
    assert out["result"]["gradients_defined"] == 1
    _, out = mock_cli.run("gradient", "apply", "--gradient-name", "sky",
                          "--name", "box", "--angle", "45")
    assert out["result"]["updated"] == 1
    _, out = mock_cli.run("gradient", "list")
    g = out["result"]["gradients"][0]
    assert g["name"] == "sky" and g["stop_count"] == 2
    _, out = mock_cli.run("inspect", "paths", "--name", "box")
    assert out["result"]["paths"][0]["fill"]["type"] == "gradient"


def test_style_and_transform(mock_cli):
    mock_cli.run("doc", "new")
    mock_cli.run("shape", "rect", "--x", "10", "--y", "10", "--w", "40",
                 "--h", "20", "--item-name", "bar")
    _, out = mock_cli.run("style", "set", "--name", "bar",
                          "--stroke", "0,0,0", "--cap", "round",
                          "--dash", "[4,2]", "--opacity", "80")
    assert out["result"]["updated"] == 1
    _, out = mock_cli.run("inspect", "paths", "--name", "bar")
    p = out["result"]["paths"][0]
    assert p["cap"] == "round" and p["dash"] == [4, 2] and p["opacity"] == 80
    _, out = mock_cli.run("object", "transform", "--name", "bar",
                          "--scale-x", "200", "--scale-y", "200",
                          "--about", "topleft")
    after = out["result"]["items"][0]["after"]["bounds"]
    assert abs(after["w"] - 80) < 0.5 and abs(after["h"] - 40) < 0.5


def test_inspect_document_and_editability(mock_cli):
    mock_cli.run("doc", "new", "--base-layer", "Art")
    mock_cli.run("text", "add", "hello", "--x", "5", "--y", "5")
    _, out = mock_cli.run("inspect", "document")
    layers = out["result"]["layers"]
    assert layers[0]["name"] == "Art"
    assert layers[0]["item_counts"]["text"] == 1
    _, out = mock_cli.run("inspect", "editability")
    ed = out["result"]["editability"]
    assert ed["editability_status"] in ("PASS", "WARN")
    assert ed["live_text"] == 1


def test_text_update_typography(mock_cli):
    mock_cli.run("doc", "new")
    mock_cli.run("text", "add", "axis label", "--x", "5", "--y", "5",
                 "--item-name", "t")
    _, out = mock_cli.run("text", "update", "--name", "t",
                          "--set-tracking", "50", "--set-leading", "14",
                          "--set-justify", "center")
    after = out["result"]["items"][0]["after"]
    assert after["tracking"] == 50 and after["leading"] == 14
    assert after["justification"] == "center"


# ------------------------------------------------------------ reference engine
def test_reference_analyze_svg(mock_cli, tmp_path):
    src = tmp_path / "ref.svg"
    src.write_text(SVG)
    _, out = mock_cli.run("reference", "analyze", str(src))
    r = out["result"]
    assert r["format"] == "svg"
    assert r["recovery_plan"]["recommended_mode"] == "preserve"
    assert r["recovery_plan"]["classes"]["text_live"]["present"] is True


def test_reference_render_and_compare_identical(mock_cli, tmp_path):
    src = tmp_path / "ref.svg"
    src.write_text(SVG)
    _, out = mock_cli.run("reference", "render", str(src),
                          str(tmp_path / "a.png"), "--dpi", "96")
    a = out["result"]
    assert a["width_px"] > 100
    mock_cli.run("reference", "render", str(src), str(tmp_path / "b.png"),
                 "--dpi", "96")
    _, out = mock_cli.run("reference", "compare", str(tmp_path / "a.png"),
                          str(tmp_path / "b.png"), "--dpi", "96")
    m = out["result"]["metrics"]
    assert m["ssim"] > 0.99
    assert out["result"]["largest_differences"] == []


# ------------------------------------------------------------ reconstruct
def test_reconstruct_preserve_svg(mock_cli, tmp_path):
    src = tmp_path / "ref.svg"
    src.write_text(SVG)
    out_ai = tmp_path / "recon.ai"
    _, out = mock_cli.run("figure", "reconstruct", "--reference", str(src),
                          "--mode", "preserve", "--output", str(out_ai))
    man = out["result"]
    assert man["mode"] == "preserve" and man["route"] == "native_open"
    assert os.path.isfile(out_ai)
    assert os.path.isfile(man["manifest_path"])
    assert man["editability"]["editability_status"] in ("PASS", "WARN")
    assert man["editability"]["live_text"] >= 1        # SVG text stayed live
    # mock export produces stub bytes -> compare must degrade to a warning
    assert man["compare"] is None
    assert any("comparison unavailable" in w.lower() for w in man["warnings"])


def test_reconstruct_auto_follows_preflight(mock_cli, tmp_path):
    src = tmp_path / "ref.svg"
    src.write_text(SVG)
    _, out = mock_cli.run("figure", "reconstruct", "--reference", str(src),
                          "--mode", "auto", "--no-compare",
                          "--output", str(tmp_path / "r2.ai"))
    assert out["result"]["mode"] == "preserve"


def test_reconstruct_raster_places_locked_template(mock_cli, tmp_path):
    from PIL import Image
    ref = tmp_path / "scan.png"
    Image.new("RGB", (640, 480), (250, 250, 250)).save(ref, dpi=(96, 96))
    _, out = mock_cli.run("figure", "reconstruct", "--reference", str(ref),
                          "--mode", "fidelity", "--no-compare",
                          "--output", str(tmp_path / "r3.ai"))
    man = out["result"]
    assert man["route"] == "raster_template"
    assert man["unrecoverable"], "raster limits must be disclosed"
    _, layers = mock_cli.run("layer", "list", "--doc", "r3.ai")
    ref_layer = [l for l in layers["result"]["layers"]
                 if l["name"].startswith("Reference")][0]
    assert ref_layer["locked"] is True


def test_reconstruct_preserve_refuses_raster(mock_cli, tmp_path):
    from PIL import Image
    ref = tmp_path / "scan.png"
    Image.new("RGB", (100, 100)).save(ref)
    proc, out = mock_cli.run("figure", "reconstruct", "--reference", str(ref),
                             "--mode", "preserve",
                             "--output", str(tmp_path / "x.ai"),
                             expect_exit=2)
    assert "preserve mode needs recoverable vector content" in out["error"]["message"]


def test_reconstruct_overwrite_guard(mock_cli, tmp_path):
    src = tmp_path / "ref.svg"
    src.write_text(SVG)
    target = tmp_path / "keep.ai"
    target.write_text("PRECIOUS")
    proc, out = mock_cli.run("figure", "reconstruct", "--reference", str(src),
                             "--output", str(target), expect_exit=8)
    assert target.read_text() == "PRECIOUS"
