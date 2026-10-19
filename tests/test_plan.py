import pytest

from redline.cli import main
from test_merged import merged, on_step, remote  # noqa: F401 (remote is a fixture)
from test_pr import AUDIT, github, pr  # noqa: F401 (github is a fixture)
from test_start import change, fresh_branch, merge_step, start  # noqa: F401 (change is a fixture)

PLAN = "redline/initiatives/greetings/plan.md"
VALID = """# Initiative: greetings
Goal: every visitor is greeted and seen off

## Phase 1: Greet
Changes: add-greet, add-wave
Stop: visitors are greeted by name

## Phase 2: See off
Changes: add-farewell
Stop: visitors are seen off too
"""
FAREWELL = {"redline/changes/add-farewell/steps.md": "# Steps: add-farewell\n\n## S: Spec for farewells\n\n## C: Close\n"}
WAVE = {"redline/changes/add-wave/steps.md": "# Steps: add-wave\n\n## S: Spec for waving\n\n## C: Close\n"}


def check_plan(repo, capsys, *args: str) -> tuple[int, str]:
    code = main(["check-plan", *args, "--repo", str(repo.path)])
    return code, capsys.readouterr().out


def complete(repo, change: str, steps: tuple[str, ...]) -> None:
    repo.git("checkout", "-q", "main")
    for step in steps:
        repo.commit(f"{step} done\n\nRedline-Step: {change}/{step}")


@pytest.fixture
def planned(change):
    change.commit("greetings plan", {PLAN: VALID, **FAREWELL, **WAVE})
    return change


def test_a_valid_plan_passes(planned, capsys):
    code, out = check_plan(planned, capsys)
    assert code == 0, out
    assert out.startswith("ok: 1 initiative")


def test_no_initiatives_pass(change, capsys):
    assert check_plan(change, capsys)[0] == 0


@pytest.mark.parametrize(("plan", "message"), [
    (VALID.replace("Goal: every visitor is greeted and seen off\n", ""), "no Goal: line"),
    (VALID.split("## Phase 1")[0], "no phases"),
    (VALID.replace("## Phase 2", "## Phase 3"), "phase 3 is out of order"),
    (VALID.replace("Changes: add-farewell\n", ""), "phase 2 has no changes"),
    (VALID.replace("Changes: add-farewell", "Changes: "), "phase 2 has no changes"),
    (VALID.replace("Stop: visitors are seen off too\n", ""), "phase 2 has no Stop: line"),
    (VALID.replace("Changes: add-farewell", "Changes: add-farewell, add-greet"), "add-greet is listed twice"),
], ids=["no-goal", "no-phases", "out-of-order", "no-changes", "empty-changes", "no-stop", "listed-twice"])
def test_a_broken_plan_fails(change, capsys, plan, message):
    change.commit("plan", {PLAN: plan})
    code, out = check_plan(change, capsys)
    assert code == 1
    assert message in out
    assert out.startswith("greetings: ")


def test_a_change_in_two_initiatives_fails(planned, capsys):
    other = "# Initiative: more\nGoal: more\n\n## Phase 1: More\nChanges: add-farewell\nStop: more\n"
    planned.commit("second plan", {"redline/initiatives/more/plan.md": other})
    code, out = check_plan(planned, capsys)
    assert code == 1
    assert "add-farewell is listed twice" in out


def test_one_initiative_is_checked_alone(planned, capsys):
    planned.commit("broken plan", {"redline/initiatives/more/plan.md": "# Initiative: more\n"})
    assert check_plan(planned, capsys, "greetings")[0] == 0
    assert check_plan(planned, capsys, "more")[0] == 1
    code, out = check_plan(planned, capsys, "nope")
    assert code == 2
    assert "no plan redline/initiatives/nope/plan.md" in out


def test_a_later_phase_waits_for_every_change_of_the_earlier_ones(planned, capsys):
    complete(planned, "add-wave", ("S", "C"))
    fresh_branch(planned, "farewell")
    code, out = start(planned, capsys, "add-farewell/S")
    assert code == 1
    assert "add-greet" in out and "phase 1" in out
    assert "add-wave" not in out  # complete: its last step is merged


def test_a_later_phase_starts_once_the_earlier_ones_are_complete(planned, capsys):
    complete(planned, "add-wave", ("S", "C"))
    complete(planned, "add-greet", ("S", "R", "G1", "G2", "C"))
    fresh_branch(planned, "farewell")
    code, out = start(planned, capsys, "add-farewell/S")
    assert code == 0, out


def test_a_planned_change_with_no_steps_is_not_complete(change, capsys):
    plan = VALID.replace("add-greet, add-wave", "add-wave, add-hello")
    change.commit("plan", {PLAN: plan, **FAREWELL, **WAVE})
    complete(change, "add-wave", ("S", "C"))
    fresh_branch(change, "farewell")
    code, out = start(change, capsys, "add-farewell/S")
    assert code == 1
    assert "add-hello" in out


def test_the_brief_names_the_initiative_the_phase_and_its_stop(planned, capsys):
    fresh_branch(planned, "spec")
    code, out = start(planned, capsys, "add-greet/S")
    assert code == 0, out
    assert "## Initiative: greetings" in out
    assert "Goal: every visitor is greeted and seen off" in out
    assert "Phase 1 of 2: Greet" in out
    assert "Stop: visitors are greeted by name" in out


def test_a_change_in_no_initiative_has_no_initiative_in_its_brief(change, capsys):
    fresh_branch(change, "spec")
    code, out = start(change, capsys, "add-greet/S")
    assert code == 0, out
    assert "Initiative" not in out


def close_greet(repo, capsys, remote) -> tuple[int, str]:
    complete(repo, "add-greet", ("S", "R", "G1", "G2"))
    remote.landing = "add-greet/C"
    on_step(repo, capsys, "C", "close")
    return merged(repo, capsys, "add-greet/C")


def test_completing_a_phase_announces_its_stopping_point_and_the_next_phase(planned, capsys, remote):
    complete(planned, "add-wave", ("S", "C"))
    code, out = close_greet(planned, capsys, remote)
    assert code == 0, out
    assert "change add-greet is complete" in out
    assert "greetings is at a stopping point: phase 1 (Greet) is complete" in out
    assert "Stop: visitors are greeted by name" in out
    assert "Next: phase 2 (See off): add-farewell" in out


def test_no_stopping_point_while_the_phase_has_an_incomplete_change(planned, capsys, remote):
    code, out = close_greet(planned, capsys, remote)
    assert code == 0, out
    assert "change add-greet is complete" in out
    assert "stopping point" not in out


def test_completing_the_last_phase_completes_the_initiative(change, capsys, remote):
    plan = VALID.split("## Phase 2")[0].replace("add-greet, add-wave", "add-greet")
    change.commit("plan", {PLAN: plan})
    code, out = close_greet(change, capsys, remote)
    assert code == 0, out
    assert "greetings is at a stopping point" in out
    assert "The initiative greetings is complete." in out


def test_pr_refuses_on_a_broken_plan(change, capsys, github):
    fresh_branch(change, "spec")
    assert start(change, capsys, "add-greet/S")[0] == 0
    change.commit("audit and a plan", {**AUDIT, PLAN: VALID.replace("Stop: visitors are seen off too\n", "")})
    code, out = pr(change, capsys)
    assert code == 1
    assert "check-plan: greetings: phase 2 has no Stop: line" in out
