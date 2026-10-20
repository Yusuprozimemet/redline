"""A change whose C step is merged on main is closed: its delta stops counting as a declaration (§4)."""

from redline.breaks import holds
from redline.links import check_links
from redline.premises import check_premises
from test_check_links import DELTA, SPEC, marked, run, scenarios

LATER = "redline/changes/add-hi/specs/toy/delta.md"


def close(repo, change: str = "add-bye", step: str = "C") -> None:
    repo.commit(f"{step}\n\nRedline-Step: {change}/{step}")


def test_a_later_change_may_modify_a_scenario_a_closed_change_added(repo, capsys):
    repo.commit("A closed", {SPEC: scenarios("TOY.S1"), DELTA: scenarios("TOY.S1"), "tests/test_toy.py": marked("TOY.S1")})
    close(repo)
    repo.commit("B modifies", {LATER: scenarios("TOY.S1")})
    assert run(repo, capsys) == (0, ["ok: 1 scenarios, each linked to a test"])


def test_until_its_c_step_merges_a_change_still_declares(repo, capsys):
    repo.commit("A open", {SPEC: scenarios("TOY.S1"), DELTA: scenarios("TOY.S1"), "tests/test_toy.py": marked("TOY.S1")})
    close(repo, step="G1")
    repo.commit("B modifies", {LATER: scenarios("TOY.S1")})
    assert run(repo, capsys) == (1, [f"duplicate scenario TOY.S1: {DELTA}:3, {LATER}:3, {SPEC}:3"])


def test_a_c_step_only_on_a_branch_does_not_close(repo, capsys):
    repo.commit("A", {SPEC: scenarios("TOY.S1"), DELTA: scenarios("TOY.S1"), "tests/test_toy.py": marked("TOY.S1")})
    repo.git("checkout", "-q", "-b", "c")
    close(repo)
    repo.commit("B modifies", {LATER: scenarios("TOY.S1")})
    assert run(repo, capsys)[0] == 1


def test_a_scenario_removed_after_its_change_closed_is_unknown(repo, capsys):
    repo.commit("A closed", {SPEC: scenarios("TOY.S1", "TOY.S2"), DELTA: scenarios("TOY.S2"),
                             "tests/test_toy.py": marked("TOY.S1", "TOY.S2")})
    close(repo)
    repo.commit("B removes", {SPEC: scenarios("TOY.S1"), LATER: "## REMOVED Requirements\n- TOY.S2: gone\n"})
    assert check_links(repo.path).gaps == ["unknown scenario TOY.S2 (tests/test_toy.py:7): no spec declares it"]


def test_a_closed_changes_hold_tag_is_not_a_hold(repo):
    repo.commit("A closed", {SPEC: scenarios("TOY.H1", tag="hold"), DELTA: scenarios("TOY.H1", tag="hold")})
    close(repo)
    repo.commit("B makes it new", {LATER: scenarios("TOY.H1")})
    assert holds(repo.path) == ["TOY.H1"]  # the living spec still says hold until B's C step
    repo.commit("B closes", {SPEC: scenarios("TOY.H1")})
    assert holds(repo.path) == []
    assert holds(repo.path, "add-bye") == ["TOY.H1"]  # its own checks still read it


def test_check_premises_without_a_change_skips_closed_changes(repo):
    stale = "### Premises\n- P1: Gone — `auth/gone.py:1`\n"
    repo.commit("A closed", {DELTA: scenarios("TOY.S1") + stale})
    close(repo)
    assert check_premises(repo.path).bad == []
    assert check_premises(repo.path, "add-bye").bad == [f"{DELTA}:7: auth/gone.py:1: no such file"]
