"""Fidelity engine for cli-anything-illustrator.

Pure-Python reference preflight analysis (``analyze``), reference
rasterisation (``render``), visual comparison (``compare``) and structural
editability scoring (``editability``).  Nothing in this package talks to
Adobe Illustrator; every function is a pure function over file paths and
plain dicts, so the engine is portable and unit-testable on any platform.

Imports are lazy: ``import cli_anything.illustrator.fidelity`` never
requires the optional third-party dependencies (pymupdf, numpy, pillow).
They are imported on first use, and a missing dependency raises an
``ImportError`` whose message names the exact install command.

Public API (resolved lazily via module ``__getattr__``):

- ``analyze_reference(path)``            -> preflight report dict
- ``render_reference(path, dpi, out_png)`` -> render info dict
- ``compare_images(ref_png, candidate_png, ...)`` -> comparison dict
- ``map_regions_to_objects(regions, objects_json, dpi)`` -> mapping list
- ``score_editability(doc_report)``      -> editability report dict
"""

_INSTALL_HINT = (
    "The fidelity engine requires the optional dependencies pymupdf, "
    "numpy and pillow. Install them with:\n"
    '    pip install "cli-anything-illustrator[fidelity]"\n'
    "or directly:\n"
    "    pip install pymupdf numpy pillow"
)

_EXPORTS = {
    "analyze_reference": "cli_anything.illustrator.fidelity.analyze",
    "render_reference": "cli_anything.illustrator.fidelity.render",
    "compare_images": "cli_anything.illustrator.fidelity.compare",
    "map_regions_to_objects": "cli_anything.illustrator.fidelity.compare",
    "score_editability": "cli_anything.illustrator.fidelity.editability",
}

__all__ = [
    "analyze_reference",
    "compare_images",
    "map_regions_to_objects",
    "render_reference",
    "require",
    "score_editability",
]


def require(module_name):
    """Import an optional dependency, or raise an actionable ImportError.

    Parameters:
        module_name (str): importable module name, e.g. ``"fitz"``,
            ``"numpy"``, ``"PIL.Image"``.

    Returns:
        module: the imported module object.

    Raises:
        ImportError: if the module is unavailable.  The message names the
            missing module and the install command
            ``pip install "cli-anything-illustrator[fidelity]"``.
    """
    import importlib

    if module_name == "fitz":
        # pymupdf >= 1.24 exposes the canonical `pymupdf` name; importing the
        # legacy `fitz` alias prints a deprecation warning on STDOUT, which
        # would corrupt the CLI's JSON envelope. Prefer the canonical name.
        try:
            return importlib.import_module("pymupdf")
        except ImportError:
            pass
    try:
        return importlib.import_module(module_name)
    except ImportError as exc:
        raise ImportError(
            "Missing optional dependency %r needed by the fidelity engine.\n%s"
            % (module_name, _INSTALL_HINT)
        ) from exc


def __getattr__(name):
    """PEP 562 lazy attribute access for the public API."""
    if name in _EXPORTS:
        import importlib

        mod = importlib.import_module(_EXPORTS[name])
        return getattr(mod, name)
    raise AttributeError("module %r has no attribute %r" % (__name__, name))


def __dir__():
    return sorted(set(list(globals()) + __all__))
