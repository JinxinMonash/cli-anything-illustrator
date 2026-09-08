"""LIVE integration tests: require macOS + Adobe Illustrator + Automation
permission. Run on the Mac with:

    python -m pytest tests/integration -m illustrator -v

Every test uses disposable documents and writes only under a temp directory.
These tests are the evidence layer the mock cannot provide.
"""
import json
import os
import shutil
import subprocess
import sys

import pytest

pytestmark = [
    pytest.mark.illustrator,
    pytest.mark.skipif(sys.platform != "darwin", reason="requires macOS"),
    pytest.mark.skipif(shutil.which("osascript") is None, reason="requires osascript"),
]

GREEK = "Δ conc. (µM) — αβγ ≥ 10 \"quoted\" 'single'"

SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="300pt" height="200pt">
<rect x="10" y="10" width="280" height="180" fill="none" stroke="black"/>
<path d="M20 180 L280 30" stroke="blue" fill="none"/>
<text x="150" y="195" font-family="Helvetica" font-size="10">Synthetic x (a.u.)</text>
</svg>"""


def run_cli(*args, expect_exit=0, timeout=240):
    proc = subprocess.run(
        [sys.executable, "-m", "cli_anything.illustrator", *args],
        capture_output=True, text=True, timeout=timeout,
    )
    assert proc.returncode == expect_exit, (
        f"exit {proc.returncode} != {expect_exit}\n{proc.stdout}\n{proc.stderr}")
    return json.loads(proc.stdout) if proc.stdout.strip() else None


@pytest.fixture(autouse=True)
def _close_leftover_docs():
    yield
    # close any documents the test left open, discarding changes
    out = run_cli("doc", "list")
    for d in out["result"]["documents"]:
        run_cli("doc", "close", "--doc", d["name"], "--discard-changes")


def test_doctor_all_green():
    out = run_cli("app", "doctor")
    checks = {c["check"]: c["status"] for c in out["result"]["checks"]}
    assert checks.get("illustrator_installed") == "ok"
    assert checks.get("automation_permission") == "ok"
    assert checks.get("scripting_roundtrip") == "ok"


def test_minimal_round_trip(tmp_path):
    """Brief section 3: create doc, add text, read back, save new AI file."""
    out = run_cli("doc", "new", "--width", "100", "--height", "80",
                  "--units", "mm")
    assert abs(out["result"]["width"] - 100 * 72 / 25.4) < 0.5
    out = run_cli("text", "add", GREEK, "--x", "10", "--y", "10",
                  "--units", "mm", "--item-name", "probe")
    assert out["result"]["contents_full"] == GREEK
    out = run_cli("text", "list")
    assert out["result"]["total_matches"] == 1
    target = tmp_path / "round trip ω.ai"
    out = run_cli("doc", "save-as", str(target))
    assert os.path.getsize(target) > 1000
    run_cli("doc", "close")
    out = run_cli("doc", "open", str(target))
    assert out["result"]["text_frames"] == 1
    out = run_cli("text", "list")
    assert out["result"]["items"][0]["name"] == "probe"


def test_ambiguous_document_refused():
    run_cli("doc", "new")
    run_cli("doc", "new")
    out = run_cli("doc", "info", expect_exit=5)
    assert out["error"]["code"] == "AMBIGUOUS_DOCUMENT"


def test_font_resolution_and_refusal():
    run_cli("doc", "new")
    out = run_cli("text", "add", "x", "--x", "10", "--y", "10",
                  "--font", "ThisFontDoesNotExist-Bold", expect_exit=6)
    assert out["error"]["code"] == "FONT_NOT_FOUND"
    out = run_cli("fonts", "list", "--contains", "helvetica")
    assert out["result"]["returned"] >= 1


def test_shapes_and_object_ops():
    run_cli("doc", "new", "--width", "300", "--height", "300")
    for i in range(2):
        run_cli("shape", "rect", "--x", str(20 + 60 * i), "--y", "20",
                "--w", "40", "--h", "40", "--item-name", f"box{i}")
    out = run_cli("object", "list", "--type", "path")
    assert out["result"]["total_matches"] == 2
    out = run_cli("object", "move", "--name", "box1", "--to", "100", "100")
    b = out["result"]["items"][0]["after"]["bounds"]
    assert abs(b["x"] - 100) < 0.5 and abs(b["y"] - 100) < 0.5
    out = run_cli("object", "group", "--type", "path", "--group-name", "pair")
    assert out["result"]["member_count"] == 2


def test_import_editable_svg(tmp_path):
    src = tmp_path / "panel.svg"
    src.write_text(SVG)
    run_cli("doc", "new", "--width", "500", "--height", "400")
    out = run_cli("import", str(src), "--layer", "Panels",
                  "--group-name", "panel_A", "--at", "20", "20")
    r = out["result"]
    assert r["editable"] is True and r["items_copied"] >= 2
    assert abs(r["bounds"]["x"] - 20) < 0.5


def test_exports_and_reopen(tmp_path):
    run_cli("doc", "new", "--width", "200", "--height", "150")
    run_cli("text", "add", "export probe", "--x", "20", "--y", "40")
    master = tmp_path / "master.ai"
    run_cli("doc", "save-as", str(master))
    png = tmp_path / "out.png"
    out = run_cli("export", "png", str(png), "--dpi", "150")
    assert os.path.getsize(png) > 500
    svg = tmp_path / "out.svg"
    run_cli("export", "svg", str(svg))
    assert b"<svg" in open(svg, "rb").read(200).lower()
    pdf = tmp_path / "out.pdf"
    out = run_cli("export", "pdf", str(pdf))
    assert open(pdf, "rb").read(5) == b"%PDF-"
    # document association restored to the .ai master
    assert out["result"]["reassociated_to"] == str(master)
    out = run_cli("doc", "info")
    assert out["result"]["path"] == str(master)
    # overwrite guard
    run_cli("export", "png", str(png), expect_exit=8)


def test_figure_assembly_acceptance(tmp_path):
    """Principal acceptance demo (brief section 7) at integration level."""
    pdir = tmp_path / "panels"
    pdir.mkdir()
    for pid in "ABCD":
        (pdir / f"panel_{pid}.svg").write_text(SVG)
    spec = {
        "version": 1,
        "canvas": {"width": 180, "height": 120, "units": "mm", "color_mode": "RGB"},
        "defaults": {"label": {"font": "Helvetica-Bold", "size_pt": 12}},
        "panels": [
            {"id": p, "source": f"panels/panel_{p}.svg",
             "frame": {"x": x, "y": y, "w": 88, "h": 58}, "label": {"text": p}}
            for p, (x, y) in zip("ABCD", [(0, 0), (92, 0), (0, 62), (92, 62)])
        ],
        "output": {"ai": "figure1.ai",
                   "exports": [{"format": "png", "path": "figure1.png", "dpi": 300},
                               {"format": "svg", "path": "figure1.svg"},
                               {"format": "pdf", "path": "figure1.pdf"}]},
    }
    spec_path = tmp_path / "figure1.json"
    spec_path.write_text(json.dumps(spec))
    out = run_cli("figure", "assemble", "--spec", str(spec_path))
    man = out["result"]
    assert man["completed"] and len(man["panels"]) == 4
    run_cli("doc", "close", "--doc", "figure1.ai", "--discard-changes")
    out = run_cli("figure", "verify", "--spec", str(spec_path))
    assert out["result"]["ok"] is True, out["result"]["checks"]
