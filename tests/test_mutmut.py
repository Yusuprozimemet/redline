"""mutmut behind the Mutator seam: Redline's settings alone, `[tool.mutmut]` taken out of the copy, and the
scenario's tests copied; first with mutmut's run faked, then on the real mutmut, which runs only on Linux and
only with REDLINE_REAL_RUNNERS=1, as the runners CI job sets. See docs/design.md, §5."""

import configparser
import os
import subprocess
import tomllib
from pathlib import Path

import pytest
import yaml

from redline.breaks import Mutmut
from redline.cli import main
from test_check_break import HOLD_TESTS, HOLDS, delta, holds, mutator  # noqa: F401 (fixtures)
from test_ci import WORKFLOW
from test_start import CHANGE, change  # noqa: F401 (a fixture)

GREET = 'def greet():\n    return "hello"\n'
RESULTS = "    greet.x_greet__mutmut_1: killed\n    greet.x_greet__mutmut_2: survived\n"
PYTEST = '[tool.pytest.ini_options]\naddopts = "-q"\n\n'
TABLE = '[tool.mutmut]\nsource_paths = ["other.py"]\npytest_add_cli_args = ["-p", "no:redline"]\n\n'


def toy(root: Path, files: dict[str, str]) -> Path:
    for path, text in files.items():
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text(text, encoding="utf-8")
    return root


def fake_run(monkeypatch) -> list[dict]:
    """mutmut's run faked: each call keeps the copy's mutmut settings and pyproject.toml as mutmut would find them."""
    seen = []

    def run(command, cwd, **kwargs):
        config = configparser.ConfigParser()
        config.read(cwd / "setup.cfg", encoding="utf-8")
        pyproject = cwd / "pyproject.toml"
        seen.append({"mutmut": dict(config["mutmut"]) if config.has_section("mutmut") else None,
                     "pyproject": tomllib.loads(pyproject.read_text(encoding="utf-8")) if pyproject.exists() else None})
        return subprocess.CompletedProcess(command, 0, RESULTS, "")

    monkeypatch.setattr("redline.breaks.subprocess.run", run)
    return seen


def test_mutmut_gets_redlines_settings_alone_and_the_scenarios_tests_with_their_conftests_and_support(repo, monkeypatch):
    repo.commit("toy", {"greet.py": GREET, "conftest.py": "", "checks/conftest.py": "", "checks/unit/test_h.py": "",
                        "helpers/build.py": "", "redline/config.yaml": yaml.safe_dump({"support": ["helpers/*.py"]}),
                        "setup.cfg": "[mutmut]\npytest_add_cli_args = -p no:redline\ndo_not_mutate = *\n"})
    seen = fake_run(monkeypatch)
    assert Mutmut(repo.path).kills(["greet.py"], "TOY.H1", ["checks/unit/test_h.py"]) == (2, 1)
    settings = seen[0]["mutmut"]
    assert sorted(settings) == ["also_copy", "pytest_add_cli_args", "source_paths"]  # the repository's own are gone
    assert settings["source_paths"] == "greet.py" and settings["pytest_add_cli_args"] == "--redline-spec=TOY.H1"
    assert settings["also_copy"].split() == ["checks", "checks/unit", "conftest.py", "helpers"]  # directories, as mutmut copies


def test_tool_mutmut_is_taken_out_of_the_copy_and_pytests_settings_stay(tmp_path, monkeypatch):
    toy(tmp_path, {"greet.py": GREET, "pyproject.toml": PYTEST + TABLE + '[tool.mutmut.extra]\nx = 1\n\n[project]\nname = "toy"\n'})
    seen = fake_run(monkeypatch)
    Mutmut(tmp_path).kills(["greet.py"], "TOY.H1", [])
    assert seen[0]["pyproject"] == {"tool": {"pytest": {"ini_options": {"addopts": "-q"}}}, "project": {"name": "toy"}}
    assert "also_copy" not in seen[0]["mutmut"]  # nothing to copy: mutmut would read "" as ".", the whole copy
    assert "mutmut" in (tmp_path / "pyproject.toml").read_text(encoding="utf-8")  # the repository itself is untouched


@pytest.mark.parametrize("table", ['tool = { mutmut = { source_paths = ["other.py"] } }\n',
                                   '[tool]\nmutmut.source_paths = ["other.py"]\n'])
def test_a_tool_mutmut_that_cant_be_taken_out_by_its_table_is_an_error(tmp_path, monkeypatch, table):
    toy(tmp_path, {"greet.py": GREET, "pyproject.toml": table})
    seen = fake_run(monkeypatch)
    with pytest.raises(RuntimeError, match=r"can't take \[tool.mutmut\] out of pyproject.toml"):
        Mutmut(tmp_path).kills(["greet.py"], "TOY.H1", [])
    assert seen == []


def test_check_break_hands_mutmut_the_scenarios_test_files(holds, capsys, mutator):
    holds.commit("H1 in checks/", {f"{CHANGE}/specs/greet/delta.md": delta(HOLDS.split("#### Scenario GREET.H2")[0]),
                                   "checks/test_hold.py": HOLD_TESTS.split('@pytest.mark.spec("GREET.H2"')[0]})
    assert main(["check-break", "add-greet", "--repo", str(holds.path)]) == 0, capsys.readouterr().out
    assert mutator.tests == [["checks/test_hold.py"]]


def test_the_runners_job_runs_the_real_mutmut():
    job = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["runners"]
    runs = " ".join(step.get("run", "") for step in job["steps"])
    assert "-r requirements.txt" in runs and "tests/test_mutmut.py" in runs  # mutmut, on Linux


real = pytest.mark.skipif(os.environ.get("REDLINE_REAL_RUNNERS") != "1", reason="the real mutmut runs in the runners CI job")
CREDIT = """import pytest
from greet import greet


@pytest.mark.spec("TOY.H1")
def test_weak():
    assert greet() is not None


@pytest.mark.spec("TOY.H2")
def test_strong():
    assert greet() == "hello"


def test_unlinked():
    assert greet() == "hello"
"""


@real
@pytest.mark.parametrize("pyproject", ["", TABLE.replace("other.py", "greet.py")], ids=["setup.cfg", "tool.mutmut"])
def test_the_real_mutmut_credits_a_scenario_only_with_its_own_tests_kills(tmp_path, pyproject):
    toy(tmp_path, {"greet.py": GREET, "tests/test_greet.py": CREDIT, "pyproject.toml": pyproject})
    mutmut = Mutmut(tmp_path)
    assert mutmut.unavailable() is None
    assert mutmut.kills(["greet.py"], "TOY.H1", ["tests/test_greet.py"]) == (2, 0)  # test_unlinked kills both
    assert mutmut.kills(["greet.py"], "TOY.H2", ["tests/test_greet.py"]) == (2, 2)


@real
def test_the_real_mutmut_runs_a_test_outside_tests_with_its_root_conftest(tmp_path):
    test = 'import pytest\nfrom greet import greet\n\n\n@pytest.mark.spec("TOY.H1")\ndef test_h(word):\n    assert greet() == word\n'
    toy(tmp_path, {"greet.py": GREET, "conftest.py": 'import pytest\n\n\n@pytest.fixture\ndef word():\n    return "hello"\n',
                   "checks/test_h.py": test})
    assert Mutmut(tmp_path).kills(["greet.py"], "TOY.H1", ["checks/test_h.py"]) == (2, 2)
