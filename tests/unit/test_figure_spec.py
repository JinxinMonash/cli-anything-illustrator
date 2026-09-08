import copy

from cli_anything.illustrator.ops.figure import validate_spec


def good_spec(tmp_path):
    (tmp_path / "p.svg").write_text("<svg width='100' height='100'></svg>")
    return {
        "version": 1,
        "canvas": {"width": 180, "height": 120, "units": "mm", "color_mode": "RGB"},
        "panels": [
            {"id": "A", "source": "p.svg", "frame": {"x": 0, "y": 0, "w": 80, "h": 50},
             "label": {"text": "A"}},
            {"id": "B", "source": "p.svg", "frame": {"x": 90, "y": 0, "w": 80, "h": 50}},
        ],
        "output": {"ai": "fig.ai",
                   "exports": [{"format": "png", "path": "fig.png", "dpi": 300}]},
    }


def test_valid_spec_passes(tmp_path):
    assert validate_spec(good_spec(tmp_path), str(tmp_path)) == []


def _expect_error(tmp_path, mutate, needle):
    spec = good_spec(tmp_path)
    mutate(spec)
    errs = validate_spec(spec, str(tmp_path))
    assert any(needle in e for e in errs), errs


def test_bad_version(tmp_path):
    _expect_error(tmp_path, lambda s: s.update(version=2), "version")


def test_duplicate_panel_ids(tmp_path):
    def m(s): s["panels"][1]["id"] = "A"
    _expect_error(tmp_path, m, "duplicated")


def test_missing_source(tmp_path):
    def m(s): s["panels"][0]["source"] = "nope.svg"
    _expect_error(tmp_path, m, "not found")


def test_bad_source_extension(tmp_path):
    (tmp_path / "p.docx").write_text("x")
    def m(s): s["panels"][0]["source"] = "p.docx"
    _expect_error(tmp_path, m, ".svg/.ai/.pdf/.eps")


def test_frame_exceeds_canvas(tmp_path):
    def m(s): s["panels"][0]["frame"]["w"] = 500
    _expect_error(tmp_path, m, "exceeds")


def test_stretching_rejected(tmp_path):
    def m(s): s["panels"][0]["fit"] = "stretch"
    _expect_error(tmp_path, m, "contain")


def test_output_must_be_ai(tmp_path):
    def m(s): s["output"]["ai"] = "fig.pdf"
    _expect_error(tmp_path, m, ".ai")


def test_bad_export_format(tmp_path):
    def m(s): s["output"]["exports"][0]["format"] = "tiff"
    _expect_error(tmp_path, m, "format")


def test_validation_collects_multiple_errors(tmp_path):
    spec = good_spec(tmp_path)
    spec["version"] = 3
    spec["panels"][0]["frame"]["w"] = -1
    errs = validate_spec(spec, str(tmp_path))
    assert len(errs) >= 2
