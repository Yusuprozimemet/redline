"""The real Jest and Stryker on the toy project in tests/toys/jest. Skipped unless REDLINE_REAL_RUNNERS=1,
which the `runners` CI job sets after `npm ci` there; with it, a missing tool fails. They prove the helper,
REDLINE_SPEC, Stryker's counts, and check-break end to end on a git repository holding the toy.
See specs/, §5."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from redline.breaks import Stryker, check_break
from redline.runner import install

TOY = Path(__file__).parent / "toys" / "jest"
pytestmark = pytest.mark.skipif(os.environ.get("REDLINE_REAL_RUNNERS") != "1",
                                reason="the real Jest and Stryker run in the runners CI job")
# Written by the toy fixture, never committed or read in Redline's tree: no spec there declares TOY.H1 or TOY.H2 (O-SELF5)
TESTS = """const { spec } = require("../redline/runners/jest");
const { adult } = require("./adult");

spec("TOY.H1").test("a grown-up is an adult", () => {
  expect(adult(30)).toBe(true);
});

spec("TOY.H2").test("an adult starts at 18", () => {
  expect(adult(18)).toBe(true);
  expect(adult(17)).toBe(false);
});
"""


@pytest.fixture(scope="module")
def toy():
    install(TOY, "jest")
    (TOY / "src" / "adult.test.js").write_text(TESTS, encoding="utf-8")
    yield TOY
    shutil.rmtree(TOY / "redline")
    (TOY / "src" / "adult.test.js").unlink()


def jest(toy, *paths, sid=None) -> subprocess.CompletedProcess:
    npx = shutil.which("npx")
    assert npx, "npx isn't installed"
    env = {key: value for key, value in os.environ.items() if key != "REDLINE_SPEC"}
    env |= {"REDLINE_SPEC": sid} if sid else {}
    return subprocess.run([npx, "--no-install", "jest", "--ci", *paths], cwd=toy, capture_output=True,
                          encoding="utf-8", errors="replace", env=env)


def test_jest_runs_every_test_and_doesnt_take_the_helper_for_a_test_file(toy):
    done = jest(toy)
    assert done.returncode == 0, done.stderr
    assert "Test Suites: 1 passed, 1 total" in done.stderr
    assert "Tests:       2 passed, 2 total" in done.stderr


def test_redline_spec_runs_one_scenarios_tests_alone(toy):
    done = jest(toy, sid="TOY.H1")
    assert done.returncode == 0, done.stderr
    assert "Tests:       1 skipped, 1 passed, 2 total" in done.stderr


@pytest.mark.parametrize("expected, code", [("2", 0), ("1", 1)])
def test_a_new_test_runs_as_test_failing_so_one_that_passes_fails_the_run(toy, expected, code):
    path = toy / "src" / "new.test.js"
    path.write_text('const { spec } = require("../redline/runners/jest");\n\n'
                    f'spec("TOY.S1", {{ new: true }}).test("not built yet", () => {{\n  expect(1).toBe({expected});\n}});\n')
    try:
        done = jest(toy, "src/new.test.js")
    finally:
        path.unlink()
    assert done.returncode == code, done.stderr


def test_stryker_kills_only_what_the_scenarios_tests_kill(toy):
    stryker = Stryker(toy)
    assert stryker.unavailable() is None
    assert stryker.kills(["src/adult.js"], "TOY.H1") == (6, 4)  # REDLINE_SPEC reaches its Jest workers
    assert stryker.kills(["src/adult.js"], "TOY.H2") == (6, 6)
    assert not (toy / "reports").exists()


DELTA = """## ADDED Requirements

### Requirement: Adults

#### Scenario TOY.H1 [hold]: a grown-up is an adult
- THEN adult(30) is true

#### Scenario TOY.H2 [hold]: an adult starts at 18
- THEN adult(18) is true AND adult(17) is false

#### Scenario TOY.H3 [hold]: arithmetic still works
- THEN 1 + 1 is 2

### Premises
- P1: adult compares the age with 18 — `src/adult.js:1-3` (`adult`)
"""
H3 = 'spec("TOY.H3").test("asserts nothing about adult", () => {\n  expect(1 + 1).toBe(2);\n});\n'


@pytest.fixture
def toy_repo(toy, tmp_path):
    """A git repository holding the toy and a change whose premise cites src/adult.js; node_modules is linked."""
    repo = tmp_path / "toy"
    shutil.copytree(toy, repo, ignore=shutil.ignore_patterns("node_modules"))
    link = repo / "node_modules"
    try:
        link.symlink_to(toy / "node_modules", target_is_directory=True)
    except OSError:  # Windows without the right to make symlinks: a junction
        import _winapi
        _winapi.CreateJunction(str(toy / "node_modules"), str(link))
    with open(repo / "src" / "adult.test.js", "a", encoding="utf-8") as tests:
        tests.write("\n" + H3)
    (repo / ".gitignore").write_text("node_modules\nreports/\n.stryker-tmp/\n", encoding="utf-8")  # the toy's ignores redline/
    (repo / "redline" / "changes" / "toy" / "specs" / "adult").mkdir(parents=True)
    (repo / "redline" / "changes" / "toy" / "specs" / "adult" / "delta.md").write_text(DELTA, encoding="utf-8")
    for command in (["init", "-q", "-b", "main"], ["add", "-A"],
                    ["-c", "user.name=Toy", "-c", "user.email=toy@example.com", "commit", "-q", "-m", "toy"]):
        subprocess.run(["git", *command], cwd=repo, check=True, capture_output=True)
    yield repo
    try:
        link.unlink()
    except OSError:
        os.rmdir(link)  # a junction; removing it leaves the toy's node_modules alone


def test_check_break_runs_jest_and_stryker_end_to_end(toy_repo):
    report = check_break(toy_repo, "toy")
    assert report.skipped == {}
    assert report.results == {"TOY.H1": None, "TOY.H2": None,
                              "TOY.H3": "its tests survive every mutant (0 of 6 killed, in src/adult.js)"}
