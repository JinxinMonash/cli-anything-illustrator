"""Unit tests for structural editability scoring (stdlib-only module)."""

import pytest

from cli_anything.illustrator.fidelity.editability import score_editability


def _clean_report(**over):
    rep = {
        "name": "figure1.ai",
        "width": 612, "height": 792,
        "artboards": 1,
        "layers": 3,
        "page_items": 12,
        "text_frames": 5,
        "placed_items": 0,
        "raster_items": 0,
        "legacy_text_items": 0,
        "compound_paths": 1,
        "clipping_paths": 2,
        "fonts_used": [
            {"font": "Helvetica", "text_frames": 5,
             "available_in_app": True}],
        "fonts_unavailable": [],
        "placed_links": [],
        "locked_layers": [],
        "hidden_layers": [],
        "warnings": [],
    }
    rep.update(over)
    return rep


def test_clean_report_passes():
    res = score_editability(_clean_report())
    assert res["editability_status"] == "PASS"
    assert res["reasons"] == []
    assert res["live_text"] == 5
    assert res["text_objects"] == 5
    assert res["vector_objects"] == 7   # 12 - 5 text
    assert res["rasterized_regions"] == 0
    assert res["clipping_groups"] == 2
    assert res["layers"] == {"count": 3, "locked": [], "hidden": []}
    assert res["gradients"] is None     # no count in the report


def test_raster_present_warns():
    res = score_editability(_clean_report(raster_items=2, page_items=14))
    assert res["editability_status"] == "WARN"
    assert res["rasterized_regions"] == 2
    assert any("rasterized" in r.lower() for r in res["reasons"])


def test_unavailable_fonts_warn():
    res = score_editability(
        _clean_report(fonts_unavailable=["MyriadPro-Regular"]))
    assert res["editability_status"] == "WARN"
    assert any("MyriadPro-Regular" in r for r in res["reasons"])


def test_raster_only_document_fails():
    res = score_editability(_clean_report(
        text_frames=0, raster_items=3, page_items=3))
    assert res["editability_status"] == "FAIL"
    assert res["live_text"] == 0
    assert res["vector_objects"] == 0
    assert any("not" in r and "editable" in r for r in res["reasons"])


def test_empty_document_fails():
    res = score_editability(_clean_report(
        page_items=0, text_frames=0, clipping_paths=0))
    assert res["editability_status"] == "FAIL"
    assert any("no page items" in r for r in res["reasons"])


def test_legacy_only_text_fails():
    res = score_editability(_clean_report(
        text_frames=0, legacy_text_items=4, page_items=7))
    assert res["editability_status"] == "FAIL"
    assert res["text_objects"] == 4
    assert any("legacy" in r for r in res["reasons"])


def test_legacy_plus_live_text_warns():
    res = score_editability(_clean_report(legacy_text_items=1))
    assert res["editability_status"] == "WARN"
    assert res["live_text"] == 5
    assert res["text_objects"] == 6
    assert any("legacy" in r for r in res["reasons"])


def test_missing_links_warn():
    res = score_editability(_clean_report(
        placed_items=1,
        placed_links=[{"name": "chart.pdf", "missing": True,
                       "file": None}]))
    assert res["editability_status"] == "WARN"
    assert any("chart.pdf" in r for r in res["reasons"])


def test_locked_and_hidden_layers_warn():
    res = score_editability(_clean_report(
        locked_layers=["annotations"], hidden_layers=["draft"]))
    assert res["editability_status"] == "WARN"
    assert res["layers"]["locked"] == ["annotations"]
    assert res["layers"]["hidden"] == ["draft"]
    assert sum(1 for r in res["reasons"]
               if "locked" in r or "hidden" in r) == 2


def test_editability_block_takes_precedence():
    res = score_editability(_clean_report(editability={
        "vector_objects": 9, "gradients": 4, "clipping_groups": 1,
        "rasterized_regions": 0, "live_text": 5}))
    assert res["vector_objects"] == 9
    assert res["gradients"] == 4
    assert res["clipping_groups"] == 1
    assert res["editability_status"] == "PASS"


def test_absent_editability_block_handled():
    rep = _clean_report()
    assert "editability" not in rep
    res = score_editability(rep)
    assert res["editability_status"] == "PASS"
    assert res["gradients"] is None


def test_empty_report_warns_not_crashes():
    res = score_editability({})
    assert res["editability_status"] == "WARN"
    assert res["live_text"] is None
    assert res["vector_objects"] is None
    assert any("empty" in r for r in res["reasons"])
    res2 = score_editability(None)
    assert res2["editability_status"] == "WARN"


def test_partial_report_without_counts_warns():
    res = score_editability({"name": "x.ai", "fonts_unavailable": []})
    assert res["editability_status"] == "WARN"
    assert any("lacks item counts" in r for r in res["reasons"])
