"""The README kept in step with the CLI and the approvals (docs/design.md, §7 and O-DOC1).

The README restates no progress, so nothing in it goes stale as steps merge. What it does state, the
commands and the labels a repository needs, comes from the code, and these tests fail when the two part.
"""

import re
from pathlib import Path

import pytest

from redline import approval
from redline.cli import main

ROOT = Path(__file__).resolve().parent.parent
LABELS = {approval.DEPARTURE, approval.OVERSIZED, approval.TRACK, approval.RIGOR, approval.MANUAL}


def readme() -> str:
    return (ROOT / "README.md").read_text(encoding="utf-8")


def subcommands(capsys) -> set[str]:
    with pytest.raises(SystemExit):
        main(["--help"])
    return set(re.search(r"\{([a-z,-]+)\}", capsys.readouterr().out)[1].split(","))


def table() -> list[str]:
    """The command of each row of the README's `## Commands` tables: `redline <command> …` in the first cell."""
    _, _, section = readme().partition("\n## Commands\n")
    section = section.split("\n## ", 1)[0]
    return re.findall(r"^\| `redline ([a-z][a-z-]*)\b", section, re.MULTILINE)


def test_the_command_table_lists_each_subcommand_once(capsys):
    rows = table()
    assert sorted(rows) == sorted(subcommands(capsys))


def test_every_command_the_readme_names_exists(capsys):
    named = set(re.findall(r"(?:^|`)redline ([a-z][a-z-]*)", readme(), re.MULTILINE))
    assert named, "the README names no command"
    assert named <= subcommands(capsys)


def settings() -> str:
    design = (ROOT / "docs" / "design.md").read_text(encoding="utf-8")
    return design.split("\n### Repository settings\n", 1)[1].split("\n## ", 1)[0]


@pytest.mark.parametrize("text", [readme, settings], ids=["README", "design §7"])
def test_the_settings_name_the_labels_approval_reads(text):
    assert set(re.findall(r"redline:[a-z]+", text())) == LABELS
