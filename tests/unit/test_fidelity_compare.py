"""Unit tests for the fidelity visual-comparison engine.

Synthetic image pairs are built at test time with Pillow; assertions cover
metric behaviour (identical images score ~1.0), localization of a shifted
rectangle, colour-only-change classification, text-region classification,
registration tolerance, artifact generation and region->object mapping.
"""

import os

import pytest

pytest.importorskip("numpy")
PIL_Image = pytest.importorskip("PIL.Image")
from PIL import ImageDraw

from cli_anything.illustrator.fidelity.compare import (
    compare_images,
    map_regions_to_objects,
)

W, H = 512, 384
RECT = (100, 100, 160, 140)       # black rectangle (tiles ~(1,1)-(2,2))
BLUE_RECT = (300, 200, 400, 260)  # colour-change target


def _base_image(rect_shift=0, blue_color=(20, 60, 200), with_text=True):
    im = PIL_Image.new("RGB", (W, H), (255, 255, 255))
    dr = ImageDraw.Draw(im)
    x1, y1, x2, y2 = RECT
    dr.rectangle((x1 + rect_shift, y1, x2 + rect_shift, y2),
                 fill=(0, 0, 0))
    dr.rectangle(BLUE_RECT, fill=blue_color)
    if with_text:
        for i, line in enumerate(
                ["Panel A: dose response", "n = 12, p < 0.001",
                 "mean +/- SEM", "two-way ANOVA"]):
            dr.text((66, 292 + 14 * i), line, fill=(0, 0, 0))
    return im


@pytest.fixture(scope="module")
def images(tmp_path_factory):
    d = tmp_path_factory.mktemp("cmp")
    paths = {}

    def save(name, im):
        p = str(d / (name + ".png"))
        im.save(p)
        paths[name] = p

    save("ref", _base_image())
    save("identical", _base_image())
    save("shifted", _base_image(rect_shift=12))
    save("recolored", _base_image(blue_color=(200, 30, 30)))
    save("notext", _base_image(with_text=False))
    small = _base_image().resize((int(W * 0.99), int(H * 0.99)),
                                 PIL_Image.LANCZOS)
    save("small1pct", small)
    tiny = _base_image().resize((int(W * 0.9), int(H * 0.9)),
                                PIL_Image.LANCZOS)
    save("small10pct", tiny)
    return paths


def _overlaps(bbox, target):
    return not (bbox[2] <= target[0] or bbox[0] >= target[2]
                or bbox[3] <= target[1] or bbox[1] >= target[3])


# --------------------------------------------------------------- metrics

def test_identical_images_score_one(images):
    res = compare_images(images["ref"], images["identical"])
    m = res["metrics"]
    assert m["ssim"] > 0.99
    assert m["pixel_mae"] < 0.5
    assert m["rmse"] < 0.5
    assert m["edge_similarity"] == pytest.approx(1.0)
    assert m["color_delta"] < 0.5
    assert res["largest_differences"] == []
    assert res["candidate"]["resized"] is False


def test_perturbed_images_score_below_one(images):
    res = compare_images(images["ref"], images["shifted"])
    assert res["metrics"]["ssim"] < 0.995
    assert res["metrics"]["pixel_mae"] > 0.5
    assert 0.0 <= res["metrics"]["ssim"] <= 1.0
    assert 0.0 <= res["metrics"]["edge_similarity"] <= 1.0


# ---------------------------------------------------------- localization

def test_shifted_rect_localizes_to_correct_tiles(images):
    res = compare_images(images["ref"], images["shifted"], tile=64)
    regions = res["largest_differences"]
    assert regions, "shift must produce at least one region"
    # union of the old and new rectangle position
    target = (RECT[0], RECT[1], RECT[2] + 12, RECT[3])
    top = regions[0]
    assert _overlaps(top["bbox_px"], target)
    # every reported high/med region should be near the rectangle
    for r in regions:
        if r["severity"] in ("high", "med"):
            assert _overlaps(r["bbox_px"], target)
    assert top["rank"] == 1
    assert top["severity"] in ("high", "med", "low")


def test_color_only_change_flags_color(images):
    res = compare_images(images["ref"], images["recolored"], tile=64)
    regions = res["largest_differences"]
    assert regions
    top = regions[0]
    assert _overlaps(top["bbox_px"], BLUE_RECT)
    assert top["probable_type"] == "color"


def test_text_change_flags_text(images):
    res = compare_images(images["ref"], images["notext"], tile=64)
    regions = res["largest_differences"]
    assert regions
    text_area = (60, 285, 240, 360)
    top = regions[0]
    assert _overlaps(top["bbox_px"], text_area)
    assert top["probable_type"] == "text"


def test_bbox_pt_matches_dpi_conversion(images):
    dpi = 144.0
    res = compare_images(images["ref"], images["shifted"], tile=64,
                         dpi=dpi)
    for r in res["largest_differences"]:
        for px, pt in zip(r["bbox_px"], r["bbox_pt"]):
            assert pt == pytest.approx(px * 72.0 / dpi, abs=0.02)


def test_region_cap_is_ten(images):
    res = compare_images(images["ref"], images["notext"], tile=32)
    assert len(res["largest_differences"]) <= 10


# ---------------------------------------------------------- registration

def test_registration_within_two_percent_resizes(images):
    res = compare_images(images["ref"], images["small1pct"])
    assert res["candidate"]["resized"] is True
    assert res["reference"]["width_px"] == W
    assert res["metrics"]["ssim"] > 0.5  # comparable after registration


def test_registration_beyond_two_percent_errors(images):
    with pytest.raises(ValueError):
        compare_images(images["ref"], images["small10pct"])


# ------------------------------------------------------------- artifacts

def test_heatmap_and_overlay_written(images, tmp_path):
    hm = str(tmp_path / "heat.png")
    ov = str(tmp_path / "over.png")
    res = compare_images(images["ref"], images["shifted"],
                         heatmap_png=hm, overlay_png=ov)
    assert res["artifacts"] == {"heatmap_png": hm, "overlay_png": ov}
    for p in (hm, ov):
        assert os.path.isfile(p)
        with PIL_Image.open(p) as im:
            assert im.size == (W, H)


def test_default_artifact_paths_next_to_candidate(images):
    res = compare_images(images["ref"], images["identical"])
    stem = os.path.splitext(images["identical"])[0]
    assert res["artifacts"]["heatmap_png"] == stem + "_heatmap.png"
    assert res["artifacts"]["overlay_png"] == stem + "_overlay.png"
    assert os.path.isfile(res["artifacts"]["heatmap_png"])


# ------------------------------------------------------- object mapping

def _items():
    # bounds in POINTS (items_list descriptor shape)
    return [
        {"name": "black_box", "uuid": "u1", "type": "path",
         "bounds": {"x": 75.0, "y": 75.0, "w": 45.0, "h": 30.0}},
        {"name": "blue_box", "uuid": "u2", "type": "path",
         "bounds": {"x": 225.0, "y": 150.0, "w": 75.0, "h": 45.0}},
        {"name": "caption", "uuid": "u3", "type": "text",
         "bounds": {"x": 45.0, "y": 215.0, "w": 140.0, "h": 45.0}},
    ]


def test_map_regions_picks_overlapping_object(images):
    dpi = 96.0
    res = compare_images(images["ref"], images["recolored"], dpi=dpi)
    mapped = map_regions_to_objects(res["largest_differences"],
                                    _items(), dpi=dpi)
    assert len(mapped) == len(res["largest_differences"])
    top = mapped[0]
    assert top["candidates"], "expected at least one candidate object"
    assert top["candidates"][0]["uuid"] == "u2"
    assert top["candidates"][0]["overlap_fraction"] > 0.2
    assert top["probable_type"] == "color"


def test_map_regions_accepts_px_only_and_dict_items():
    regions = [{"bbox_px": [96, 96, 192, 192]}]  # 72-144 pt at 96 dpi
    objs = {"items": [
        {"name": "hit", "uuid": "a", "type": "path",
         "bounds": {"x": 72.0, "y": 72.0, "w": 72.0, "h": 72.0}},
        {"name": "miss", "uuid": "b", "type": "path",
         "bounds": {"x": 400.0, "y": 400.0, "w": 10.0, "h": 10.0}},
    ]}
    mapped = map_regions_to_objects(regions, objs, dpi=96.0)
    assert mapped[0]["bbox_pt"] == [72.0, 72.0, 144.0, 144.0]
    cands = mapped[0]["candidates"]
    assert len(cands) == 1 and cands[0]["uuid"] == "a"
    assert cands[0]["overlap_fraction"] == pytest.approx(1.0)


def test_map_regions_requires_bbox():
    with pytest.raises(ValueError):
        map_regions_to_objects([{"severity": "high"}], [])
