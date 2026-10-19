import hashlib

import yaml

from redline.cli import main
from test_check_break import HOLD_TESTS, PASSING, check_break, holds, mutator  # noqa: F401 (fixtures)
from test_ci import ci
from test_pr import RED_TESTS, github, pr  # noqa: F401 (github is a fixture)
from test_start import change, fresh_branch, merge_step, start  # noqa: F401 (change is a fixture)

LOCK = "redline/contracts/lock.yaml"
METHOD = """
class TestHolds:
    @pytest.mark.spec("GREET.H1")
    def test_again(self):
        assert placeholder() is None
"""
H1 = 'def test_h1():\n    assert placeholder() is None'
WEAKENED = PASSING.replace(H1, "def test_h1():\n    assert True")
APPROVED = "Redline-Departure: test_hold.py::test_h1 approved-by @maintainer: GREET.S1 covers it now"


def lock(repo, capsys) -> None:
    assert main(["lock", "add-greet", "--repo", str(repo.path)]) == 0
    capsys.readouterr()


def check_lock(repo, capsys, *args: str) -> tuple[int, str]:
    code = main(["check-lock", "add-greet", "--repo", str(repo.path), *args])
    return code, capsys.readouterr().out


def test_lock_hashes_each_test_function_check_break_counts(holds, capsys, mutator):
    holds.commit("hold tests", {"test_hold.py": HOLD_TESTS + METHOD})
    lock(holds, capsys)
    locked = yaml.safe_load((holds.path / LOCK).read_text(encoding="utf-8"))["add-greet"]
    h1 = hashlib.sha256(f'@pytest.mark.spec("GREET.H1")\n{H1}\n'.encode()).hexdigest()
    assert sorted(locked) == ["GREET.H1", "GREET.H3"]  # H2's only marker has new=True
    assert locked["GREET.H1"]["test_hold.py::test_h1"] == h1
    assert sorted(locked["GREET.H1"]) == ["test_hold.py::TestHolds::test_again", "test_hold.py::test_h1"]
    assert "GREET.H2: no test links it without new=True" in check_break(holds, capsys)[1]
    code, out = check_lock(holds, capsys)
    assert code == 0, out
    assert "ok: 3 locked test(s) match the code" in out


def test_check_lock_prints_each_difference_but_not_the_rest_of_the_file(holds, capsys):
    holds.commit("hold tests", {"test_hold.py": PASSING})
    lock(holds, capsys)
    edited = "# a comment\n" + WEAKENED.replace('spec("GREET.H2")', 'spec("GREET.H2", new=True)') + (
        '\n@pytest.mark.spec("GREET.H3")\ndef test_h3b():\n    assert True\n\n'
        '@pytest.mark.spec("GREET.S1", new=True)\ndef test_s1():\n    assert False\n')
    holds.commit("edits", {"test_hold.py": edited})
    code, out = check_lock(holds, capsys)
    assert code == 1
    assert out.splitlines() == [
        "GREET.H1: test_hold.py::test_h1 changed since it was locked",
        "GREET.H2: test_hold.py::test_h2 is locked but missing",
        "GREET.H3: test_hold.py::test_h3b isn't in the lock",
    ]


def test_the_red_step_gate_needs_every_hold_test_in_the_lock(holds, capsys, mutator, github):
    merge_step(holds, "S")
    fresh_branch(holds, "red")
    assert start(holds, capsys, "add-greet/R")[0] == 0
    holds.commit("red tests", {"tests/test_greet.py": RED_TESTS, "test_hold.py": PASSING})
    code, out = pr(holds, capsys)
    assert code == 1
    assert "check-lock: GREET.H1: test_hold.py::test_h1 isn't in the lock" in out
    lock(holds, capsys)
    holds.commit("lock")
    code, out = pr(holds, capsys)
    assert code == 0, out


def test_a_green_step_changes_a_frozen_test_only_with_an_approved_departure(holds, capsys, github):
    merge_step(holds, "S")
    holds.commit("red tests", {"tests/test_greet.py": RED_TESTS, "test_hold.py": PASSING})
    lock(holds, capsys)
    holds.commit("R\n\nRedline-Step: add-greet/R")
    fresh_branch(holds, "g1")
    assert start(holds, capsys, "add-greet/G1")[0] == 0
    holds.commit("weaken", {"test_hold.py": WEAKENED})
    code, out = pr(holds, capsys)
    assert code == 1
    assert "check-lock: GREET.H1: test_hold.py::test_h1 changed since it was locked" in out
    lock(holds, capsys)
    holds.commit("relock\n\nRedline-Departure: test_hold.py::test_h1")  # names no approver
    code, out = pr(holds, capsys)
    assert code == 1
    assert "check-lock: GREET.H1: test_hold.py::test_h1: its lock entry changed since main, with no approved departure" in out
    assert "changed since it was locked" not in out
    holds.git("commit", "-q", "--amend", "-m", f"relock\n\n{APPROVED}")
    code, out = check_lock(holds, capsys, "--base", "main")
    assert code == 0, out
    assert "CI will need the `redline:departure` label from a maintainer" in out
    code, out = pr(holds, capsys)
    assert code == 0, out
    assert "CI will need the `redline:departure` label from a maintainer" in out


def test_ci_runs_check_lock_at_a_green_step(holds, capsys):
    merge_step(holds, "S")
    merge_step(holds, "R")
    fresh_branch(holds, "g1")
    holds.commit("G1\n\nRedline-Step: add-greet/G1", {"test_hold.py": PASSING})
    code, out = ci(holds, capsys, "pr")
    assert code == 1
    assert "check-lock: GREET.H1: test_hold.py::test_h1 isn't in the lock" in out
