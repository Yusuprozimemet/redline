import pytest

from redline.cli import main

CHANGE = "redline/changes/add-greet"
STEPS = """# Steps: add-greet

## S: Spec for greeting

## R: Red tests for greeting
Owns: GREET.S1, GREET.S2

## G1: Greet by name
Owns: GREET.S1

## G2: Greet a crowd
Owns: GREET.S2

## C: Close

## Open items
- O1 [G1]: decide on the punctuation
- O2 [G2]: names with spaces
"""
DELTA = """## ADDED Requirements

### Requirement: Greeting

#### Scenario GREET.S1 [new]: greets by name
- GIVEN the name "Ada"
- WHEN greet is called
- THEN it returns "Hello, Ada!"

#### Scenario GREET.S2 [new]: greets a crowd
- GIVEN two names
- THEN both are greeted

### Premises
- P1: Only a placeholder exists so far — `greet.py:1` (`placeholder`)
"""


@pytest.fixture
def change(repo):
    repo.commit("add-greet spec", {
        f"{CHANGE}/steps.md": STEPS,
        f"{CHANGE}/specs/greet/delta.md": DELTA,
        "greet.py": "def placeholder():\n    pass\n",
    })
    return repo


def merge_step(repo, step: str) -> None:
    """Land a step on main, as its merged PR would."""
    repo.git("checkout", "-q", "main")
    repo.commit(f"{step} done\n\nRedline-Step: add-greet/{step}")


def fresh_branch(repo, name: str) -> None:
    repo.git("checkout", "-q", "main")
    repo.git("checkout", "-q", "-b", name)


def start(repo, capsys, step: str) -> tuple[int, str]:
    code = main(["start", step, "--repo", str(repo.path)])
    return code, capsys.readouterr().out


def test_first_step_starts_on_a_fresh_branch(change, capsys):
    fresh_branch(change, "spec")
    code, out = start(change, capsys, "add-greet/S")
    assert code == 0
    assert "Goal: Spec for greeting" in out


def test_brief_has_goal_owned_scenarios_cited_files_and_open_items(change, capsys):
    merge_step(change, "S")
    merge_step(change, "R")
    fresh_branch(change, "g1")
    code, out = start(change, capsys, "add-greet/G1")
    assert code == 0
    assert out.startswith("# Brief: add-greet/G1\n")
    assert "Goal: Greet by name" in out
    assert '#### Scenario GREET.S1 [new]: greets by name\n- GIVEN the name "Ada"\n' in out
    assert '- THEN it returns "Hello, Ada!"' in out
    assert f"{CHANGE}/specs/greet/delta.md:5" in out
    assert "- P1: Only a placeholder exists so far — `greet.py:1` (`placeholder`)" in out
    assert "- O1: decide on the punctuation" in out
    assert "GREET.S2" not in out  # owned by G2
    assert "O2" not in out.split("## Progress")[0]  # the progress lists it as a later step's


def test_scenario_found_in_the_living_specs(change, capsys):
    change.commit("living", {"redline/specs/greet/spec.md": "#### Scenario GREET.S0 [hold]: says hi\n- THEN hi\n"})
    change.commit("own it", {f"{CHANGE}/steps.md": STEPS.replace("Owns: GREET.S1, GREET.S2", "Owns: GREET.S0")})
    merge_step(change, "S")
    fresh_branch(change, "r")
    code, out = start(change, capsys, "add-greet/R")
    assert code == 0
    assert "#### Scenario GREET.S0 [hold]: says hi\n- THEN hi" in out


def test_refuses_when_the_previous_step_is_not_merged_on_main(change, capsys):
    merge_step(change, "S")
    change.git("checkout", "-q", "-b", "unmerged-r")
    change.commit("R on a branch\n\nRedline-Step: add-greet/R")
    fresh_branch(change, "g1")
    code, out = start(change, capsys, "add-greet/G1")
    assert code == 1
    assert "previous step add-greet/R is not merged on main" in out
    assert "Brief" not in out


def test_trailer_must_name_the_step_exactly(change, capsys):
    merge_step(change, "S")
    change.commit("not R\n\nRedline-Step: add-greet/R2")
    fresh_branch(change, "g1")
    assert start(change, capsys, "add-greet/G1")[0] == 1


@pytest.mark.parametrize("setup", ["on main", "ahead of main", "behind main"])
def test_refuses_unless_the_branch_is_fresh_from_main(change, capsys, setup):
    if setup != "on main":
        fresh_branch(change, "spec")
    if setup == "ahead of main":
        change.commit("early work", {"greet.py": "pass\n"})
    if setup == "behind main":
        change.git("checkout", "-q", "main")
        change.commit("main moves on", {"other.py": "pass\n"})
        change.git("checkout", "-q", "spec")
    code, out = start(change, capsys, "add-greet/S")
    assert code == 1
    assert "fresh from main" in out


def test_one_open_step_at_a_time_until_it_merges(change, capsys):
    fresh_branch(change, "spec")
    assert start(change, capsys, "add-greet/S")[0] == 0
    assert start(change, capsys, "add-greet/S")[0] == 0  # the same step can print its brief again
    merge_step(change, "S")
    change.git("checkout", "-q", "-b", "r")
    assert start(change, capsys, "add-greet/R")[0] == 0
    fresh_branch(change, "g2")
    code, out = start(change, capsys, "add-greet/G2")
    assert code == 1
    assert "step add-greet/R is still open" in out


@pytest.mark.parametrize(("step", "message"), [
    ("add-greet/G9", "no step G9 in redline/changes/add-greet/steps.md"),
    ("nope/S", "no steps file redline/changes/nope/steps.md"),
    ("add-greet", "a step is <change>/<step>"),
])
def test_unknown_step_is_an_error(change, capsys, step, message):
    fresh_branch(change, "x")
    code, out = start(change, capsys, step)
    assert code == 2
    assert message in out


def test_owned_scenario_that_no_spec_declares_is_an_error(change, capsys):
    change.commit("typo", {f"{CHANGE}/steps.md": STEPS.replace("Owns: GREET.S1, GREET.S2", "Owns: GREET.TYPO")})
    merge_step(change, "S")
    fresh_branch(change, "r")
    code, out = start(change, capsys, "add-greet/R")
    assert code == 2
    assert "scenario GREET.TYPO is not declared in any spec" in out
