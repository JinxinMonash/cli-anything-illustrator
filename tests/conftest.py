import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

MOCKS = Path(__file__).parent / "mocks"


class CliRunnerProc:
    """Runs the installed CLI as a real subprocess against the mock backend."""

    def __init__(self, env, cwd):
        self.env = env
        self.cwd = cwd

    def run(self, *args, expect_exit=0, timeout=60):
        proc = subprocess.run(
            [sys.executable, "-m", "cli_anything.illustrator", *args],
            capture_output=True, text=True, env=self.env, cwd=self.cwd,
            timeout=timeout,
        )
        assert proc.returncode == expect_exit, (
            f"exit {proc.returncode} != {expect_exit}\n"
            f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
        )
        payload = json.loads(proc.stdout) if proc.stdout.strip() else None
        return proc, payload


@pytest.fixture
def mock_cli(tmp_path):
    env = dict(os.environ)
    env["PATH"] = f"{MOCKS}:{env['PATH']}"
    env["CAI_PLATFORM"] = "darwin"
    env["CAI_ILLUSTRATOR_APP"] = "Adobe Illustrator"
    env["MOCK_AI_STATE"] = str(tmp_path / "mock_state.json")
    env["CAI_LOG_FILE"] = str(tmp_path / "oplog.jsonl")
    env.pop("MOCK_OSASCRIPT_MODE", None)
    return CliRunnerProc(env, cwd=str(tmp_path))
