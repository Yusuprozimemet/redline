"""A frozen test is frozen whichever change locked it; a closed change's entry moves to the later change (§4, §5)."""

import pytest
import yaml

from redline.cli import main
from redline.pr import gates
from test_check_break import mutator  # noqa: F401 (a fixture)
from test_close import HELD
from test_start import CHANGE, DELTA, change, fresh_branch, merge_step  # noqa: F401 (change is a fixture)

LOCK = "redline/contracts/lock.yaml"
OLD = "redline/changes/old-greet"
H1 = "#### Scenario GREET.H1 [hold]: the placeholder stays\n- THEN it returns nothing\n"
OLD_DELTA = f"## ADDED Requirements\n\n### Requirement: Placeholder\n\n{H1}"
MODIFIED = f"{DELTA}\n## MODIFIED Requirements\n\n### Requirement: Placeholder\n\n{H1}"
REMOVED = f"{DELTA}\n## REMOVED Requirements\n- GREET.H1: the placeholder is gone\n"
TEST = "tests/test_hold.py::test_h1"
EDITED = HELD.replace("assert True", "assert 1")
FROZEN = f"check-lock: GREET.H1: {TEST}: its lock entry changed since main, with no approved departure"
STALE = f"check-lock: old-greet: GREET.H1: {TEST} changed since it was locked"
APPROVED = f"Redline-Departure: {TEST} approved-by @maintainer: the placeholder may return 1"


def run(repo, *args: str) -> int:
    return main([*args, "--repo", str(repo.path)])


def locked(repo) -> dict:
    return yaml.safe_load((repo.path / LOCK).read_text(encoding="utf-8"))


def closed_old_greet(repo, delta: str, rigor: str = "standard") -> None:
    """old-greet added and locked GREET.H1 and closed; add-greet's S step, with `delta`, is merged."""
    repo.commit("old-greet", {f"{OLD}/proposal.md": f"# old-greet\nRigor: {rigor}\n",
                              f"{OLD}/specs/greet/delta.md": OLD_DELTA, "tests/test_hold.py": HELD})
    assert run(repo, "lock", "old-greet") == 0
    repo.commit("old-greet closed\n\nRedline-Step: old-greet/C")
    repo.commit("add-greet spec", {f"{CHANGE}/specs/greet/delta.md": delta})
    merge_step(repo, "S")


@pytest.fixture(autouse=True)
def fake_mutator(mutator):
    """The R gate runs check-break; in CI, where mutmut is installed, the real one would run on the toy."""
    return mutator


@pytest.fixture
def moved(change):
    closed_old_greet(change, MODIFIED)
    fresh_branch(change, "step")
    return change


def test_lock_moves_a_scenario_from_a_closed_change_unedited(moved, capsys):
    before = locked(moved)["old-greet"]["GREET.H1"][TEST]
    assert run(moved, "lock", "add-greet") == 0
    after = locked(moved)
    assert "old-greet" not in after  # its only entry moved, so it is dropped
    assert after["add-greet"]["GREET.H1"][TEST] == before
    assert run(moved, "check-lock", "old-greet") == 0  # closed: it asks for no test to be locked
    moved.commit("lock")
    assert not [f for f in gates(moved.path, "add-greet", "R") if f.startswith("check-lock")]


def test_a_move_keeps_reach_from_a_critical_closed_change(change):
    closed_old_greet(change, MODIFIED, rigor="critical")
    before = locked(change)["old-greet"]["GREET.H1"][TEST]
    assert set(before) == {"test", "reach"}
    assert run(change, "lock", "add-greet") == 0  # add-greet is standard, and still writes the reach
    assert locked(change)["add-greet"]["GREET.H1"][TEST] == before


@pytest.mark.parametrize("step", ["S", "R", "G1", "C"])
def test_editing_another_changes_frozen_test_is_a_departure_at_every_step(moved, step):
    moved.commit("edit", {"tests/test_hold.py": EDITED})
    assert STALE in gates(moved.path, "add-greet", step)  # the no-base check, on every change the lock names
    assert run(moved, "lock", "add-greet") == 0
    moved.commit("relock")
    failures = gates(moved.path, "add-greet", step)
    assert FROZEN in failures and STALE not in failures  # by test, against main's lock
    moved.git("commit", "-q", "--amend", "-m", f"relock\n\n{APPROVED}")
    assert FROZEN not in gates(moved.path, "add-greet", step)


def test_a_closed_changes_entry_is_never_rewritten_with_a_later_hash(moved):
    moved.commit("edit", {"tests/test_hold.py": EDITED})
    assert run(moved, "lock", "add-greet") == 0
    assert "old-greet" not in locked(moved)


def test_removing_a_closed_changes_hold_scenario_moves_it_out_and_deleting_its_test_is_a_departure(change):
    closed_old_greet(change, REMOVED)
    fresh_branch(change, "step")
    (change.path / "tests/test_hold.py").unlink()
    assert run(change, "lock", "add-greet") == 0
    assert "old-greet" not in (locked(change) or {})
    change.commit("delete the frozen test")
    assert FROZEN in gates(change.path, "add-greet", "R")
