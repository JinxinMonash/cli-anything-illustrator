# Upstream provenance and reuse matrix

**Primary upstream:** https://github.com/yb2460/harness-anything
**Pinned revision audited:** `dcb3e516dee1e7b4c83e1909a07062a0bb8dea0a` (2026-07-19)
**Upstream licence:** MIT ("cli-anything-wps contributors") — retained in `LICENSE`.
**PR reviewed:** #10 (`b41bb6cb7b353d7a61df1ba8292612ae525ff442`, unmerged at audit
time). PR #10 moves the package under `cli_anything/`, replaces the PowerPoint
`setup.py` with Illustrator packaging, removes duplicated COM code from
`project.py`, and adds non-launching CLI tests. It remains 100% Windows COM.

## Audit findings at the pinned revision

| # | Finding | Location | Status here |
|---|---------|----------|-------------|
| 1 | `setup.py` is PowerPoint packaging (name `cli-anything-powerpoint`, entry point `powerpoint_cli:cli`, `python-pptx` deps) | `illustrator-harness/agent-harness/setup.py` | Replaced by `pyproject.toml` with correct name/entry point (direction taken from PR #10, modernised) |
| 2 | Imports reference `cli_anything.illustrator.*` but no `cli_anything/` directory exists → package unimportable | `illustrator_cli.py` | Fixed: PEP 420 layout `src/cli_anything/illustrator/` (as in PR #10) |
| 3 | Click group functions `project` and `text` shadow the imported modules of the same names → `AttributeError` at runtime | `illustrator_cli.py` | Fixed: modules aliased on import; group functions named `*_grp` |
| 4 | User text interpolated into JavaScript via f-strings / `repr()` → quoting/injection failures (quotes, Unicode, Greek, newlines) | `core/text.py`, `core/shapes.py`, `core/project.py` | Replaced: static JSX templates + JSON parameter envelope; no user data is ever spliced into code |
| 5 | Swallowed exceptions (`except Exception: pass`) around `DoJavaScript`; subprocess/COM success conflated with document change | `core/project.py`, `core/export.py`, `core/text.py` | Replaced: every JSX op returns a structured JSON envelope; Python raises typed errors with exit codes; mutations are read back |
| 6 | Export uses numeric COM constants (PNG=5, SVG=2, PDF=3) that do not match Illustrator's ExportType values; PDF is not an ExportType at all | `core/export.py` | Replaced: `exportFile` with `ExportOptionsPNG24`/`ExportOptionsSVG` symbolic enums; PDF via `saveAs(PDFSaveOptions)` with document-association restore |
| 7 | Windows COM (`win32com`, `pythoncom`) imported directly in core modules | `core/project.py`, `utils/ai_backend.py` | Core is now platform-free; COM isolated in `backend/win.py` (optional, experimental) |
| 8 | Active-document-only model: every op mutates whichever document happens to be active | all core modules | Replaced: explicit `--doc` targeting; ambiguous targets rejected |
| 9 | Layer/text targeting by mutable 1-based collection index only | `core/layers.py`, `core/text.py` | Replaced: selector grammar (uuid/name/layer/type/contains); non-unique matches rejected |
| 10 | Interactive REPL (`repl_skin.py`) | `utils/repl_skin.py` | Dropped (out of scope for skill-driven use; CLI is non-interactive) |

## Reuse matrix

| Upstream component | Decision | Notes |
|---|---|---|
| Command-group taxonomy (`project/layer/text/shape/export/backend detect`) | **Adapted** | Preserved as `doc/layer/text/shape/export/app` with upstream-compatible aliases where meaningful (`project` alias for `doc`, `backend detect` → `app detect`) |
| Click CLI structure (group/command/`--json`, context object) | **Adapted** | Same shape; JSON envelope now default on stdout |
| ExtendScript operation bodies (rectangle/ellipse/polygon/star/pointText/areaText geometry, `artboardRect` sizing) | **Adapted** | Geometry and API call patterns retained, moved into parameterised `.jsx` templates |
| `core/layers.py` operation set (list/add/remove/show/hide) | **Adapted** | Reimplemented over JSX with selector targeting |
| `export_artboards` per-artboard loop | **Adapted** | Rewritten with symbolic enums and read-back |
| Windows COM transport (`DoJavaScript`) | **Adapted (isolated)** | `backend/win.py`, experimental, not validated in this project |
| `setup.py` | **Replaced** | PowerPoint metadata; see finding 1 |
| Numeric export constants | **Replaced** | See finding 6 |
| f-string JSX generation | **Replaced** | See finding 4 |
| `repl_skin.py`, REPL command | **Dropped** | See finding 10 |
| `test_ai_harness.py` (launches real app, Windows-only) | **Replaced** | Split into portable unit tests and `-m illustrator` integration tests |

## Repositories also inspected

`yb2460/harness-anything-mac` was NOT used as a source: per the project brief its
name is not evidence of an Illustrator port; the primary repository above remains
the provenance source for all adapted code.
