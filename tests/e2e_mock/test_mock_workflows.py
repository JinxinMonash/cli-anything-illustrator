"""End-to-end CLI workflows against the Node mock Illustrator DOM.

These exercise the REAL pipeline -- console script, JSON parameter envelope,
JSX assembly, prelude logic (targeting, selectors, coordinates), transport,
envelope parsing, exit codes -- with only Illustrator itself replaced by a
mock. They are NOT live-Illustrator evidence (see tests/integration/).
"""
import json
import os
import shutil

import pytest

node_missing = shutil.which("node") is None
pytestmark = pytest.mark.skipif(node_missing, reason="node required for mock")

GREEK = "Δ conc. (µM) — αβγ ≥ 10 \"quoted\" 'single'"


# ---------------------------------------------------------------- basics
def test_ping_roundtrip(mock_cli):
    _, out = mock_cli.run("app", "launch")
    assert out["ok"] and out["result"]["pong"] is True


def test_app_info(mock_cli):
    _, out = mock_cli.run("app", "info")
    assert out["result"]["version"].startswith("29.")
    assert out["result"]["font_count"] >= 5


def test_doc_new_info_and_canvas_size(mock_cli):
    _, out = mock_cli.run("doc", "new", "--width", "180", "--height", "120",
                          "--units", "mm", "--base-layer", "Panels")
    r = out["result"]
    assert abs(r["width"] - 180 * 72 / 25.4) < 0.01
    assert r["color_space"].endswith("RGB")
    _, out = mock_cli.run("doc", "info")
    assert out["result"]["layers"] == 1


# ---------------------------------------------------------------- text
def test_text_add_unicode_and_readback(mock_cli):
    mock_cli.run("doc", "new")
    _, out = mock_cli.run("text", "add", GREEK, "--x", "30", "--y", "40",
                          "--size", "14", "--item-name", "greek_label")
    assert out["result"]["contents_full"] == GREEK
    assert out["result"]["uuid"]
    _, out = mock_cli.run("text", "list")
    items = out["result"]["items"]
    assert out["result"]["total_matches"] == 1
    assert items[0]["name"] == "greek_label"
    assert GREEK.startswith(items[0]["contents"][:20])


def test_text_position_uses_canvas_coordinates(mock_cli):
    mock_cli.run("doc", "new", "--width", "100", "--height", "100")
    _, out = mock_cli.run("text", "add", "hi", "--x", "10", "--y", "20")
    b = out["result"]["bounds"]  # canvas coords: origin top-left, y down
    assert abs(b["x"] - 10) < 0.01
    assert abs(b["y"] - (20 - 12)) < 0.5  # point-text cap ~size above baseline


def test_text_update_by_name(mock_cli):
    mock_cli.run("doc", "new")
    mock_cli.run("text", "add", "old", "--x", "0", "--y", "10",
                 "--item-name", "t1")
    _, out = mock_cli.run("text", "update", "--name", "t1",
                          "--set-contents", "new content", "--set-size", "18")
    assert out["result"]["updated"] == 1
    assert out["result"]["items"][0]["after"]["contents_full"] == "new content"


def test_font_not_found_vs_substitute(mock_cli):
    mock_cli.run("doc", "new")
    proc, out = mock_cli.run("text", "add", "x", "--x", "0", "--y", "0",
                             "--font", "NoSuchFont-Bold", expect_exit=6)
    assert out["error"]["code"] == "FONT_NOT_FOUND"
    _, out = mock_cli.run("text", "add", "x", "--x", "0", "--y", "0",
                          "--font", "NoSuchFont-Bold", "--allow-font-substitute")
    assert out["result"]["font_substituted"] is True
    # family-name resolution counts as a (visible) inexact match
    _, out = mock_cli.run("text", "add", "y", "--x", "0", "--y", "0",
                          "--font", "Helvetica")
    assert out["result"]["font"]["exact"] is True


# ---------------------------------------------------------------- targeting
def test_ambiguous_document_rejected(mock_cli):
    mock_cli.run("doc", "new")
    mock_cli.run("doc", "new")
    proc, out = mock_cli.run("doc", "info", expect_exit=5)
    assert out["error"]["code"] == "AMBIGUOUS_DOCUMENT"
    assert len(out["error"]["details"]["open_documents"]) == 2
    _, out = mock_cli.run("doc", "list")
    name = out["result"]["documents"][0]["name"]
    _, out = mock_cli.run("doc", "info", "--doc", name)
    assert out["result"]["name"] == name


def test_no_document_error(mock_cli):
    proc, out = mock_cli.run("doc", "info", expect_exit=5)
    assert out["error"]["code"] == "NO_DOCUMENT"


def test_selector_ambiguity_rejected(mock_cli):
    mock_cli.run("doc", "new")
    for _ in range(2):
        mock_cli.run("shape", "rect", "--x", "0", "--y", "0", "--w", "10",
                     "--h", "10", "--item-name", "twin")
    proc, out = mock_cli.run("object", "move", "--name", "twin",
                             "--to", "5", "5", expect_exit=6)
    assert out["error"]["code"] == "SELECTOR_AMBIGUOUS"
    _, out = mock_cli.run("object", "move", "--name", "twin", "--to", "5", "5",
                          "--all")
    assert out["result"]["updated"] == 2


def test_uuid_targeting(mock_cli):
    mock_cli.run("doc", "new")
    _, out = mock_cli.run("shape", "rect", "--x", "1", "--y", "2", "--w", "3",
                          "--h", "4")
    uuid = out["result"]["uuid"]
    _, out = mock_cli.run("object", "rename", "fresh-name", "--uuid", uuid)
    assert out["result"]["items"][0]["after"]["name"] == "fresh-name"


def test_delete_requires_confirm(mock_cli):
    mock_cli.run("doc", "new")
    mock_cli.run("shape", "rect", "--x", "0", "--y", "0", "--w", "5", "--h", "5",
                 "--item-name", "victim")
    proc, out = mock_cli.run("object", "delete", "--name", "victim",
                             expect_exit=6)
    assert out["error"]["code"] == "CONFIRM_REQUIRED"
    _, out = mock_cli.run("object", "delete", "--name", "victim", "--confirm")
    assert out["result"]["deleted"] == 1


# ---------------------------------------------------------------- layers
def test_layer_lifecycle_and_guards(mock_cli):
    mock_cli.run("doc", "new")
    mock_cli.run("layer", "add", "Annotations")
    _, out = mock_cli.run("layer", "list")
    assert [l["name"] for l in out["result"]["layers"]] == ["Annotations", "Layer 1"]
    mock_cli.run("text", "add", "note", "--x", "0", "--y", "0",
                 "--layer", "Annotations")
    proc, out = mock_cli.run("layer", "remove", "Annotations", expect_exit=6)
    assert out["error"]["code"] == "LAYER_NOT_EMPTY"
    mock_cli.run("layer", "remove", "Annotations", "--force")
    proc, out = mock_cli.run("layer", "remove", "Ghost", expect_exit=6)
    assert out["error"]["code"] == "LAYER_NOT_FOUND"
    mock_cli.run("layer", "rename", "Layer 1", "Base")
    _, out = mock_cli.run("layer", "list")
    assert out["result"]["layers"][0]["name"] == "Base"


# ---------------------------------------------------------------- files
def test_save_close_reopen_preserves_text(mock_cli, tmp_path):
    target = tmp_path / "dir with spaces" / "fïgure ω.ai"
    mock_cli.run("doc", "new")
    mock_cli.run("text", "add", GREEK, "--x", "5", "--y", "5",
                 "--item-name", "keeper")
    _, out = mock_cli.run("doc", "save-as", str(target))
    assert out["result"]["saved"] is True
    assert os.path.isfile(target)
    mock_cli.run("doc", "close")
    _, out = mock_cli.run("doc", "open", str(target))
    assert out["result"]["text_frames"] == 1
    _, out = mock_cli.run("text", "list")
    assert out["result"]["items"][0]["name"] == "keeper"


def test_save_overwrite_guard(mock_cli, tmp_path):
    target = tmp_path / "master.ai"
    target.write_text("PRECIOUS")
    mock_cli.run("doc", "new")
    proc, out = mock_cli.run("doc", "save-as", str(target), expect_exit=8)
    assert out["error"]["code"] == "OVERWRITE_REFUSED"
    assert target.read_text() == "PRECIOUS"  # nothing touched the file
    mock_cli.run("doc", "save-as", str(target), "--overwrite")
    assert target.read_text().startswith("%!MOCK-AI")


def test_close_refuses_unsaved_changes(mock_cli):
    mock_cli.run("doc", "new")
    mock_cli.run("text", "add", "unsaved", "--x", "0", "--y", "0")
    proc, out = mock_cli.run("doc", "close", expect_exit=6)
    assert out["error"]["code"] == "UNSAVED_CHANGES"
    mock_cli.run("doc", "close", "--discard-changes")
    proc, out = mock_cli.run("doc", "list")
    assert out["result"]["count"] == 0


def test_save_as_rejects_non_ai_extension(mock_cli):
    proc, out = mock_cli.run("doc", "save-as", "out.pdf", expect_exit=2)


# ---------------------------------------------------------------- failure modes
def test_permission_denied_maps_to_exit_4(mock_cli):
    mock_cli.env["MOCK_OSASCRIPT_MODE"] = "denied"
    proc, out = mock_cli.run("doc", "list", expect_exit=4)
    assert out["error"]["code"] == "AUTOMATION_DENIED"
    assert "Privacy & Security" in out["error"]["message"]


def test_app_missing_maps_to_exit_3(mock_cli):
    mock_cli.env["MOCK_OSASCRIPT_MODE"] = "appmissing"
    proc, out = mock_cli.run("doc", "list", expect_exit=3)
    assert out["error"]["code"] == "APP_MISSING"


def test_no_session_maps_to_exit_3(mock_cli):
    mock_cli.env["MOCK_OSASCRIPT_MODE"] = "nosession"
    proc, out = mock_cli.run("doc", "list", expect_exit=3)
    assert out["error"]["code"] == "SESSION_UNAVAILABLE"


def test_garbage_output_maps_to_script_error(mock_cli):
    mock_cli.env["MOCK_OSASCRIPT_MODE"] = "garbage"
    proc, out = mock_cli.run("doc", "list", expect_exit=6)
    assert out["error"]["code"] == "SCRIPT_ERROR"


def test_timeout_maps_to_exit_7(mock_cli):
    mock_cli.env["MOCK_OSASCRIPT_MODE"] = "timeout"
    proc, out = mock_cli.run("--timeout", "1", "doc", "list", expect_exit=7,
                             timeout=120)
    assert out["error"]["code"] == "TIMEOUT"
    assert "Inspect document state" in out["error"]["message"]


# ---------------------------------------------------------------- operation log
def test_operation_record_written(mock_cli):
    mock_cli.run("doc", "new")
    log = mock_cli.env["CAI_LOG_FILE"]
    rows = [json.loads(l) for l in open(log)]
    assert rows and rows[-1]["command"] == "doc new" and rows[-1]["ok"]
