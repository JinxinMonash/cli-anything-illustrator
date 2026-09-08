import os

import pytest

from cli_anything.illustrator.errors import OverwriteRefusedError, ValidationError
from cli_anything.illustrator.ops.common import (
    build_selector, prepare_output_path, rgb_triplet, to_pt,
)


def test_to_pt():
    assert to_pt(72, "pt") == 72
    assert abs(to_pt(25.4, "mm") - 72.0) < 1e-9
    assert abs(to_pt(1, "in") - 72.0) < 1e-9
    assert abs(to_pt(2.54, "cm") - 72.0) < 1e-9
    with pytest.raises(ValidationError):
        to_pt(1, "furlong")


def test_prepare_output_path_creates_dirs_and_guards(tmp_path):
    target = tmp_path / "sub dir" / "outé.ai"
    p = prepare_output_path(str(target), overwrite=False)
    assert os.path.isdir(os.path.dirname(p))
    target.write_text("existing")
    with pytest.raises(OverwriteRefusedError) as ei:
        prepare_output_path(str(target), overwrite=False)
    assert ei.value.exit_code == 8
    assert prepare_output_path(str(target), overwrite=True) == str(target)
    assert target.read_text() == "existing"  # guard itself never mutates


def test_rgb_triplet():
    assert rgb_triplet("1,2,3") == [1, 2, 3]
    assert rgb_triplet("#ff8000") == [255, 128, 0]
    for bad in ("1,2", "256,0,0", "#ff80", "red"):
        with pytest.raises(ValidationError):
            rgb_triplet(bad)


def test_build_selector():
    assert build_selector(name="a", layer="L") == {"name": "a", "layer": "L"}
    assert build_selector(index=0) == {"index": 0}
    with pytest.raises(ValidationError):
        build_selector()
    assert build_selector(required=False) == {}
