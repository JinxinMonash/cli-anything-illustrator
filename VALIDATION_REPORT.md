# Validation report — cli-anything-illustrator

**Date:** 2026-09-08 (UTC)
**Build environment:** Linux x86_64, Python 3.11.15, Node v18.19.1, pytest 90 passed / 8 skipped (98 collected)
**Upstream audited:** yb2460/harness-anything @ `dcb3e516dee1e7b4c83e1909a07062a0bb8dea0a`; PR #10 head `b41bb6c` reviewed (unmerged)

## Honest summary

This project was developed on a **Linux machine without macOS or Adobe
Illustrator**. Everything marked PASS below is real, executed evidence from
this machine; everything requiring a live Illustrator session is marked
**NOT RUN** and is covered by the shipped integration tests plus
`scripts/run_mac_validation.sh`, which produces the missing evidence in one
command on the user's Mac. Mocked results are labelled as mocked and are not
represented as live-Illustrator testing.

## Evidence classes

| Class | What it proves | Status |
|---|---|---|
| Unit tests (55) | Packaging/imports, CLI `--help` for all 45+ commands offline, parameter-envelope safety (quotes/Unicode/Greek round trip, ASCII-only embedding), envelope parsing, exit-code mapping, units/paths/selectors, overwrite guard semantics, figure-spec validation, backend selection, app discovery overrides, osascript error triage (-1743 / app missing / -609) | **PASS** (this machine) |
| JSX syntax (27) | Every assembled ExtendScript program (prelude + each of the 26 op templates, with adversarial params) parses as valid JavaScript (`node --check`). ExtendScript is ES3 ⊂ what Node accepts, so this catches generation errors, not Illustrator API validity | **PASS** (this machine) |
| Mock end-to-end (35) | Full pipeline — console script → JSON params → JSX assembly → transport → prelude logic (document targeting, selectors, canvas coordinates, alignment math) → envelope → exit codes — executed against a Node mock of the Illustrator DOM with state persisted across CLI processes. Includes: save/close/reopen with Unicode paths+contents, ambiguity rejection, uuid targeting, confirm/force/overwrite/unsaved-changes guards, font refusal vs approved substitution, editable vs linked import, permission/app-missing/timeout/garbage failure modes, operation log, 4-panel assemble→verify (20/20 checks) with aspect-ratio assertions | **PASS (mock — not live evidence)** |
| Acceptance demo (mock) | `figure validate → assemble → close → verify` on the four synthetic panels: manifest written, panels editable groups, labels live text, AI/PDF/SVG/PNG outputs produced, verify 20/20 | **PASS (mock)** — artefacts in `validation_evidence_mock/` |
| Live Illustrator integration (8 tests) | Real `do javascript` round trip, real font resolution, real SVG import editability, real export files, reopen checks, doctor all-green | **NOT RUN** — blocker: no macOS/Illustrator in the build environment. Run `scripts/run_mac_validation.sh` |
| Codex skill evaluation (13 cases) | Activation/refusal/missing-input behaviour of the skill under Codex | **NOT RUN** — cases defined in `.agents/skills/cli-anything-illustrator/references/evaluation.md`; requires Codex + macOS |
| Windows COM backend | Upstream platform retained, isolated | **NOT RUN**, marked experimental |

## Post-release live finding (fixed in 0.9.1)

The first live-Mac run (via a Codex session) confirmed the predicted risk
area: the AppleScript runner's `tell application <runtime variable>` block
prevented dictionary resolution of `do javascript`. Fixed by generating the
runner with the application name as a compile-time literal; regression-guarded
portably (literal/escaping tests) and live (`osacompile` check in the
integration suite). This validates the report's honesty framework: mock
evidence could not, and did not, stand in for live evidence.

## What is explicitly not claimed

- No claim of Apple Silicon or Intel coverage: neither was exercised.
- No claim that Illustrator-side enum/API usage (`ExportOptionsPNG24`,
  `SVGFontType`, `PDFSaveOptions.preserveEditability`, `PageItem.uuid`,
  `textFrames.pointText`, artboard-rect coordinate conventions) behaves as
  modelled — the mock encodes the documented behaviour; the live tests verify
  it. This is the primary risk area for first-run-on-Mac fixes.
- The AppleScript runner (`read … as «class utf8»`, `do javascript`) is
  untested against a real osascript; `app doctor` and the validation script
  will surface dialect issues immediately and errors are mapped to actionable
  messages.
- Mock PNG/SVG/PDF exports are stub bytes; only existence/paths/options flow
  is validated portably.

## Upstream defect repairs (verified by tests where portable)

1. PowerPoint `setup.py` replaced by correct packaging (entry point installs; verified).
2. Broken `cli_anything.*` imports fixed via PEP 420 `src/cli_anything/` layout (as PR #10).
3. Click group/module shadowing (`project`, `text`) eliminated; regression-guarded by help-walk test.
4. f-string/`repr()` JS injection replaced by JSON parameter envelope (tested with quotes/newlines/Greek).
5. Swallowed exceptions replaced by structured envelopes + typed exit codes (tested).
6. Wrong numeric export constants replaced by symbolic enums; PDF moved to `saveAs` with association restore (live-verification pending).
7. Windows COM removed from core; isolated in `backend/win.py`.
8. Active-document mutation replaced by explicit `--doc` targeting with ambiguity rejection (tested).
9. Index-only item addressing replaced by uuid/name/layer/type/contains selectors with uniqueness enforcement (tested).

## Reproduce

```bash
pip install -e ".[dev]"
python -m pytest tests/ -q          # 90 passed, 8 skipped (integration) here
# on the Mac:
scripts/run_mac_validation.sh       # writes validation_evidence/summary.json
```
