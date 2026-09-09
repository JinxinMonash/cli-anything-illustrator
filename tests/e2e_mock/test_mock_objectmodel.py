"""Expanded object-model templates executed against the Node mock DOM.

The CLI has no subcommands for these ops yet (they are wired upstream), so
each test drives the REAL template through the same path the backend uses:
``build_script`` assembles prelude + params + template, and the assembled
program runs in the mock runner (``tests/mocks/run_jsx.js``) as a separate
node process per op, persisting state via $MOCK_AI_STATE -- exactly how the
fake ``osascript`` executes scripts for the CLI e2e tests.

NOT live-Illustrator evidence (see tests/integration/).
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from cli_anything.illustrator.backend.base import build_script

MOCKS = Path(__file__).parent.parent / "mocks"
node = shutil.which("node")
pytestmark = pytest.mark.skipif(node is None, reason="node required for mock")


class OpRunner:
    """Executes one JSX op per node process against persistent mock state."""

    def __init__(self, tmp_path):
        self.tmp = tmp_path
        self.env = dict(os.environ)
        self.env["MOCK_AI_STATE"] = str(tmp_path / "mock_state.json")
        self.env.pop("MOCK_OSASCRIPT_MODE", None)
        self._n = 0

    def raw(self, op, params=None):
        self._n += 1
        jsx = self.tmp / f"op_{self._n}_{op}.js"
        jsx.write_text(build_script(op, params or {}), encoding="utf-8")
        proc = subprocess.run(
            [node, str(MOCKS / "run_jsx.js"), "runner.applescript",
             str(jsx), "Adobe Illustrator", "60"],
            capture_output=True, text=True, env=self.env, timeout=60,
        )
        assert proc.returncode == 0, f"{op}: {proc.stderr}"
        return json.loads(proc.stdout)

    def ok(self, op, params=None):
        env = self.raw(op, params)
        assert env["ok"], f"{op} failed: {env.get('error')}"
        return env["result"]

    def err(self, op, params=None):
        env = self.raw(op, params)
        assert not env["ok"], f"{op} unexpectedly succeeded: {env.get('result')}"
        return env["error"]


@pytest.fixture
def ops(tmp_path):
    r = OpRunner(tmp_path)
    r.ok("doc_new", {"width": 400, "height": 300})
    return r


# ------------------------------------------------------------- bezier paths
def test_path_add_bezier_roundtrip_canvas_coords(ops):
    res = ops.ok("path_add", {
        "anchors": [[10, 20], [100, 40], [180, 120]],
        "left_handles": [None, [80, 10], None],
        "right_handles": [None, [120, 70], None],
        "closed": False,
        "stroke": [0, 0, 0], "stroke_width": 2, "name": "bez",
    })
    assert res["type"] == "path" and res["name"] == "bez"
    assert res["closed"] is False
    assert res["anchor_count"] == 3
    a = res["anchors"]
    assert a[0]["anchor"] == pytest.approx([10, 20])
    assert a[1]["anchor"] == pytest.approx([100, 40])
    assert a[1]["left"] == pytest.approx([80, 10])
    assert a[1]["right"] == pytest.approx([120, 70])
    assert a[1]["type"] == "smooth"
    # handles default to the anchor -> corner point
    assert a[0]["type"] == "corner"
    assert a[0]["left"] == pytest.approx([10, 20])
    assert res["stroke"]["type"] == "rgb"
    assert res["stroke_width"] == 2


def test_path_add_persists_across_processes(ops):
    ops.ok("path_add", {
        "anchors": [[0, 0], [50, 0], [50, 50]],
        "left_handles": [None, [40, -10], None],
        "right_handles": [None, [60, 10], None],
        "closed": True, "fill": [200, 10, 10], "name": "tri",
    })
    # separate node process: geometry must round-trip through $MOCK_AI_STATE
    res = ops.ok("inspect_paths", {"selector": {"name": "tri"}})
    assert res["total_matches"] == 1
    p = res["paths"][0]
    assert p["closed"] is True
    assert p["anchors"][1]["anchor"] == pytest.approx([50, 0])
    assert p["anchors"][1]["left"] == pytest.approx([40, -10])
    assert p["anchors"][1]["type"] == "smooth"
    assert p["fill"] == {"type": "rgb", "rgb": [200, 10, 10]}


def test_path_add_rejects_single_anchor(ops):
    err = ops.err("path_add", {"anchors": [[10, 10]]})
    assert err["code"] == "BAD_PARAMS"


def test_path_edit_moves_anchor_and_drags_handles(ops):
    ops.ok("path_add", {
        "anchors": [[0, 0], [100, 0]],
        "left_handles": [None, [80, -20]],
        "right_handles": [None, [120, 20]],
        "closed": False, "name": "seg",
    })
    res = ops.ok("path_edit", {
        "selector": {"name": "seg"},
        "points": [{"index": 1, "anchor": [110, 10]}],
    })
    a = res["anchors"][1]
    assert a["anchor"] == pytest.approx([110, 10])
    # handles translated by the same delta (+10, +10)
    assert a["left"] == pytest.approx([90, -10])
    assert a["right"] == pytest.approx([130, 30])


def test_path_edit_sets_handles_and_point_type(ops):
    ops.ok("path_add", {"anchors": [[0, 0], [100, 0]], "closed": False,
                        "name": "seg2"})
    res = ops.ok("path_edit", {
        "selector": {"name": "seg2"},
        "points": [{"index": 0, "left": [-20, -20], "right": [20, 20],
                    "point_type": "smooth"}],
        "closed": True,
    })
    assert res["closed"] is True
    assert res["anchors"][0]["left"] == pytest.approx([-20, -20])
    assert res["anchors"][0]["type"] == "smooth"


def test_path_edit_point_index_out_of_range(ops):
    ops.ok("path_add", {"anchors": [[0, 0], [10, 10]], "name": "p2"})
    err = ops.err("path_edit", {"selector": {"name": "p2"},
                                "points": [{"index": 5, "anchor": [1, 1]}]})
    assert err["code"] == "BAD_PARAMS"
    assert "out of range" in err["message"]


# --------------------------------------------------------- compound + clip
def test_compound_make_combines_paths(ops):
    ops.ok("shape_add", {"kind": "rect", "x": 0, "y": 0, "w": 50, "h": 50,
                         "name": "ring", "fill": [0, 0, 0]})
    ops.ok("shape_add", {"kind": "ellipse", "x": 10, "y": 10, "w": 30, "h": 30,
                         "name": "ring", "fill": [255, 255, 255]})
    res = ops.ok("compound_make", {"selector": {"name": "ring"}, "name": "donut"})
    assert res["type"] == "compound"
    assert res["path_count"] == 2
    rep = ops.ok("doc_report", {})
    assert rep["compound_paths"] == 1
    assert rep["editability"]["path_items"] == 2  # members still counted


def test_compound_make_needs_two_paths(ops):
    ops.ok("shape_add", {"kind": "rect", "x": 0, "y": 0, "w": 10, "h": 10,
                         "name": "solo"})
    err = ops.err("compound_make", {"selector": {"name": "solo"}})
    assert err["code"] == "BAD_PARAMS"


def test_clip_make_reports_clip_bounds(ops):
    ops.ok("shape_add", {"kind": "rect", "x": 0, "y": 0, "w": 200, "h": 150,
                         "name": "cm", "fill": [0, 100, 200]})
    # added second -> topmost -> becomes the clipping path
    ops.ok("shape_add", {"kind": "ellipse", "x": 20, "y": 30, "w": 60, "h": 40,
                         "name": "cm"})
    res = ops.ok("clip_make", {"selector": {"name": "cm"}, "name": "masked"})
    assert res["member_count"] == 2
    assert res["clipped"] is True
    cb = res["clip_bounds"]
    assert (cb["x"], cb["y"], cb["w"], cb["h"]) == pytest.approx((20, 30, 60, 40))
    # clipped group reports the clip-path bounds, and doc_report sees the mask
    assert (res["bounds"]["x"], res["bounds"]["w"]) == pytest.approx((20, 60))
    rep = ops.ok("doc_report", {})
    assert rep["editability"]["clipping_groups"] == 1
    assert rep["clipping_paths"] == 1


def test_clip_make_requires_path_on_top(ops):
    ops.ok("shape_add", {"kind": "rect", "x": 0, "y": 0, "w": 10, "h": 10,
                         "name": "t"})
    ops.ok("text_add", {"contents": "label", "x": 0, "y": 0, "name": "t"})
    err = ops.err("clip_make", {"selector": {"name": "t"}})
    assert err["code"] == "BAD_PARAMS"
    assert "path" in err["message"]


# --------------------------------------------------------------- gradients
def test_gradient_add_and_inspect_roundtrip(ops):
    res = ops.ok("gradient_add", {
        "name": "heat", "type": "radial",
        "stops": [
            {"offset": 0, "color": [0, 0, 128]},
            {"offset": 55, "color": [255, 200, 0], "midpoint": 60, "opacity": 80},
            {"offset": 100, "color": [255, 0, 0]},
        ],
    })
    assert res["type"] == "radial" and res["replaced"] is False
    inv = ops.ok("inspect_gradients", {})  # separate process: round-trip
    assert inv["gradients_defined"] == 1
    g = inv["gradients"][0]
    assert g["name"] == "heat" and g["type"] == "radial" and g["stop_count"] == 3
    assert g["stops"][1]["offset"] == 55
    assert g["stops"][1]["midpoint"] == 60
    assert g["stops"][1]["opacity"] == 80
    assert g["stops"][1]["color"] == {"type": "rgb", "rgb": [255, 200, 0]}


def test_gradient_add_duplicate_then_replace(ops):
    stops = [{"offset": 0, "color": [0, 0, 0]}, {"offset": 100, "color": [255, 255, 255]}]
    ops.ok("gradient_add", {"name": "g1", "type": "linear", "stops": stops})
    err = ops.err("gradient_add", {"name": "g1", "type": "linear", "stops": stops})
    assert err["code"] == "GRADIENT_EXISTS"
    res = ops.ok("gradient_add", {"name": "g1", "type": "radial", "stops": stops,
                                  "replace": True})
    assert res["replaced"] is True and res["type"] == "radial"
    assert ops.ok("inspect_gradients", {})["gradients_defined"] == 1


def test_gradient_apply_fill_and_readback(ops):
    ops.ok("gradient_add", {"name": "fade", "type": "linear", "stops": [
        {"offset": 0, "color": [255, 255, 255]}, {"offset": 100, "color": [0, 0, 0]}]})
    ops.ok("shape_add", {"kind": "rect", "x": 10, "y": 10, "w": 80, "h": 40,
                         "name": "panelbg"})
    res = ops.ok("gradient_apply", {"gradient": "fade", "angle": 45,
                                    "origin": [10, 10], "length": 80,
                                    "selector": {"name": "panelbg"}})
    assert res["gradient"] == "fade" and res["angle"] == 45
    assert res["items"][0]["paths_painted"] == 1
    ins = ops.ok("inspect_paths", {"selector": {"name": "panelbg"}})
    fill = ins["paths"][0]["fill"]
    assert fill["type"] == "gradient"
    assert fill["gradient"] == "fade"
    assert fill["angle"] == 45
    rep = ops.ok("doc_report", {})
    assert rep["editability"]["gradients_defined"] == 1


def test_gradient_apply_unknown_gradient(ops):
    ops.ok("shape_add", {"kind": "rect", "x": 0, "y": 0, "w": 10, "h": 10,
                         "name": "r"})
    err = ops.err("gradient_apply", {"gradient": "nope", "selector": {"name": "r"}})
    assert err["code"] == "GRADIENT_NOT_FOUND"


# ------------------------------------------------------------------- style
def test_style_set_stroke_style_roundtrip(ops):
    ops.ok("shape_add", {"kind": "rect", "x": 0, "y": 0, "w": 100, "h": 50,
                         "name": "frame"})
    res = ops.ok("style_set", {
        "selector": {"name": "frame"},
        "stroke": [10, 20, 30], "stroke_width": 1.5,
        "cap": "round", "join": "bevel", "miter_limit": 8,
        "dash": [4, 2], "dash_offset": 1, "opacity": 70,
    })
    assert res["updated"] == 1 and res["items"][0]["paths_styled"] == 1
    p = ops.ok("inspect_paths", {"selector": {"name": "frame"}})["paths"][0]
    assert p["cap"] == "round"
    assert p["join"] == "bevel"
    assert p["dash"] == [4, 2]
    assert p["dash_offset"] == 1
    assert p["miter_limit"] == 8
    assert p["stroke_width"] == 1.5
    assert p["opacity"] == 70
    assert p["stroke"] == {"type": "rgb", "rgb": [10, 20, 30]}


def test_style_set_fill_none_and_group_descent(ops):
    ops.ok("shape_add", {"kind": "rect", "x": 0, "y": 0, "w": 10, "h": 10,
                         "name": "m", "fill": [1, 2, 3]})
    ops.ok("shape_add", {"kind": "rect", "x": 20, "y": 0, "w": 10, "h": 10,
                         "name": "m", "fill": [1, 2, 3]})
    ops.ok("group_make", {"selector": {"name": "m"}, "name": "grp"})
    res = ops.ok("style_set", {"selector": {"name": "grp"}, "fill": "none"})
    assert res["items"][0]["paths_styled"] == 2
    ins = ops.ok("inspect_paths", {})
    assert all(p["fill"]["type"] == "none" for p in ins["paths"])


# -------------------------------------------------------------- transforms
def test_transform_translate_canvas_y_down(ops):
    ops.ok("shape_add", {"kind": "rect", "x": 10, "y": 10, "w": 40, "h": 20,
                         "name": "r"})
    res = ops.ok("transform_apply", {"selector": {"name": "r"}, "dx": 5, "dy": 7})
    b = res["items"][0]["after"]["bounds"]
    assert (b["x"], b["y"], b["w"], b["h"]) == pytest.approx((15, 17, 40, 20))


def test_transform_scale_topleft_and_stroke_preservation(ops):
    ops.ok("shape_add", {"kind": "rect", "x": 10, "y": 10, "w": 40, "h": 20,
                         "name": "r", "stroke": [0, 0, 0], "stroke_width": 2})
    res = ops.ok("transform_apply", {"selector": {"name": "r"}, "scale_x": 200,
                                     "about": "topleft", "preserve_strokes": True})
    b = res["items"][0]["after"]["bounds"]
    assert (b["x"], b["y"], b["w"], b["h"]) == pytest.approx((10, 10, 80, 40))
    p = ops.ok("inspect_paths", {"selector": {"name": "r"}})["paths"][0]
    assert p["stroke_width"] == 2  # preserved
    ops.ok("transform_apply", {"selector": {"name": "r"}, "scale_x": 50,
                               "about": "topleft"})
    p = ops.ok("inspect_paths", {"selector": {"name": "r"}})["paths"][0]
    assert p["stroke_width"] == pytest.approx(1)  # scaled with geometry


def test_transform_rotate_90_about_center_swaps_extent(ops):
    ops.ok("shape_add", {"kind": "rect", "x": 10, "y": 10, "w": 40, "h": 20,
                         "name": "r"})
    res = ops.ok("transform_apply", {"selector": {"name": "r"}, "rotate": 90,
                                     "about": "center"})
    b = res["items"][0]["after"]["bounds"]
    assert (b["w"], b["h"]) == pytest.approx((20, 40))
    # center preserved: (30, 20)
    assert (b["x"] + b["w"] / 2, b["y"] + b["h"] / 2) == pytest.approx((30, 20))


def test_transform_rotates_bezier_anchors(ops):
    ops.ok("path_add", {"anchors": [[0, 0], [100, 0]], "name": "seg"})
    ops.ok("transform_apply", {"selector": {"name": "seg"}, "rotate": 90,
                               "about": "topleft"})
    a = ops.ok("inspect_paths", {"selector": {"name": "seg"}})["paths"][0]["anchors"]
    # AI rotation is counter-clockwise (y-up): (100,0)canvas rotates to (0,-100)canvas
    assert a[1]["anchor"] == pytest.approx([0, -100], abs=1e-9)


# -------------------------------------------------------------- text attrs
def test_text_update_typography_and_inspect(ops):
    ops.ok("text_add", {"contents": "Figure 1", "x": 20, "y": 30, "size": 10,
                        "name": "cap"})
    res = ops.ok("text_update", {"selector": {"name": "cap"}, "updates": {
        "tracking": 25, "leading": 14, "justification": "center", "size": 12}})
    after = res["items"][0]["after"]
    assert after["tracking"] == 25
    assert after["leading"] == 14
    assert after["auto_leading"] is False
    assert after["justification"] == "center"
    ins = ops.ok("inspect_text", {"selector": {"name": "cap"}})  # new process
    f = ins["frames"][0]
    assert f["contents_full"] == "Figure 1"
    assert f["size"] == 12 and f["tracking"] == 25 and f["leading"] == 14
    assert f["justification"] == "center"
    assert f["kind"] == "point"
    assert f["font"]["family"] == "Helvetica"


def test_area_text_resize_and_point_text_rejection(ops):
    ops.ok("text_add", {"contents": "legend text", "kind": "area",
                        "x": 10, "y": 10, "box_w": 100, "box_h": 50,
                        "name": "leg"})
    ops.ok("text_update", {"selector": {"name": "leg"},
                           "updates": {"width": 140, "height": 60}})
    f = ops.ok("inspect_text", {"selector": {"name": "leg"}})["frames"][0]
    assert f["kind"] == "area"
    assert (f["bounds"]["w"], f["bounds"]["h"]) == pytest.approx((140, 60))
    ops.ok("text_add", {"contents": "pt", "x": 0, "y": 0, "name": "pt"})
    err = ops.err("text_update", {"selector": {"name": "pt"},
                                  "updates": {"width": 50}})
    assert err["code"] == "BAD_PARAMS"


def test_text_update_rejects_bad_justification(ops):
    ops.ok("text_add", {"contents": "x", "x": 0, "y": 0, "name": "t"})
    err = ops.err("text_update", {"selector": {"name": "t"},
                                  "updates": {"justification": "justified"}})
    assert err["code"] == "BAD_PARAMS"


# -------------------------------------------------------------- inspection
def test_inspect_document_layer_tree(ops):
    ops.ok("layer_add", {"name": "Panels"})
    ops.ok("shape_add", {"kind": "rect", "x": 0, "y": 0, "w": 10, "h": 10,
                         "layer": "Panels"})
    ops.ok("text_add", {"contents": "A", "x": 0, "y": 0, "layer": "Panels"})
    res = ops.ok("inspect_document", {})
    assert res["doc"]["layers"] == 2
    by_name = {l["name"]: l for l in res["layers"]}
    assert by_name["Panels"]["item_counts"]["path"] == 1
    assert by_name["Panels"]["item_counts"]["text"] == 1
    assert by_name["Panels"]["item_counts"]["total"] == 2
    assert by_name["Layer 1"]["item_counts"]["total"] == 0


def test_inspect_colors_unique_counts(ops):
    ops.ok("shape_add", {"kind": "rect", "x": 0, "y": 0, "w": 10, "h": 10,
                         "fill": [255, 0, 0]})
    ops.ok("shape_add", {"kind": "rect", "x": 20, "y": 0, "w": 10, "h": 10,
                         "fill": [255, 0, 0], "stroke": [0, 0, 255]})
    ops.ok("text_add", {"contents": "t", "x": 0, "y": 40, "color": [255, 0, 0]})
    ops.ok("text_add", {"contents": "u", "x": 0, "y": 60})  # default black text
    res = ops.ok("inspect_colors", {})
    assert res["unique_colors"] == 3  # red, blue, default text black
    red = next(c for c in res["colors"]
               if c["color"] == {"type": "rgb", "rgb": [255, 0, 0]})
    assert red["fill_count"] == 2 and red["text_count"] == 1
    blue = next(c for c in res["colors"]
                if c["color"] == {"type": "rgb", "rgb": [0, 0, 255]})
    assert blue["stroke_count"] == 1


def test_doc_report_editability_block(ops):
    ops.ok("shape_add", {"kind": "rect", "x": 0, "y": 0, "w": 10, "h": 10})
    ops.ok("text_add", {"contents": "x", "x": 0, "y": 20})
    ops.ok("gradient_add", {"name": "g", "stops": [
        {"offset": 0, "color": [0, 0, 0]}, {"offset": 100, "color": [9, 9, 9]}]})
    ed = ops.ok("doc_report", {})["editability"]
    assert ed == {"text_frames": 1, "path_items": 1, "raster_items": 0,
                  "placed_items": 0, "gradients_defined": 1,
                  "clipping_groups": 0, "locked_items": 0, "hidden_items": 0}


def test_inspect_paths_anchor_limit(ops):
    ops.ok("path_add", {"anchors": [[i * 10, 0] for i in range(6)], "name": "long"})
    p = ops.ok("inspect_paths", {"selector": {"name": "long"}, "limit": 3})["paths"][0]
    assert p["anchor_count"] == 6
    assert len(p["anchors"]) == 3
    assert p["anchors_truncated"] is True
