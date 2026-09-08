#!/usr/bin/env bash
# One-command live validation on a Mac with Adobe Illustrator.
# Produces validation_evidence/ with a machine-readable summary, the pytest
# log, the assembled acceptance figure and its manifest.
set -uo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "This validation script must run on macOS." >&2
    exit 3
fi

EVIDENCE="validation_evidence"
mkdir -p "$EVIDENCE"
PYBIN="${PYTHON:-python3}"

echo "== 1/5 install (user venv recommended) =="
"$PYBIN" -m pip install -e ".[dev]" || exit 1

echo "== 2/5 doctor =="
cli-anything-illustrator app doctor | tee "$EVIDENCE/doctor.json"
DOCTOR_EXIT=${PIPESTATUS[0]}
if [[ $DOCTOR_EXIT -ne 0 ]]; then
    echo "Doctor failed (exit $DOCTOR_EXIT). Fix the reported check (install /" \
         "Automation permission / session) and re-run." >&2
    exit "$DOCTOR_EXIT"
fi

echo "== 3/5 portable test suite =="
"$PYBIN" -m pytest tests/unit tests/e2e_mock -q 2>&1 | tee "$EVIDENCE/pytest_portable.log"

echo "== 4/5 LIVE Illustrator integration tests =="
"$PYBIN" -m pytest tests/integration -m illustrator -v 2>&1 | tee "$EVIDENCE/pytest_live.log"
LIVE_EXIT=${PIPESTATUS[0]}

echo "== 5/5 acceptance demo: 4 panels -> editable figure -> exports =="
DEMO="$EVIDENCE/acceptance_demo"
rm -rf "$DEMO"; mkdir -p "$DEMO/panels"
"$PYBIN" examples/make_panels.py --outdir "$DEMO/panels"
( cd examples && "$PYBIN" - "$PWD/../$DEMO" <<'PYEOF'
import json, sys, pathlib
demo = pathlib.Path(sys.argv[1])
spec = json.load(open("figure1_spec.json"))
json.dump(spec, open(demo / "figure1_spec.json", "w"), indent=2)
PYEOF
)
( cd "$DEMO" && \
  cli-anything-illustrator figure validate --spec figure1_spec.json && \
  cli-anything-illustrator figure assemble --spec figure1_spec.json | tee assemble_result.json && \
  cli-anything-illustrator doc close --doc figure1.ai --discard-changes && \
  cli-anything-illustrator figure verify --spec figure1_spec.json | tee verify_result.json && \
  cli-anything-illustrator doc list )
DEMO_EXIT=$?

python3 - "$EVIDENCE" "$LIVE_EXIT" "$DEMO_EXIT" <<'PYEOF'
import datetime, json, platform, subprocess, sys
ev, live_exit, demo_exit = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
summary = {
    "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "macos": platform.mac_ver()[0], "machine": platform.machine(),
    "python": platform.python_version(),
    "live_tests_exit": live_exit, "acceptance_demo_exit": demo_exit,
    "status": "PASS" if live_exit == 0 and demo_exit == 0 else "FAIL",
}
try:
    doctor = json.load(open(f"{ev}/doctor.json"))
    summary["illustrator"] = doctor["result"].get("app")
except Exception as e:
    summary["doctor_parse_error"] = str(e)
json.dump(summary, open(f"{ev}/summary.json", "w"), indent=2)
print(json.dumps(summary, indent=2))
PYEOF
