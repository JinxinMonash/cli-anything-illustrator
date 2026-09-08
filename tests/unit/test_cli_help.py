"""--help must work for every command without contacting Illustrator."""
import click
from click.testing import CliRunner

from cli_anything.illustrator.cli import cli


def _walk(cmd, prefix):
    yield prefix
    if isinstance(cmd, click.Group):
        for name, sub in cmd.commands.items():
            yield from _walk(sub, prefix + [name])


def test_every_command_has_working_help():
    runner = CliRunner()
    paths = list(_walk(cli, []))
    assert len(paths) > 40  # root + groups + leaf commands
    for path in paths:
        result = runner.invoke(cli, [*path, "--help"])
        assert result.exit_code == 0, f"{path}: {result.output}"
        assert "Usage:" in result.output


def test_version_flag():
    result = CliRunner().invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "cli-anything-illustrator" in result.output


def test_upstream_alias_project_group():
    result = CliRunner().invoke(cli, ["project", "--help"])
    assert result.exit_code == 0
    assert "save-as" in result.output
