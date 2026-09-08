"""Diagnostics distinguishing: missing app, denied automation, unavailable
session, and scripting errors -- without conflating them."""
from __future__ import annotations

import platform
import shutil
import sys

from cli_anything.illustrator.errors import (
    AppMissingError, AutomationDeniedError, CAIError, SessionError,
)

PERMISSION_HELP = (
    "Grant Automation access: System Settings -> Privacy & Security -> "
    "Automation -> enable 'Adobe Illustrator' under the terminal/host app "
    "running this CLI. macOS shows a one-time consent prompt on first use; "
    "if it was dismissed, reset with: tccutil reset AppleEvents"
)


def doctor(app_override: str | None = None) -> dict:
    checks = []
    ok_overall = True

    def add(name, status, detail):
        nonlocal ok_overall
        checks.append({"check": name, "status": status, "detail": detail})
        if status == "fail":
            ok_overall = False

    add("platform", "ok" if sys.platform == "darwin" else "fail",
        f"{sys.platform} / {platform.platform()} / python {platform.python_version()} / {platform.machine()}")

    if sys.platform != "darwin":
        add("osascript", "skip", "not macOS: native backend unavailable here")
        return {"ok": False, "checks": checks,
                "hint": "Run on the macOS machine where Illustrator is installed."}

    add("osascript", "ok" if shutil.which("osascript") else "fail",
        shutil.which("osascript") or "osascript not on PATH")

    from cli_anything.illustrator.backend.mac import MacBackend, discover_illustrator
    info = None
    try:
        info = discover_illustrator(app_override)
        add("illustrator_installed", "ok",
            f"{info['app_name']} {info.get('version') or '(version unknown)'} "
            f"at {info.get('path') or '(name only)'}")
    except AppMissingError as exc:
        add("illustrator_installed", "fail", str(exc))
        return {"ok": False, "checks": checks,
                "hint": "Install Adobe Illustrator or pass --app."}

    backend = MacBackend(app_override)
    try:
        pong = backend.run_op("ping", {"echo": "doctor"}, timeout=90)
        add("automation_permission", "ok", "Apple Events accepted")
        add("scripting_roundtrip", "ok",
            f"Illustrator {pong.get('version')} evaluated ExtendScript")
    except AutomationDeniedError as exc:
        add("automation_permission", "fail", str(exc))
        add("scripting_roundtrip", "skip", PERMISSION_HELP)
    except SessionError as exc:
        add("session", "fail", str(exc))
    except CAIError as exc:
        add("scripting_roundtrip", "fail", f"[{exc.code}] {exc}")

    return {"ok": ok_overall, "checks": checks,
            "app": info, "permission_help": PERMISSION_HELP}
