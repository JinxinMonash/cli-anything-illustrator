"""EXPERIMENTAL Windows COM backend (isolated; adapted from upstream
yb2460/harness-anything ``utils/ai_backend.py``).

Reuses the same JSX templates via COM ``DoJavaScript``. This module is kept so
the port does not lose upstream's platform, but it has NOT been validated in
this project; the supported platform is macOS (see backend/mac.py).
"""
from __future__ import annotations

from cli_anything.illustrator.backend.base import Backend, build_script, parse_envelope
from cli_anything.illustrator.errors import AppMissingError


class WinBackend(Backend):
    name = "win-com-experimental"

    def __init__(self, app_override: str | None = None):
        self._app = None

    def _com_app(self):
        if self._app is None:
            try:
                import pythoncom  # type: ignore
                import win32com.client  # type: ignore
            except ImportError as exc:
                raise AppMissingError(
                    "pywin32 is required for the Windows backend: "
                    "pip install 'cli-anything-illustrator[windows]'"
                ) from exc
            pythoncom.CoInitialize()
            try:
                self._app = win32com.client.Dispatch("Illustrator.Application")
            except Exception as exc:  # noqa: BLE001
                raise AppMissingError(
                    f"Adobe Illustrator COM server not available: {exc}"
                ) from exc
        return self._app

    def run_op(self, op_name: str, params: dict, timeout: float = 120.0) -> dict:
        app = self._com_app()
        script = build_script(op_name, params)
        out = app.DoJavaScript(script)
        return parse_envelope(str(out))
