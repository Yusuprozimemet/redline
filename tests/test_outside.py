import pytest

from test_check_break import PASSING, holds  # noqa: F401 (holds is a fixture)
from test_check_lines import lines
from test_ci import BROKEN, ci
from test_lock import APPROVED, WEAKENED, lock
from test_pr import github  # noqa: F401 (a fixture)
from test_start import CHANGE, change, fresh_branch  # noqa: F401 (change is a fixture)

OUTSIDE = "ok: a PR outside any step passes check-lines, check-plan, check-lock and the test suite"
RULE = "rules:\n  premise:\n    - Cite where a value is stored, not only where it is read\n"
TOUCHED = "refused: outside any step a PR can't touch a change, the lock or the specs:"


def outside(repo, files: dict[str, str] | None = None, message: str = "a rule from retro") -> None:
    """A branch off main whose commits carry no Redline-Step trailer; main has a passing test."""
    repo.git("checkout", "-q", "main")
    repo.commit("a test", {"tests/test_ok.py": "def test_ok():\n    assert True\n"})
    fresh_branch(repo, "outside")
    repo.commit(message, files)


def test_a_pr_outside_any_step_runs_the_gates_that_hold_for_any_pr(change, capsys):
    outside(change, {"redline/config.yaml": RULE})
    code, out = ci(change, capsys, "pr", "--base", "main")
    assert code == 0, out
    assert OUTSIDE in out


@pytest.mark.parametrize("path", [f"{CHANGE}/defects.md", "redline/contracts/lock.yaml", "redline/specs/greet/spec.md"])
def test_a_pr_outside_any_step_cant_touch_a_change_the_lock_or_the_specs(change, capsys, path):
    outside(change, {"redline/config.yaml": RULE, path: "edited\n"})
    code, out = ci(change, capsys, "pr", "--base", "main")
    assert code == 1
    assert f"{TOUCHED} {path}" in out
    assert "check-" not in out and "suite" not in out


def test_moving_a_file_out_of_a_change_touches_the_change(change, capsys):
    outside(change)
    change.git("mv", f"{CHANGE}/steps.md", "steps.md")
    change.commit("move the steps out")
    code, out = ci(change, capsys, "pr", "--base", "main")
    assert code == 1
    assert f"{TOUCHED} {CHANGE}/steps.md" in out


def test_a_manual_check_outside_any_step_fails(change, capsys):
    trailer = "Redline-Manual: GREET.M1 checked-by @alice: it looks right"
    outside(change, {"notes.md": "a note\n"}, f"a note\n\n{trailer}")
    code, out = ci(change, capsys, "pr", "--base", "main")
    assert code == 1
    assert f"manual: {trailer}: a person's check counts at the C step only" in out


def test_a_pr_outside_any_step_over_400_lines_needs_oversized_and_its_label(change, capsys, github):
    outside(change, {"notes.md": lines(401)})
    code, out = ci(change, capsys, "pr", "--base", "main", "--pr", "1")
    assert code == 1
    assert "check-lines: 401 changed lines, over the limit of 400" in out
    change.commit("why\n\nOversized: a table of names, read as a whole")
    code, out = ci(change, capsys, "pr", "--base", "main", "--pr", "1")
    assert code == 1
    assert "needs the `redline:oversized` label from a maintainer" in out
    github.applied["redline:oversized"] = "maintainer"
    code, out = ci(change, capsys, "pr", "--base", "main", "--pr", "1")
    assert code == 0, out
    assert OUTSIDE in out


def test_a_pr_outside_any_step_cant_change_a_frozen_test_even_with_a_departure(holds, capsys):
    holds.commit("hold tests", {"test_hold.py": PASSING})
    lock(holds, capsys)
    holds.commit("lock")
    outside(holds, {"test_hold.py": WEAKENED}, f"weaken\n\n{APPROVED}")
    code, out = ci(holds, capsys, "pr", "--base", "main")
    assert code == 1
    assert "check-lock: add-greet: GREET.H1: test_hold.py::test_h1 changed since it was locked" in out


def test_a_pr_outside_any_step_prints_every_failure(change, capsys):
    outside(change, {"tests/test_broken.py": BROKEN, "redline/initiatives/x/plan.md": "# Initiative: x\n"})
    code, out = ci(change, capsys, "pr", "--base", "main")
    assert code == 1
    assert "check-plan: x: no Goal: line" in out
    assert "suite: the test suite failed" in out
    assert "ok:" not in out
