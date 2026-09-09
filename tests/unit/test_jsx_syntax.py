"""Every assembled JSX program must parse as valid JavaScript.

ExtendScript is ES3; anything that fails Node's parser would certainly fail
inside Illustrator. (The reverse is checked live on the Mac.)
"""
import shutil
import subprocess
from importlib import resources

import pytest

from cli_anything.illustrator.backend.base import build_script

node = shutil.which("node")
OPS = sorted(
    p.name[:-4]
    for p in (resources.files("cli_anything.illustrator") / "jsx").iterdir()
    if p.name.endswith(".jsx") and p.name not in ("prelude.jsx",)
)


def test_all_expected_ops_present():
    expected = {"ping", "app_info", "doc_new", "doc_open", "doc_list", "doc_info",
                "doc_saveas", "doc_close", "doc_report", "layer_list", "layer_add",
                "layer_remove", "layer_set", "text_add", "text_update", "shape_add",
                "items_list", "item_update", "item_delete", "group_make",
                "align_items", "import_file", "export_png", "export_svg",
                "export_pdf", "fonts_list",
                # expanded object model (v0.10)
                "path_add", "path_edit", "compound_make", "clip_make",
                "gradient_add", "gradient_apply", "style_set", "transform_apply",
                "inspect_document", "inspect_paths", "inspect_text",
                "inspect_gradients", "inspect_colors"}
    assert expected <= set(OPS)


@pytest.mark.skipif(node is None, reason="node not available")
@pytest.mark.parametrize("op", OPS)
def test_assembled_script_is_valid_javascript(op, tmp_path):
    script = build_script(op, {"probe": 'q"uote\'s αβ'})
    f = tmp_path / f"{op}.js"
    f.write_text(script, encoding="utf-8")
    proc = subprocess.run([node, "--check", str(f)], capture_output=True, text=True)
    assert proc.returncode == 0, f"{op}: {proc.stderr}"
