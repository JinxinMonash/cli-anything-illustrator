# Changelog

## 0.9.4 (2026-09-09)

- Windows COM backend rewritten and improved: attaches to a running
  Illustrator session before launching a new one (preserves open documents),
  interprets `--app` as a COM ProgID, maps HRESULTs to the same typed error
  hierarchy as macOS, and reports (rather than hides) the fact that COM calls
  cannot honour hard timeouts. New `windows` install extra
  (`pip install "cli-anything-illustrator[windows]"`). Still experimental:
  not yet validated against a live Windows Illustrator.
- Licensing files consolidated: project licence in `LICENSE`; third-party
  notices in `THIRD_PARTY_NOTICES`.

## 0.9.3 (2026-09-09)

- Live-Mac status upgraded: end-to-end figure generation via Codex confirmed
  on macOS/Illustrator. Validation report and README updated; README gains a
  "Use with Codex" fast path. No behavioural change.

## 0.9.2 (2026-09-09)

- Refined the Codex skill description and workflow statements; rewrote
  README/package descriptions. No behavioural change.

## 0.9.1 (2026-09-09)

- Fixed the AppleScript runner: the application name is now baked into the
  generated script as a compile-time literal so Illustrator's scripting
  dictionary resolves `do javascript`. Regression tests added (portable
  literal/escaping checks + live osacompile check).

## 0.9.0 (2026-09-08)

- Initial release: native macOS control of Adobe Illustrator
  (AppleScript → ExtendScript), editable multi-panel figure assembly from a
  JSON template, selector-based non-destructive editing, publication exports,
  Codex skill packaging, and a portable test suite with a Node-based mock of
  Illustrator's scripting DOM.
