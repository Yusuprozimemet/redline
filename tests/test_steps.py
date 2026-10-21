"""`redline check-steps`: the form of a change's steps.md, against its own deltas. See docs/design.md §4."""

import pytest

from redline.cli import main
from redline.pr import gates
from test_plan import FAREWELL
from test_start import CHANGE, DELTA, STEPS, change, fresh_branch  # noqa: F401 (change is a fixture)

PATH = f"{CHANGE}/steps.md"


def check(repo, capsys, change: str = "add-greet") -> tuple[int, str]:
    code = main(["check-steps", change, "--repo", str(repo.path)])
    return code, capsys.readouterr().out


def test_the_toy_change_passes(change, capsys):
    assert check(change, capsys) == (0, "ok: 5 steps, 2 open items\n")


@pytest.mark.parametrize("files, change_id", [
    ({PATH: STEPS.replace("## C:", "## G3: More\n\n## C:")}, "add-greet"),
    (FAREWELL, "add-farewell"),  # a change that only REMOVES scenarios
    ({"redline/changes/add-hold/steps.md": "## S: Spec\n\n## R: Red\nOwns: HOLD.H1\n\n## C: Close\n",
      "redline/changes/add-hold/specs/hold/delta.md": "## ADDED Requirements\n### Requirement: Hold\n"
                                                       "#### Scenario HOLD.H1 [hold]: holds\n- THEN it holds\n"}, "add-hold"),
    ({PATH: STEPS.replace("## C: Close\n\n## Open items\n- O1 [G1]: decide on the punctuation\n- O2 [G2]: names with spaces\n",
                          "## Open items\n- O1 [G1]: decide on the punctuation\n- O2 [C]: names with spaces\n\n## C: Close\n")},
     "add-greet"),  # open items before the step that owns one
])
def test_well_formed_steps_pass(change, capsys, files, change_id):
    change.commit("steps", files)
    code, out = check(change, capsys, change_id)
    assert code == 0, out


BAD = [
    ("- rate-limit repeated wrong codes later\n",
     "steps.md:19: not an open item `- <ID> [<step>]: <text>`: - rate-limit repeated wrong codes later"),
    ("- O3: no owner given\n", "steps.md:19: not an open item `- <ID> [<step>]: <text>`: - O3: no owner given"),
    ("  and a wrapped second line\n",
     "steps.md:19: not an open item `- <ID> [<step>]: <text>`:   and a wrapped second line"),
    ("- O1 [G2]: again\n", "steps.md:19: open item O1 given twice"),
    ("- O3 [G7]: no such step\n", "steps.md:19: open item O3 names no step of steps.md: [G7]"),
]


@pytest.mark.parametrize("extra, failure", BAD)
def test_a_malformed_open_item_fails(change, capsys, extra, failure):
    change.commit("item", {PATH: STEPS + extra})
    code, out = check(change, capsys)
    assert code == 1 and failure in out, out


def test_an_open_item_outside_open_items_fails(change, capsys):
    change.commit("item", {PATH: STEPS.replace("Owns: GREET.S2\n", "Owns: GREET.S2\n- O3 [G2]: misplaced\n")})
    code, out = check(change, capsys)
    assert code == 1 and "steps.md:13: an open item outside `## Open items`: - O3 [G2]: misplaced" in out, out


@pytest.mark.parametrize("steps, failure", [
    (STEPS.replace("## G1: Greet by name\nOwns: GREET.S1\n\n## G2: Greet a crowd\nOwns: GREET.S2\n",
                   "## G2: Greet a crowd\nOwns: GREET.S2\n\n## G1: Greet by name\nOwns: GREET.S1\n"),
     "steps.md: S, R, G2, G1, C aren't S, R, G1…Gn, C in order"),
    (STEPS.replace("## S: Spec for greeting\n\n", ""), "steps.md: R, G1, G2, C aren't S, R, G1…Gn, C in order"),
    (STEPS.replace("## C: Close\n\n", ""), "steps.md: S, R, G1, G2 aren't S, R, G1…Gn, C in order"),
    (STEPS.replace("## G2: Greet a crowd", "## G3: Greet a crowd"), "steps.md: S, R, G1, G3, C aren't S, R, G1…Gn, C in order"),
    (STEPS.replace("## G2: Greet a crowd", "## G2 Greet a crowd"),
     "steps.md:11: neither a step nor `## Open items`: ## G2 Greet a crowd"),
])
def test_steps_out_of_order_fail(change, capsys, steps, failure):
    change.commit("order", {PATH: steps})
    code, out = check(change, capsys)
    assert code == 1 and failure in out, out


def test_a_step_named_twice_fails(change, capsys):
    change.commit("twice", {PATH: STEPS.replace("## G2: Greet a crowd", "## G1: Greet a crowd")})
    code, out = check(change, capsys)
    assert code == 1 and "steps.md:11: step G1 named twice" in out, out


def test_an_owned_id_no_delta_declares_fails(change, capsys):
    change.commit("living", {"redline/specs/greet/spec.md": "#### Scenario GREET.S0 [hold]: says hi\n- THEN hi\n"})
    change.commit("typo", {PATH: STEPS.replace("Owns: GREET.S2\n", "Owns: GREET.S2, GREET.S0\n")})
    code, out = check(change, capsys)
    assert code == 1 and "steps.md:12: G2 owns GREET.S0, which no delta of the change declares" in out, out


def test_a_new_scenario_no_g_step_owns_fails(change, capsys):
    change.commit("unowned", {PATH: STEPS.replace("## G2: Greet a crowd\nOwns: GREET.S2\n", "## G2: Greet a crowd\n")})
    code, out = check(change, capsys)
    assert code == 1 and "GREET.S2 is new, but no G step owns it" in out, out  # R owning it isn't enough


def test_a_closed_change_still_reads_its_own_delta(change, capsys):
    change.commit("closed\n\nRedline-Step: add-greet/C")
    assert check(change, capsys)[0] == 0


def test_the_gate_checks_the_steps_change_from_the_tree(change):
    fresh_branch(change, "add-greet-S")
    assert not [f for f in gates(change.path, "add-greet", "S") if f.startswith("check-steps")]
    change.commit("trim", {PATH: STEPS.replace("## C: Close\n\n", "")})
    assert "check-steps: steps.md: S, R, G1, G2 aren't S, R, G1…Gn, C in order" in gates(change.path, "add-greet", "S")


def test_the_gate_checks_another_change_the_pr_edits(change):
    change.commit("farewell", {**FAREWELL, "redline/changes/add-wave/steps.md": "## S: Spec\n\n## C: Close\n"})
    fresh_branch(change, "add-greet-S")
    change.commit("edit both", {"redline/changes/add-farewell/steps.md": "## S: Spec for farewells\n",
                                "redline/changes/add-wave/specs/wave/delta.md": DELTA.replace("GREET", "WAVE"),
                                "notes.txt": "x\n"})
    failures = gates(change.path, "add-greet", "S")
    assert "check-steps: add-farewell: steps.md: S aren't S, R, G1…Gn, C in order" in failures
    assert "check-steps: add-wave: WAVE.S1 is new, but no G step owns it" in failures
    assert not [f for f in failures if f.startswith("check-steps: steps.md") or "add-greet:" in f]
