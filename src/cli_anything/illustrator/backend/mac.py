"""macOS backend: osascript -> AppleScript -> Illustrator ``do javascript``.

Requirements on the user's Mac: Adobe Illustrator installed and licensed, a
usable desktop session, and Automation permission for the calling terminal
(System Settings -> Privacy & Security -> Automation). This module never
bypasses those permissions; it maps denials to typed errors.
"""
from __future__ import annotations

import glob
import os
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile

from cli_anything.illustrator.backend.base import Backend, build_script, parse_envelope
from cli_anything.illustrator.errors import (
    AppMissingError,
    AutomationDeniedError,
    OpTimeoutError,
    ScriptError,
    SessionError,
)

BUNDLE_ID = "com.adobe.illustrator"
ENV_APP_OVERRIDE = "CAI_ILLUSTRATOR_APP"
ENV_DEBUG = "CAI_DEBUG"

# AppleScript / Apple Events error signatures worth distinguishing.
_ERR_NOT_AUTHORIZED = ("-1743", "Not authorized", "not allowed assistive")
_ERR_APP_NOT_FOUND = ("Can't get application", "Application can't be found", "(-2700)")
_ERR_NO_SESSION = ("-600", "-609", "connection is invalid")


def _read_bundle_version(app_path: str) -> str:
    try:
        with open(os.path.join(app_path, "Contents", "Info.plist"), "rb") as fh:
            info = plistlib.load(fh)
        return str(info.get("CFBundleShortVersionString", ""))
    except Exception:
        return ""


def _mdfind_candidates() -> list[str]:
    try:
        proc = subprocess.run(
            ["mdfind", f"kMDItemCFBundleIdentifier == '{BUNDLE_ID}'"],
            capture_output=True, text=True, timeout=15,
        )
        return [p for p in proc.stdout.splitlines() if p.strip()]
    except Exception:
        return []


def _glob_candidates() -> list[str]:
    pats = [
        "/Applications/Adobe Illustrator*/Adobe Illustrator*.app",
        "/Applications/Adobe Illustrator*.app",
        os.path.expanduser("~/Applications/Adobe Illustrator*/Adobe Illustrator*.app"),
    ]
    out: list[str] = []
    for pat in pats:
        out.extend(glob.glob(pat))
    return out


def _version_key(v: str):
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3]) if v else (0,)


def discover_illustrator(override: str | None = None) -> dict:
    """Locate Adobe Illustrator; no release name or path is hard-coded.

    ``override`` (or $CAI_ILLUSTRATOR_APP) may be an application NAME as known
    to macOS (e.g. "Adobe Illustrator") or a path to a ``.app`` bundle.
    """
    override = override or os.environ.get(ENV_APP_OVERRIDE)
    if override:
        if override.endswith(".app") or os.path.isdir(override):
            path = os.path.abspath(override)
            name = os.path.splitext(os.path.basename(path))[0]
            return {
                "app_name": name, "path": path,
                "version": _read_bundle_version(path),
                "source": "override-path", "candidates": [path],
            }
        return {"app_name": override, "path": "", "version": "",
                "source": "override-name", "candidates": []}

    seen: dict[str, str] = {}
    for p in _mdfind_candidates() + _glob_candidates():
        p = os.path.abspath(p)
        if p not in seen:
            seen[p] = _read_bundle_version(p)
    if not seen:
        raise AppMissingError(
            "Adobe Illustrator was not found (Spotlight bundle-id query and "
            "/Applications scan both empty). Install Illustrator, or pass "
            "--app / set $CAI_ILLUSTRATOR_APP to its name or .app path.",
            details={"bundle_id": BUNDLE_ID},
        )
    best = max(seen, key=lambda p: _version_key(seen[p]))
    name = os.path.splitext(os.path.basename(best))[0]
    return {
        "app_name": name, "path": best, "version": seen[best],
        "source": "discovered",
        "candidates": [{"path": p, "version": v} for p, v in sorted(seen.items())],
    }


class MacBackend(Backend):
    name = "mac-osascript"

    def __init__(self, app_override: str | None = None):
        if sys.platform != "darwin":
            # Constructing off-macOS is allowed for unit tests only; run_op
            # will fail cleanly if osascript is absent.
            pass
        self._app = None
        self._app_override = app_override

    @property
    def app_info(self) -> dict:
        if self._app is None:
            self._app = discover_illustrator(self._app_override)
        return self._app

    # -- transport -------------------------------------------------------
    @staticmethod
    def build_runner(app_name: str) -> str:
        """Runner AppleScript with the app name baked in as a LITERAL.

        The `tell application` target must be a compile-time literal so that
        osascript loads Illustrator's scripting dictionary; with a runtime
        variable the app-specific term `do javascript` does not compile
        (defect found in first live-Mac validation, fixed in 0.9.1).
        """
        from cli_anything.illustrator.backend.base import load_jsx
        escaped = app_name.replace("\\", "\\\\").replace('"', '\\"')
        return load_jsx("runner.applescript").replace("__CAI_APP_NAME__", escaped)

    def _osascript(self, jsx_source: str, timeout: float) -> str:
        if shutil.which("osascript") is None:
            raise SessionError(
                "osascript not found: the macOS backend must run on the Mac "
                "that has Illustrator installed (not in a remote/Linux shell)."
            )
        app_name = self.app_info["app_name"]
        workdir = tempfile.mkdtemp(prefix="cai-jsx-")  # 0700 by default
        jsx_path = os.path.join(workdir, "op.jsx")
        runner_path = os.path.join(workdir, "runner.applescript")
        try:
            with open(jsx_path, "w", encoding="utf-8") as fh:
                fh.write(jsx_source)
            with open(runner_path, "w", encoding="utf-8") as fh:
                fh.write(self.build_runner(app_name))
            try:
                proc = subprocess.run(
                    ["osascript", runner_path, jsx_path,
                     str(int(max(timeout, 1)))],
                    capture_output=True, text=True, timeout=timeout + 20,
                )
            except subprocess.TimeoutExpired as exc:
                raise OpTimeoutError(
                    f"osascript did not return within {timeout + 20:.0f}s. "
                    "Inspect document state (doc list / doc info) before "
                    "retrying any mutation.",
                ) from exc
            if proc.returncode != 0:
                self._raise_for_stderr(proc.stderr, app_name)
            return proc.stdout
        finally:
            if os.environ.get(ENV_DEBUG):
                sys.stderr.write(f"[cai] debug: kept {workdir}\n")
            else:
                shutil.rmtree(workdir, ignore_errors=True)

    @staticmethod
    def _raise_for_stderr(stderr: str, app_name: str):
        s = stderr or ""
        if any(sig in s for sig in _ERR_NOT_AUTHORIZED):
            raise AutomationDeniedError(
                "macOS refused Apple Events to Illustrator (error -1743). "
                "Grant permission in System Settings -> Privacy & Security -> "
                "Automation: enable Adobe Illustrator under your terminal "
                "(or the Codex host app), then re-run. If no prompt appears: "
                f"tccutil reset AppleEvents, or run once from Terminal.app.",
                details={"stderr": s.strip()[:500], "app": app_name},
            )
        if any(sig in s for sig in _ERR_APP_NOT_FOUND):
            raise AppMissingError(
                f"macOS could not resolve application '{app_name}'. "
                "Pass --app with the exact application name or .app path.",
                details={"stderr": s.strip()[:500]},
            )
        if any(sig in s for sig in _ERR_NO_SESSION):
            raise SessionError(
                "Illustrator could not be launched or reached (Apple Events "
                "connection failed). Ensure a logged-in desktop session and "
                "that Illustrator can start (licensing dialogs block scripting).",
                details={"stderr": s.strip()[:500]},
            )
        raise ScriptError(
            "osascript failed: " + s.strip()[:800],
            details={"stderr": s.strip()[:2000]},
        )

    # -- public API ------------------------------------------------------
    def run_op(self, op_name: str, params: dict, timeout: float = 120.0) -> dict:
        script = build_script(op_name, params)
        out = self._osascript(script, timeout)
        return parse_envelope(out)
