import pytest

from cli_anything.illustrator.backend import select_backend
from cli_anything.illustrator.backend.mac import (
    MacBackend, _version_key, discover_illustrator,
)
from cli_anything.illustrator.errors import (
    AppMissingError, AutomationDeniedError, ScriptError, SessionError,
    UnsupportedPlatformError,
)


def test_select_backend_rejects_linux():
    with pytest.raises(UnsupportedPlatformError) as ei:
        select_backend(platform="linux")
    assert ei.value.exit_code == 3


def test_select_backend_platforms():
    assert select_backend(platform="darwin").name == "mac-osascript"
    assert select_backend(platform="win32").name == "win-com-experimental"


def test_discover_override_name(monkeypatch):
    monkeypatch.delenv("CAI_ILLUSTRATOR_APP", raising=False)
    info = discover_illustrator("Adobe Illustrator")
    assert info["app_name"] == "Adobe Illustrator"
    assert info["source"] == "override-name"


def test_discover_override_env(monkeypatch):
    monkeypatch.setenv("CAI_ILLUSTRATOR_APP", "My Illustrator")
    assert discover_illustrator()["app_name"] == "My Illustrator"


def test_discover_override_path(tmp_path, monkeypatch):
    monkeypatch.delenv("CAI_ILLUSTRATOR_APP", raising=False)
    bundle = tmp_path / "Adobe Illustrator 2031.app"
    (bundle / "Contents").mkdir(parents=True)
    import plistlib
    with open(bundle / "Contents" / "Info.plist", "wb") as fh:
        plistlib.dump({"CFBundleShortVersionString": "31.2.1"}, fh)
    info = discover_illustrator(str(bundle))
    assert info["app_name"] == "Adobe Illustrator 2031"
    assert info["version"] == "31.2.1"
    assert info["source"] == "override-path"


def test_version_key_ordering():
    assert _version_key("29.5.1") > _version_key("28.7.9")
    assert _version_key("") == (0,)


@pytest.mark.parametrize("stderr,exc", [
    ("execution error: Not authorized to send Apple events... (-1743)", AutomationDeniedError),
    ('Can\'t get application "Adobe Illustrator"', AppMissingError),
    ("connection is invalid. (-609)", SessionError),
    ("some other scripting explosion", ScriptError),
])
def test_stderr_error_mapping(stderr, exc):
    with pytest.raises(exc):
        MacBackend._raise_for_stderr(stderr, "Adobe Illustrator")


# --- regression: first live-Mac defect (0.9.1) --------------------------
# `tell application <variable>` prevents AppleScript from loading the app's
# scripting dictionary, so `do javascript` fails to compile. The runner must
# carry the application name as a compile-time string literal.

def test_runner_bakes_app_name_as_literal():
    src = MacBackend.build_runner("Adobe Illustrator 2025")
    assert 'tell application "Adobe Illustrator 2025"' in src
    assert "__CAI_APP_NAME__" not in src
    assert "do javascript jsxSrc" in src
    # jsx path and timeout still arrive via argv (never interpolated)
    assert "item 1 of argv" in src and "item 2 of argv" in src


def test_runner_escapes_hostile_app_names():
    src = MacBackend.build_runner('Weird "App" \\ Name')
    assert 'tell application "Weird \\"App\\" \\\\ Name"' in src
    # no unescaped quote can terminate the literal early:
    # every '"' except the two delimiters must be preceded by a backslash
    line = next(l for l in src.splitlines() if "tell application" in l)
    assert line.count('"') - line.count('\\"') == 2
