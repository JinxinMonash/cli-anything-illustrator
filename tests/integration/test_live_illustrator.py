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


def test_runner_applescript_compiles(tmp_path):
    """Regression (0.9.1): the generated runner must COMPILE, which requires
    Illustrator's dictionary to resolve `do javascript` from the literal app
    name. A runtime-variable tell target fails exactly here."""
    from cli_anything.illustrator.backend.mac import MacBackend
    src = MacBackend().build_runner(
        json.loads(subprocess.run(
            [sys.executable, "-m", "cli_anything.illustrator", "app", "detect"],
            capture_output=True, text=True).stdout)["result"]["app_name"])
    scpt = tmp_path / "runner.applescript"
    scpt.write_text(src)
    proc = subprocess.run(["osacompile", "-o", str(tmp_path / "runner.scpt"),
                           str(scpt)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


SVG_REF = """<svg xmlns="http://www.w3.org/2000/svg" width="300pt" height="200pt">
<rect x="10" y="10" width="280" height="180" fill="none" stroke="black"/>
<path d="M30 180 C 100 60, 200 160, 280 40" stroke="blue" stroke-width="2" fill="none"/>
<text x="20" y="30" font-family="Helvetica" font-size="12">Live reconstruct test</text>
</svg>"""


class TestReconstructLive:
    """v0.10 fidelity workflow against real Illustrator."""

    def test_reconstruct_preserve_and_compare(self, tmp_path):
        pytest.importorskip("pymupdf", reason="fidelity extra not installed")
        ref = tmp_path / "ref.svg"
        ref.write_text(SVG_REF)
        out_ai = tmp_path / "recon.ai"
        out = run_cli("figure", "reconstruct", "--reference", str(ref),
                      "--mode", "preserve", "--output", str(out_ai),
                      "--dpi", "150")
        man = out["result"]
        assert man["route"] == "native_open"
        assert os.path.isfile(out_ai)
        ed = man["editability"]
        assert ed["editability_status"] in ("PASS", "WARN")
        assert ed["live_text"] >= 1, "SVG text must stay live in Illustrator"
        # REAL comparison: Illustrator-rendered PNG vs reference render
        assert man["compare"] is not None, man["warnings"]
        m = man["compare"]["metrics"]
        assert m["ssim"] > 0.85, f"low fidelity: {m}"
        run_cli("doc", "close", "--doc", "recon.ai", "--discard-changes")

    def test_inspect_paths_roundtrip(self, tmp_path):
        run_cli("doc", "new", "--width", "100", "--height", "100")
        run_cli("path", "add", "--anchors", "[[10,10],[90,10],[50,90]]",
                "--closed", "--fill", "0,120,60", "--item-name", "livetri")
        out = run_cli("inspect", "paths", "--name", "livetri")
        p = out["result"]["paths"][0]
        assert p["anchor_count"] == 3 and p["closed"] is True
        assert p["fill"]["rgb"] == [0, 120, 60]
        run_cli("doc", "close", "--discard-changes")
