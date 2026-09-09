# Validation report — cli-anything-illustrator

**Last updated:** 2026-09-09 (UTC) · v0.9.4
**Build environment:** Linux x86_64, Python 3.11, Node 18 — portable suite 92+ tests passing

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
