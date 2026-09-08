"""Figure assembly workflows against the mock DOM (portable)."""
import json
import os
import shutil

import pytest

node_missing = shutil.which("node") is None
pytestmark = pytest.mark.skipif(node_missing, reason="node required for mock")

SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="300pt" height="200pt">
<rect x="10" y="10" width="280" height="180" fill="none" stroke="black"/>
<path d="M20 180 L280 30"/>
<text x="150" y="195">Synthetic x-axis (a.u.)</text>
<text x="10" y="100">Synthetic y</text>
</svg>"""


def _write_panels(tmp_path, n=4):
    pdir = tmp_path / "panels"
    pdir.mkdir(exist_ok=True)
    for i in range(n):
        (pdir / f"panel_{chr(65 + i)}.svg").write_text(SVG)
    return pdir


def _spec(tmp_path, n=4):
    panels = []
    pos = [(0, 0), (92, 0), (0, 62), (92, 62)]
    for i in range(n):
        pid = chr(65 + i)
        panels.append({"id": pid, "source": f"panels/panel_{pid}.svg",
                       "mode": "editable",
                       "frame": {"x": pos[i][0], "y": pos[i][1], "w": 88, "h": 58},
                       "label": {"text": pid}})
    return {
        "version": 1,
        "canvas": {"width": 180, "height": 120, "units": "mm", "color_mode": "RGB"},
        "defaults": {"label": {"font": "Helvetica-Bold", "size_pt": 12}},
        "panels": panels,
        "output": {"ai": "figure1.ai",
                   "exports": [{"format": "png", "path": "figure1.png", "dpi": 300},
                               {"format": "svg", "path": "figure1.svg"},
                               {"format": "pdf", "path": "figure1.pdf"}]},
    }


def test_import_editable_reports_content(mock_cli, tmp_path):
    _write_panels(tmp_path, 1)
    mock_cli.run("doc", "new", "--width", "500", "--height", "400")
    _, out = mock_cli.run("import", str(tmp_path / "panels/panel_A.svg"),
                          "--layer", "Panels", "--group-name", "panel_A",
                          "--at", "10", "10")
    r = out["result"]
    assert r["editable"] is True
    assert r["type"] == "group"
    assert r["items_copied"] >= 3
    assert r["source_summary"]["text_frames"] == 2
    b = r["bounds"]
    assert abs(b["x"] - 10) < 0.01 and abs(b["y"] - 10) < 0.01


def test_import_linked_is_flagged_not_editable(mock_cli, tmp_path):
    _write_panels(tmp_path, 1)
    mock_cli.run("doc", "new")
    _, out = mock_cli.run("import", str(tmp_path / "panels/panel_A.svg"),
                          "--mode", "linked")
    assert out["result"]["editable"] is False
    assert any("LINKED" in w for w in out["result"]["warnings"])


def test_figure_validate_catches_errors_before_mutation(mock_cli, tmp_path):
    spec = _spec(tmp_path)  # panels NOT written -> sources missing
    spec_path = tmp_path / "fig.json"
    spec_path.write_text(json.dumps(spec))
    proc, out = mock_cli.run("figure", "validate", "--spec", str(spec_path),
                             expect_exit=2)
    assert not os.path.exists(tmp_path / "figure1.ai")
    _, docs = mock_cli.run("doc", "list")
    assert docs["result"]["count"] == 0  # no document was created


def test_figure_assemble_and_verify(mock_cli, tmp_path):
    _write_panels(tmp_path)
    spec_path = tmp_path / "fig.json"
    spec_path.write_text(json.dumps(_spec(tmp_path)))
    _, out = mock_cli.run("figure", "assemble", "--spec", str(spec_path))
    man = out["result"]
    assert man["completed"] is True
    assert len(man["panels"]) == 4
    for p in man["panels"]:
        assert p["editable"] is True
        # 300x200pt panel into 88x58mm frame: scale = min limits, aspect kept
        assert 0 < p["scale_percent"] <= 100
        fb = p["final_bounds_pt"]
        assert abs(fb["w"] / fb["h"] - 300 / 200) < 0.01  # aspect preserved
        assert p["label"]["substituted"] is False
    for o in man["outputs"]:
        assert o["size_bytes"] and os.path.isfile(o["path"])
    assert os.path.isfile(man["manifest_path"])
    assert {o["format"] for o in man["outputs"]} == {"AI", "PNG", "SVG", "PDF"}

    # master must reopen with editable text + groups
    mock_cli.run("doc", "close", "--doc", "figure1.ai", "--discard-changes")
    _, out = mock_cli.run("figure", "verify", "--spec", str(spec_path))
    v = out["result"]
    assert v["ok"] is True, v["checks"]
    names = {c["check"] for c in v["checks"]}
    assert "live_text_in_master" in names
    assert "panel_A_group_present" in names


def test_figure_assemble_overwrite_guard(mock_cli, tmp_path):
    _write_panels(tmp_path)
    (tmp_path / "figure1.ai").write_text("KEEP ME")
    spec_path = tmp_path / "fig.json"
    spec_path.write_text(json.dumps(_spec(tmp_path)))
    proc, out = mock_cli.run("figure", "assemble", "--spec", str(spec_path),
                             expect_exit=8)
    assert (tmp_path / "figure1.ai").read_text() == "KEEP ME"
    _, docs = mock_cli.run("doc", "list")
    assert docs["result"]["count"] == 0  # refused BEFORE creating the document


def test_export_pdf_requires_saved_master(mock_cli, tmp_path):
    mock_cli.run("doc", "new")
    proc, out = mock_cli.run("export", "pdf", str(tmp_path / "o.pdf"),
                             expect_exit=6)
    assert out["error"]["code"] == "UNSAVED_CHANGES"
    mock_cli.run("doc", "save-as", str(tmp_path / "m.ai"))
    _, out = mock_cli.run("export", "pdf", str(tmp_path / "o.pdf"))
    assert out["result"]["reassociated_to"].endswith("m.ai")


def test_align_and_distribute(mock_cli):
    mock_cli.run("doc", "new", "--width", "300", "--height", "300")
    for i, x in enumerate((0, 50, 120)):
        mock_cli.run("shape", "rect", "--x", str(x), "--y", str(10 * i),
                     "--w", "20", "--h", "20", "--item-name", f"sq{i}",
                     "--layer", "grid", "--layer-create")
    _, out = mock_cli.run("object", "align", "top", "--layer", "grid")
    ys = [i["bounds"]["y"] for i in out["result"]["items"]]
    assert all(abs(y - ys[0]) < 1e-6 for y in ys)
    _, out = mock_cli.run("object", "distribute", "hdist", "--layer", "grid",
                          "--to", "artboard")
    xs = sorted(i["bounds"]["x"] for i in out["result"]["items"])
    gaps = [xs[1] - xs[0], xs[2] - xs[1]]
    assert abs(gaps[0] - gaps[1]) < 1e-6
