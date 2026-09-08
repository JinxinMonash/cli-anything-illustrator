"""Script assembly: parameter safety and envelope parsing."""
import json

import pytest

from cli_anything.illustrator.backend.base import build_script, parse_envelope
from cli_anything.illustrator.errors import OpError, ScriptError

TRICKY = {
    "contents": 'He said "hi\\" -- \'quotes\', newline:\nGreek: αβγ Δδ µ ± ≥ 10 µm',
    "path": "/tmp/dir with spaces/ütf-8 ñame.ai",
    "size": 12.5,
    "flag": True,
    "nothing": None,
    "nested": {"list": [1, 2, "three"], "omega": "Ω"},
}


def test_params_embedded_ascii_only_and_recoverable():
    script = build_script("ping", TRICKY)
    line = next(l for l in script.splitlines() if l.startswith("var __PARAMS_JSON"))
    assert line == line.encode("ascii", "strict").decode()  # pure ASCII
    literal = line.split("=", 1)[1].strip().rstrip(";")
    inner = json.loads(literal)          # JS string literal == JSON string
    assert json.loads(inner) == TRICKY   # full round trip
    # user text can never terminate the literal: the raw quote from the
    # contents must not appear unescaped
    assert 'He said "hi' not in script


def test_script_contains_prelude_and_op():
    script = build_script("doc_new", {"width": 100, "height": 50})
    assert "var CAI = (function" in script
    assert "app.documents.add" in script


def test_unknown_op_raises():
    with pytest.raises(FileNotFoundError):
        build_script("no_such_op", {})


def test_parse_envelope_ok():
    assert parse_envelope('{"ok": true, "result": {"x": 1}}') == {"x": 1}


def test_parse_envelope_error_maps_to_op_error():
    with pytest.raises(OpError) as ei:
        parse_envelope('{"ok": false, "error": {"code": "NO_DOCUMENT", "message": "m"}}')
    assert ei.value.code == "NO_DOCUMENT"
    assert ei.value.exit_code == 5


def test_parse_envelope_garbage_and_empty():
    with pytest.raises(ScriptError):
        parse_envelope("not json")
    with pytest.raises(ScriptError):
        parse_envelope("")
    with pytest.raises(ScriptError):
        parse_envelope('{"no_ok_key": 1}')
