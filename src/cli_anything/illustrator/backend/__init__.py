"""Backend selection: macOS (native, supported) or Windows COM (experimental)."""
from __future__ import annotations

import sys

from cli_anything.illustrator.backend.base import Backend, build_script, parse_envelope  # noqa: F401
from cli_anything.illustrator.errors import UnsupportedPlatformError


def select_backend(app_override: str | None = None,
                   platform: str | None = None) -> Backend:
    plat = platform or sys.platform
    if plat == "darwin":
        from cli_anything.illustrator.backend.mac import MacBackend
        return MacBackend(app_override)
    if plat.startswith("win"):
        from cli_anything.illustrator.backend.win import WinBackend
        return WinBackend(app_override)
    raise UnsupportedPlatformError(
        f"Platform '{plat}' cannot control Adobe Illustrator. Run this CLI on "
        "the macOS machine where Illustrator is installed (Windows COM backend "
        "is experimental)."
    )
