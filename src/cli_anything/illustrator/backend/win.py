"""Windows COM backend (experimental).

Controls Adobe Illustrator through its COM automation interface using the
same parameterised ExtendScript templates and JSON result envelope as the
macOS backend, so commands, output shape and exit codes are identical on
both platforms.

Requirements: Windows desktop session, Adobe Illustrator installed, and
pywin32 (``pip install "cli-anything-illustrator[windows]"``).

Design decisions
----------------
- **Attach before launch.** We first try to attach to a running Illustrator
  (``GetActiveObject``) and only fall back to starting a new instance
  (``Dispatch``): reusing the live session preserves the user's open
  documents and unsaved work instead of spawning a second process.
- **ProgID override.** ``--app`` / ``$CAI_ILLUSTRATOR_APP`` is interpreted as
  a COM ProgID (default ``Illustrator.Application``, which binds the newest
  installed version); a version-specific ProgID pins one release.
- **No enforceable timeout.** A synchronous COM call cannot be cancelled from
  Python; ``timeout`` is therefore advisory here. If a call overruns it we
  still return the (valid) result but attach a warning through the normal
  envelope path rather than pretending the operation failed.
- **Typed errors.** COM failures are mapped onto the same error hierarchy as
  the macOS transport (app missing / session unavailable / script error), so
  scripted callers never need platform-specific handling.

Status: experimental — exercised portably (import guards, backend selection,
script assembly) but not yet validated against a live Windows Illustrator.
"""
from __future__ import annotations

import time

from cli_anything.illustrator.backend.base import Backend, build_script, parse_envelope
from cli_anything.illustrator.errors import (
    AppMissingError, ScriptError, SessionError,
)

DEFAULT_PROGID = "Illustrator.Application"

# HRESULTs worth telling apart (WinError codes surface inside com_error).
_CO_E_CLASSSTRING = -2147221005      # invalid/unregistered ProgID
_MK_E_UNAVAILABLE = -2147221021      # GetActiveObject: no running instance
_E_ACCESSDENIED = -2147024891


class WinBackend(Backend):
    name = "windows-com-experimental"

    def __init__(self, app_override: str | None = None):
        self.progid = app_override or DEFAULT_PROGID
        self._app = None

    # -- COM plumbing ------------------------------------------------------
    @staticmethod
    def _modules():
        try:
            import pythoncom  # type: ignore
            import win32com.client  # type: ignore
        except ImportError as exc:
            raise AppMissingError(
                "The Windows backend needs pywin32. Install it with: "
                "pip install \"cli-anything-illustrator[windows]\""
            ) from exc
        return pythoncom, win32com.client

    def _connect(self):
        if self._app is not None:
            return self._app
        pythoncom, client = self._modules()
        pythoncom.CoInitialize()
        # 1) prefer the user's running session
        try:
            self._app = client.GetActiveObject(self.progid)
            return self._app
        except Exception:
            pass  # not running (or ProgID bad) -- decided by the launch path
        # 2) launch a new instance
        try:
            self._app = client.Dispatch(self.progid)
            return self._app
        except pythoncom.com_error as exc:  # type: ignore[attr-defined]
            hresult = exc.args[0] if exc.args else None
            if hresult == _CO_E_CLASSSTRING:
                raise AppMissingError(
                    f"No COM class registered for ProgID '{self.progid}'. "
                    "Is Adobe Illustrator installed? Pass --app with a valid "
                    "ProgID (e.g. Illustrator.Application)."
                ) from exc
            if hresult == _E_ACCESSDENIED:
                raise SessionError(
                    "COM access denied: run from the same interactive desktop "
                    "session as Illustrator (not a service/RDP-disconnected "
                    "session)."
                ) from exc
            raise SessionError(
                f"Could not start or attach to Illustrator via COM: {exc}"
            ) from exc

    # -- public API --------------------------------------------------------
    def run_op(self, op_name: str, params: dict, timeout: float = 120.0) -> dict:
        app = self._connect()
        script = build_script(op_name, params)
        started = time.monotonic()
        try:
            raw = app.DoJavaScript(script)
        except Exception as exc:  # com_error or dispatch failure
            raise ScriptError(
                f"Illustrator COM call failed: {exc}",
                details={"progid": self.progid, "op": op_name},
            ) from exc
        elapsed = time.monotonic() - started
        result = parse_envelope("" if raw is None else str(raw))
        if elapsed > timeout and isinstance(result, dict):
            result.setdefault("warnings", []).append(
                f"Operation took {elapsed:.0f}s (requested timeout {timeout:.0f}s); "
                "COM calls cannot be interrupted."
            )
        return result
