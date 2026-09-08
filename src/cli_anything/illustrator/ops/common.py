"""Shared helpers for CLI operations (units, paths, selectors)."""
from __future__ import annotations

import os

from cli_anything.illustrator.errors import OverwriteRefusedError, ValidationError

PT_PER_MM = 72.0 / 25.4
PT_PER_IN = 72.0


def to_pt(value: float, units: str) -> float:
    u = (units or "pt").lower()
    if u == "pt":
        return float(value)
    if u == "mm":
        return float(value) * PT_PER_MM
    if u == "cm":
        return float(value) * PT_PER_MM * 10.0
    if u in ("in", "inch"):
        return float(value) * PT_PER_IN
    raise ValidationError(f"Unknown units: {units} (use pt, mm, cm, in)")


def prepare_output_path(path: str, overwrite: bool) -> str:
    """Absolute output path with directory creation and overwrite guard."""
    abs_path = os.path.abspath(os.path.expanduser(path))
    parent = os.path.dirname(abs_path) or "."
    os.makedirs(parent, exist_ok=True)
    if os.path.exists(abs_path) and not overwrite:
        raise OverwriteRefusedError(
            f"Refusing to overwrite existing file: {abs_path} (pass --overwrite)."
        )
    return abs_path


def require_input_path(path: str) -> str:
    abs_path = os.path.abspath(os.path.expanduser(path))
    if not os.path.isfile(abs_path):
        raise ValidationError(f"Input file not found: {abs_path}")
    return abs_path


def build_selector(uuid=None, name=None, layer=None, item_type=None,
                   contains=None, index=None, required=True) -> dict:
    sel = {}
    if uuid:
        sel["uuid"] = str(uuid)
    if name:
        sel["name"] = str(name)
    if layer:
        sel["layer"] = str(layer)
    if item_type:
        sel["type"] = str(item_type)
    if contains:
        sel["contains"] = str(contains)
    if index is not None:
        sel["index"] = int(index)
    if required and not sel:
        raise ValidationError(
            "Empty selector: pass at least one of --uuid/--name/--layer/"
            "--type/--contains/--index."
        )
    return sel


def rgb_triplet(value: str) -> list[int]:
    """Parse 'r,g,b' (0-255) or hex '#rrggbb'."""
    v = value.strip()
    if v.startswith("#"):
        if len(v) != 7:
            raise ValidationError(f"Bad hex colour: {value}")
        return [int(v[i:i + 2], 16) for i in (1, 3, 5)]
    parts = [p.strip() for p in v.split(",")]
    if len(parts) != 3:
        raise ValidationError(f"Bad colour '{value}': use 'r,g,b' or '#rrggbb'.")
    nums = []
    for p in parts:
        n = int(p)
        if not 0 <= n <= 255:
            raise ValidationError(f"Colour channel out of range 0-255: {p}")
        nums.append(n)
    return nums
