import hashlib

import pytest
import yaml

from redline.cli import main
from test_check_break import holds  # noqa: F401 (a fixture)
from test_lock import H1, LOCK, check_lock, lock
from test_pr import RED_TESTS, github, pr  # noqa: F401 (github is a fixture)
from test_start import CHANGE, STEPS, change, fresh_branch, merge_step, start  # noqa: F401 (change is a fixture)

TIMED = """import pytest
from greet import placeholder

TIMEOUT = 5
pytestmark = pytest.mark.timeout(30)

def wait(timeout=TIMEOUT):
    return timeout

def unrelated():
    return 1

@pytest.fixture
def ready():
    return wait()

@pytest.mark.spec("GREET.H1")
def test_h1(ready, tick):
    assert placeholder() is None

@pytest.mark.spec("GREET.H2")
def test_h2():
    assert True

@pytest.mark.spec("GREET.H3")
def test_h3():
    assert placeholder() is None
"""
CONFTEST = """import time
import pytest

@pytest.fixture
def tick():
    time.sleep(0.1)

@pytest.fixture(autouse=True)
def settle():
    time.sleep(0.2)

@pytest.fixture
def idle():
    time.sleep(9)
"""
FILES = {"test_hold.py": TIMED, "conftest.py": CONFTEST, "pytest.ini": "[pytest]\ntimeout = 60\n"}
REACHED = "GREET.H1: test_hold.py::test_h1: a fixture, helper, mark or setting it reaches changed since it was locked"
UNREACHED = "GREET.H1: test_hold.py::test_h1 is locked without what it reaches; the change is critical, so re-run `redline lock`"


@pytest.fixture
def critical(holds):
    holds.commit("critical", {f"{CHANGE}/proposal.md": "# Proposal\n\nRigor: critical\n", **FILES})
    return holds


def entry(repo, test: str = "test_hold.py::test_h1"):
    return yaml.safe_load((repo.path / LOCK).read_text(encoding="utf-8"))["add-greet"]["GREET.H1"][test]


def test_a_critical_lock_hashes_the_test_and_what_it_reaches(critical, capsys):
    lock(critical, capsys)
    locked = entry(critical)
    assert sorted(locked) == ["reach", "test"]
    assert locked["test"] == hashlib.sha256(f'@pytest.mark.spec("GREET.H1")\n{H1}\n'.replace(
        "def test_h1():", "def test_h1(ready, tick):").encode()).hexdigest()
    assert check_lock(critical, capsys) == (0, "ok: 3 locked test(s) match the code\n")
    critical.commit("lower", {f"{CHANGE}/proposal.md": "Rigor: standard\n", "pytest.ini": "[pytest]\n"})
    assert REACHED in check_lock(critical, capsys)[1].splitlines()  # a reach the lock has is checked


@pytest.mark.parametrize("path, old, new", [
    ("test_hold.py", "TIMEOUT = 5", "TIMEOUT = 50"),  # a constant a helper reads
    ("test_hold.py", "return timeout", "return timeout * 2"),  # a helper a fixture calls
    ("test_hold.py", "return wait()", "return wait(60)"),  # a fixture in the test's file
    ("test_hold.py", "timeout(30)", "timeout(300)"),  # the module's pytestmark
    ("conftest.py", "sleep(0.1)", "sleep(1)"),  # a fixture in conftest.py
    ("conftest.py", "sleep(0.2)", "sleep(2)"),  # an autouse fixture
    ("pytest.ini", "timeout = 60", "timeout = 600"),  # pytest-timeout's setting
])
def test_a_longer_wait_anywhere_the_test_reaches_is_a_difference(critical, capsys, path, old, new):
    lock(critical, capsys)
    critical.commit("wait longer", {path: FILES[path].replace(old, new)})
    assert REACHED in check_lock(critical, capsys)[1].splitlines()


def test_code_the_test_doesnt_reach_isnt_in_its_lock_entry(critical, capsys):
    lock(critical, capsys)
    critical.commit("elsewhere", {
        "greet.py": "def placeholder():\n    return None\n",  # imported: the code under test
        "test_hold.py": TIMED.replace("return 1", "return 2").replace(  # a helper nothing reaches; test_h3
            "def test_h3():\n    assert placeholder() is None", "def test_h3():\n    assert True"),
        "conftest.py": CONFTEST.replace("sleep(9)", "sleep(90)"),  # a fixture nothing requests
    })
    code, out = check_lock(critical, capsys)
    assert code == 1
    assert out.splitlines() == ["GREET.H3: test_hold.py::test_h3 changed since it was locked"]


def test_a_plain_entry_still_reads_and_adding_its_reach_isnt_a_change_since_main(holds, capsys):
    holds.commit("R\n\nRedline-Step: add-greet/R", FILES)
    lock(holds, capsys)
    holds.commit("lock")
    assert isinstance(entry(holds), str)
    fresh_branch(holds, "g1")
    holds.commit("critical", {f"{CHANGE}/proposal.md": "Rigor: critical\n"})
    assert UNREACHED in check_lock(holds, capsys)[1].splitlines()
    lock(holds, capsys)
    holds.commit("relock")
    assert check_lock(holds, capsys, "--base", "main") == (0, "ok: 3 locked test(s) match the code\n")


def test_the_level_comes_from_the_proposal_then_the_config(holds, capsys):
    holds.commit("default", {"redline/config.yaml": "rigor: critical\n", **FILES})
    lock(holds, capsys)
    assert sorted(entry(holds)) == ["reach", "test"]
    holds.commit("unknown", {f"{CHANGE}/proposal.md": "Rigor: urgent\n"})
    assert main(["lock", "add-greet", "--repo", str(holds.path)]) == 2
    assert "add-greet: unknown rigor level `urgent`" in capsys.readouterr().out


def test_a_green_step_changes_what_a_test_reaches_only_with_an_approved_departure(critical, capsys, github):
    critical.commit("track", {f"{CHANGE}/steps.md": STEPS.replace("Owns: GREET.S1\n", "Owns: GREET.S1\nTrack: greet.py\n")})
    merge_step(critical, "S")
    critical.commit("R\n\nRedline-Step: add-greet/R", {"tests/test_greet.py": RED_TESTS})
    lock(critical, capsys)
    critical.commit("lock")
    fresh_branch(critical, "g1")
    assert start(critical, capsys, "add-greet/G1")[0] == 0
    critical.commit("poll longer", {"conftest.py": CONFTEST.replace("sleep(0.1)", "sleep(10)")})
    lock(critical, capsys)
    critical.commit("relock")
    code, out = pr(critical, capsys)
    assert code == 1
    assert "check-lock: GREET.H1: test_hold.py::test_h1: its lock entry changed since main, with no approved departure" in out
    approved = "Redline-Departure: test_hold.py::test_h1 approved-by @maintainer: the event now takes 10 s"
    critical.git("commit", "-q", "--amend", "-m", f"relock\n\n{approved}")
    code, out = pr(critical, capsys)
    assert code == 0, out
    assert "CI will need the `redline:departure` label from a maintainer" in out
