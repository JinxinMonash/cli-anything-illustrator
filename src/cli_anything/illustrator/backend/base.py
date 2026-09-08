"""Backend-independent script assembly and result parsing.

Operation logic lives in static ExtendScript templates (``jsx/``); parameters
travel as a JSON document embedded as a JS string literal (ASCII-only, escaped
by ``json.dumps``), so user-supplied text can never break out into code.
"""
from __future__ import annotations

import json
from importlib import resources

from cli_anything.illustrator.errors import OpError, ScriptError

_PKG = "cli_anything.illustrator"


def load_jsx(name: str) -> str:
    return (resources.files(_PKG) / "jsx" / name).read_text(encoding="utf-8")


def build_script(op_name: str, params: dict) -> str:
    """prelude + params literal + operation template -> one JSX program."""
    prelude = load_jsx("prelude.jsx")
    op_src = load_jsx(f"{op_name}.jsx")
    params_json = json.dumps(params, ensure_ascii=True, separators=(",", ":"))
    # Double-encode: the inner document becomes a JS string literal.
    params_literal = json.dumps(params_json, ensure_ascii=True)
    return (
        prelude
        + "\nvar __PARAMS_JSON = " + params_literal + ";\n"
        + op_src
    )


def parse_envelope(text: str) -> dict:
    """Parse the JSON envelope a JSX op returns; raise typed errors."""
    text = (text or "").strip()
    if not text:
        raise ScriptError("Illustrator returned an empty result (no envelope).")
    try:
        env = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ScriptError(
            f"Unparseable result from Illustrator: {text[:400]!r}",
            details={"json_error": str(exc)},
        ) from exc
    if not isinstance(env, dict) or "ok" not in env:
        raise ScriptError(f"Malformed result envelope: {text[:400]!r}")
    if env["ok"]:
        return env.get("result", {})
    err = env.get("error") or {}
    raise OpError(
        code=str(err.get("code", "OP_FAILED")),
        message=str(err.get("message", "Operation failed")),
        details=err.get("details"),
    )


class Backend:
    """Interface: run one named JSX operation with JSON params."""

    name = "abstract"

    def run_op(self, op_name: str, params: dict, timeout: float = 120.0) -> dict:
        raise NotImplementedError
