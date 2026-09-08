# Changelog

## 0.9.3 (2026-09-09)

- Live-Mac status upgraded: end-to-end figure generation via Codex confirmed
  on macOS/Illustrator (user-reported after the 0.9.1 fix). Validation report
  and README updated accordingly; hedging language removed.
- README gains a "Use with Codex" fast path (install-and-run prompt, template
  figure workflow); limitations trimmed to actual design notes.
- Skill description now names the template-spec workflow and high-resolution
  deliverables explicitly. No behavioural change.

## 0.9.2 (2026-09-09)

- Refined the Codex skill description and workflow statements (clearer
  activation boundaries and integrity rules; no behavioural change).
- Rewrote README/package descriptions; upstream provenance now lives solely
  in LICENSE and PROVENANCE.md.

## 0.9.1 (2026-09-09)

Fix from first live-Mac validation (reported via Codex session):

- **AppleScript runner: `do javascript` failed to compile.** The runner used
  `tell application appName` with a runtime variable, so osascript could not
  load Illustrator's scripting dictionary and the app-specific term
  `do javascript` was unresolvable. The application name (from discovery or
  `--app`/`$CAI_ILLUSTRATOR_APP`) is now baked into the generated runner as an
  escaped compile-time string literal; the JSX path and timeout still travel
  via argv. Added a portable regression test for literal-baking/escaping and a
  live `osacompile` compile check (`tests/integration`), and the same check to
  `scripts/run_mac_validation.sh` territory via the integration suite.

## 0.9.0 (2026-09-08)

Initial macOS port of the yb2460/harness-anything Illustrator harness +
Codex skill packaging. See PROVENANCE.md and VALIDATION_REPORT.md.
