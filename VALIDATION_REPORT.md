# Validation report — cli-anything-illustrator

**Last updated:** 2026-09-09 (UTC) · v0.9.4
**Build environment:** Linux x86_64, Python 3.11, Node 18 — portable suite 92+ tests passing

## v0.10.0 — reference reconstruction (evidence summary)

**Executed on this Linux build machine (real evidence):**
- Portable suite: **190 passed** (object-model mock e2e, fidelity engine
  units, reconstruct workflows, CLI help/exit-code contracts, JSX syntax).
- Perturbation-localization benchmark (real comparison engine, no mock):
  synthetic SVG pair with a moved rectangle, an isoluminant recolour and a
  text edit at 150 dpi -> all three localized as merged regions with correct
  types (geometry/color/text); self-compare returns SSIM > 0.999 with zero
  regions. Evidence: `validation_evidence_mock/reconstruction/`.
- Two engine defects were FOUND BY this benchmark and fixed: (1) isoluminant
  colour changes were invisible to SSIM-only region triggering; (2) one
  moved object flooded the region cap as many adjacent tiles. Region
  detection is now colour-aware and merges same-type connected tiles.

**Mock-only evidence (not live Illustrator):** reconstruct routing
(native_open / raster_template), locked template layers, manifest structure,
editability scoring against mock documents.

**NOT RUN here (live Mac required):** Illustrator's actual PDF/SVG/EPS import
fidelity, Image Trace (`--trace`), real export-vs-reference metrics. Covered
by `tests/integration/TestReconstructLive` and `scripts/run_mac_validation.sh`.

## Summary

Developed on Linux without macOS or Adobe Illustrator. Everything marked PASS
below is executed evidence from that machine; live-Illustrator behaviour is
validated by the shipped integration suite and, since v0.9.1, confirmed in
live use: the maintainer ran the end-to-end workflow on macOS with Adobe
Illustrator driven by Codex — install, diagnostics, and figure generation
from a template spec produced the editable figure (2026-09-09). Mocked
results are labelled as mocked and are never represented as live evidence.

## Evidence classes

| Class | What it proves | Status |
|---|---|---|
| Unit tests | Packaging/imports; `--help` for every command offline; parameter-envelope safety (quotes/Unicode/Greek round trip, ASCII-only embedding); envelope parsing; exit-code mapping; units/paths/selectors; overwrite-guard semantics; figure-spec validation; backend selection; app discovery overrides; osascript error triage (permission −1743 / app missing / no session −609); AppleScript runner literal-baking and escaping | **PASS** (Linux) |
| JSX syntax | Every assembled ExtendScript program (prelude + 26 op templates, adversarial params) parses as valid JavaScript (`node --check`) | **PASS** (Linux) |
| Mock end-to-end | Full pipeline — console script → JSON params → JSX assembly → transport → targeting/selectors/coordinates → envelope → exit codes — against a Node mock of Illustrator's DOM with cross-process state. Save/close/reopen with Unicode paths, ambiguity rejection, uuid targeting, confirm/force/overwrite/unsaved guards, font refusal vs approved substitution, editable vs linked import, permission/app-missing/timeout/garbage failure modes, operation log, 4-panel assemble→verify (20/20 checks, aspect ratios asserted) | **PASS (mock — not live evidence)** |
| Acceptance demo (mock) | `figure validate → assemble → close → verify`: manifest written, panels editable groups, labels live text, AI/PDF/SVG/PNG outputs, verify 20/20 | **PASS (mock)** — artefacts in `validation_evidence_mock/` |
| Live Illustrator integration (9 tests) | Real `do javascript` round trip, runner compilation (osacompile), font resolution, SVG import editability, export files, reopen checks, doctor all-green | **CONFIRMED IN LIVE USE** (v0.9.1+): end-to-end install → doctor → figure assembly worked on macOS/Illustrator via Codex. Formal per-test evidence bundle not yet archived — `scripts/run_mac_validation.sh` produces it in one command |
| Codex skill evaluation (13 cases) | Activation/refusal/missing-input behaviour under Codex | **PARTIALLY OBSERVED** live (installation + assembly path); full case sweep in `references/evaluation.md` not yet recorded |
| Windows COM backend | Same templates/envelope over COM; attach-then-launch; typed HRESULT mapping | **NOT RUN** — experimental; portable import/selection guards only |

## What is explicitly not claimed

- No formal line-item archive of the live integration suite yet (the live
  confirmation is user-reported workflow evidence, not a pytest log);
  `scripts/run_mac_validation.sh` writes `validation_evidence/summary.json`
  plus logs when run on a Mac.
- Mock PNG/SVG/PDF exports are stub bytes; only existence/paths/options flow
  is validated portably. Live export fidelity is checked by the integration
  tests.
- The Windows backend has never touched a live Windows Illustrator.

## Reproduce

```bash
pip install -e ".[dev]"
python -m pytest tests/ -q          # portable suite (integration auto-skips off-macOS)
# on a Mac with Illustrator:
scripts/run_mac_validation.sh
```
