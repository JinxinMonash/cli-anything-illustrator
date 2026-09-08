"""Typed errors and process exit codes.

Exit codes (stable, documented for the Codex skill):
  0  success
  2  usage / input validation error
  3  Illustrator application not found / platform unsupported
  4  macOS automation permission denied
  5  document targeting error (none open, ambiguous, not found)
  6  operation failed inside Illustrator
  7  timeout (document state must be inspected before retrying a mutation)
  8  refused to overwrite an existing output file
"""
from __future__ import annotations

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_APP_MISSING = 3
EXIT_PERMISSION = 4
EXIT_DOC_TARGET = 5
EXIT_OP_FAILED = 6
EXIT_TIMEOUT = 7
EXIT_OVERWRITE = 8

_DOC_TARGET_CODES = {"NO_DOCUMENT", "AMBIGUOUS_DOCUMENT", "DOC_NOT_FOUND"}


class CAIError(Exception):
    """Base error carrying a machine-readable code and exit code."""

    exit_code = EXIT_OP_FAILED
    code = "OP_FAILED"

    def __init__(self, message: str, code: str | None = None, details=None):
        super().__init__(message)
        if code:
            self.code = code
        self.details = details

    def to_json(self) -> dict:
        out = {"code": self.code, "message": str(self)}
        if self.details is not None:
            out["details"] = self.details
        return out


class ValidationError(CAIError):
    exit_code = EXIT_USAGE
    code = "BAD_PARAMS"


class AppMissingError(CAIError):
    exit_code = EXIT_APP_MISSING
    code = "APP_MISSING"


class UnsupportedPlatformError(CAIError):
    exit_code = EXIT_APP_MISSING
    code = "UNSUPPORTED_PLATFORM"


class AutomationDeniedError(CAIError):
    exit_code = EXIT_PERMISSION
    code = "AUTOMATION_DENIED"


class SessionError(CAIError):
    """App present but no usable desktop session / app cannot be reached."""
    exit_code = EXIT_APP_MISSING
    code = "SESSION_UNAVAILABLE"


class OpTimeoutError(CAIError):
    exit_code = EXIT_TIMEOUT
    code = "TIMEOUT"


class OverwriteRefusedError(CAIError):
    exit_code = EXIT_OVERWRITE
    code = "OVERWRITE_REFUSED"


class ScriptError(CAIError):
    """The JSX script failed or returned an unparseable result."""
    exit_code = EXIT_OP_FAILED
    code = "SCRIPT_ERROR"


class OpError(CAIError):
    """Structured failure reported by the JSX result envelope."""

    def __init__(self, code: str, message: str, details=None):
        super().__init__(message, code=code, details=details)
        self.exit_code = (
            EXIT_DOC_TARGET if code in _DOC_TARGET_CODES else EXIT_OP_FAILED
        )
