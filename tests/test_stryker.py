"""The Mutator seam: one mutation tool per runner, and Stryker's counts, with its run faked. See docs/design.md, §5."""

import json
import subprocess

import pytest

from redline import breaks
from redline.breaks import MUTATORS, Mutmut, Stryker
from redline.runner import RUNNERS
from test_check_break import mutator  # noqa: F401 (a fixture)

STATUSES = ["Killed", "Survived", "NoCoverage", "Timeout", "CompileError", "RuntimeError", "Ignored", "Pending"]
PACKAGES = ("node_modules/@stryker-mutator/core", "node_modules/@stryker-mutator/jest-runner")


def test_every_runner_has_a_mutation_tool():
    assert set(MUTATORS) == {runner.name for runner in RUNNERS}
    assert MUTATORS["pytest"] is Mutmut and MUTATORS["jest"] is Stryker


def test_the_fixture_replaces_every_runners_tool(mutator):
    assert set(breaks.MUTATORS) == {runner.name for runner in RUNNERS}
    assert all(tool is mutator for tool in breaks.MUTATORS.values())


@pytest.fixture
def project(tmp_path, monkeypatch):
    for package in PACKAGES:
        (tmp_path / package).mkdir(parents=True)
    monkeypatch.setattr("redline.breaks.shutil.which", lambda name: f"/bin/{name}")
    return tmp_path


def fake_run(monkeypatch, returncode=0) -> list:
    calls = []

    def run(argv, cwd, env, **kwargs):
        calls.append((argv, cwd, env["REDLINE_SPEC"]))
        report = cwd / "reports" / "mutation" / "mutation.json"
        report.parent.mkdir(parents=True)
        mutants = [{"id": str(i), "status": status} for i, status in enumerate(STATUSES)]
        report.write_text(json.dumps({"files": {"src/a.js": {"mutants": mutants[:3]}, "src/b.js": {"mutants": mutants[3:]}}}))
        return subprocess.CompletedProcess(argv, returncode, "", "stryker broke")

    monkeypatch.setattr("redline.breaks.subprocess.run", run)
    return calls


def test_stryker_counts_killed_of_made_and_deletes_its_report(project, monkeypatch):
    calls = fake_run(monkeypatch)
    assert Stryker(project).kills(["src/a.js", "src/b.js"], "TOY.H1") == (4, 1)  # a timeout made, not killed
    assert calls == [(["/bin/npx", "--no-install", "stryker", "run", "--mutate", "src/a.js,src/b.js",
                       "--testRunner", "jest", "--reporters", "json"], project, "TOY.H1")]
    assert not (project / "reports").exists()


def test_a_failed_stryker_run_is_an_error(project, monkeypatch):
    fake_run(monkeypatch, returncode=1)
    with pytest.raises(RuntimeError, match="stryker broke"):
        Stryker(project).kills(["src/a.js"], "TOY.H1")


def test_stryker_is_unavailable_without_npx_or_its_packages(project, monkeypatch):
    assert Stryker(project).unavailable() is None
    (project / PACKAGES[1]).rmdir()
    assert Stryker(project).unavailable() == "@stryker-mutator/jest-runner isn't installed"
    (project / PACKAGES[0]).rmdir()
    assert Stryker(project).unavailable() == "@stryker-mutator/core isn't installed"
    monkeypatch.setattr("redline.breaks.shutil.which", lambda name: None)
    assert Stryker(project).unavailable() == "npx isn't installed"
