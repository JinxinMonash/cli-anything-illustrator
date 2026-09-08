# macOS prerequisites & Automation permission

The CLI controls Illustrator through Apple Events (osascript → `do
javascript`). macOS gates this per calling application.

Requirements:
- Adobe Illustrator installed AND licensed (a blocked licensing dialog also
  blocks scripting) on this Mac, with a logged-in desktop session.
- Python 3.10+.

First run: `cli-anything-illustrator app doctor`
- `illustrator_installed: fail` → install Illustrator or pass
  `--app "<name-or-/path/to.app>"` / set `CAI_ILLUSTRATOR_APP`.
- `automation_permission: fail` (error -1743, exit 4) → System Settings →
  Privacy & Security → Automation → under your terminal (Terminal/iTerm/the
  Codex host app), enable "Adobe Illustrator". macOS normally shows a one-time
  consent prompt; if it was dismissed, reset with `tccutil reset AppleEvents`
  and run a command again to re-trigger the prompt.
- `session`/`SESSION_UNAVAILABLE` → no usable GUI session (SSH-only login,
  locked managed Mac) or Illustrator cannot start.

Never attempt to bypass these permissions; they are the user's security
boundary. The CLI requests nothing beyond Apple Events to Illustrator.
