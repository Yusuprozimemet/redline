"""`redline check-steps`: the form of a change's steps.md, against its own deltas. See docs/design.md §4."""

import pytest

from redline.cli import main
from redline.pr import gates
from test_plan import FAREWELL
from test_ci import step_pr
from test_start import CHANGE, DELTA, STEPS, change, fresh_branch, merge_step  # noqa: F401 (change is a fixture)

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


@pytest.mark.parametrize("line", ["#### Scenario GREET.S3 [manual]: looks right",
                                  "#### Scenario GREET.S3: no tag"])
def test_a_malformed_scenario_heading_in_a_delta_fails(change, capsys, line):
    change.commit("manual", {f"{CHANGE}/specs/greet/delta.md": DELTA + "\n" + line + "\n- THEN it looks right\n"})
    code, out = check(change, capsys)
    line_no = DELTA.count("\n") + 2
    assert code == 1, out
    assert (f"specs/greet/delta.md:{line_no}: not a scenario heading "
            f"`#### Scenario <ID> [new|hold]: <title>`: {line}") in out, out


def test_the_gate_fails_a_malformed_heading_at_s(change):
    fresh_branch(change, "add-greet-S")
    change.commit("manual", {f"{CHANGE}/specs/greet/delta.md": DELTA + "#### Scenario GREET.S3 [manual]: blue\n"})
    assert [f for f in gates(change.path, "add-greet", "S") if "not a scenario heading" in f] == [
        f"check-steps: specs/greet/delta.md:{DELTA.count(chr(10)) + 1}: not a scenario heading "
        "`#### Scenario <ID> [new|hold]: <title>`: #### Scenario GREET.S3 [manual]: blue"]


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


# Across steps (O-STEPS2): steps.md compared with the merge-base, items by ID and steps by name.

O2 = "- O2 [G2]: names with spaces\n"
G2 = "## G2: Greet a crowd\nOwns: GREET.S2\n\n"
WAVE = "redline/changes/add-wave/steps.md"
NO_G2 = STEPS.replace(G2, "").replace("Owns: GREET.S1\n\n## C", "Owns: GREET.S1, GREET.S2\n\n## C")


def at(repo, step: str, steps: str, merged: tuple[str, ...], extra: dict[str, str] | None = None) -> list[str]:
    """The check-steps failures of `step`'s gates, on a branch editing steps.md once `merged` are on main."""
    for done in merged:
        merge_step(repo, done)
    fresh_branch(repo, "step")
    repo.commit("edit", {PATH: steps, **(extra or {})})
    return [f for f in gates(repo.path, "add-greet", step) if f.startswith("check-steps")]


@pytest.mark.parametrize("step, merged, steps, failure", [
    ("G1", ("S", "R"), STEPS.replace(O2, ""),
     "check-steps: steps.md: open item O2 dropped since the merge-base: - O2 [G2]: names with spaces"),
    ("G2", ("S", "R", "G1"), STEPS.replace(O2, ""),  # at its owning step too: an item stays as the record
     "check-steps: steps.md: open item O2 dropped since the merge-base: - O2 [G2]: names with spaces"),
    ("G1", ("S", "R"), STEPS + "- O3 [R]: given to a merged step\n",
     "check-steps: steps.md:19: open item O3 given to R, which is merged on main"),
    ("G1", ("S", "R"), STEPS.replace("- O2 [G2]", "- O2 [R]"),
     "check-steps: steps.md:18: open item O2 given to R, which is merged on main"),
    ("G1", ("S", "R"), STEPS.replace("## R: Red tests for greeting\nOwns: GREET.S1, GREET.S2\n\n", ""),
     "check-steps: steps.md: step R removed since the merge-base, and it is merged on main"),
    ("G2", ("S", "R", "G1"), NO_G2.replace("- O2 [G2]", "- O2 [C]"),
     "check-steps: steps.md: step G2 removed since the merge-base, and it is this PR's step"),
], ids=["item-dropped", "item-dropped-by-its-owner", "item-given-to-merged", "item-re-owned-to-merged",
        "merged-step-removed", "own-step-removed"])
def test_what_leaves_steps_md_since_the_merge_base_fails(change, step, merged, steps, failure):
    assert at(change, step, steps, merged) == [failure]


@pytest.mark.parametrize("steps", [
    STEPS + "- O3 [G1]: done in this PR\n",  # the step's own isn't merged yet
    NO_G2.replace("- O2 [G2]", "- O2 [C]"),  # an unmerged step, its scenario and item moved
    STEPS.replace("- O2 [G2]", "- O2 [C]"),  # an item moved to a later step
], ids=["item-given-to-own", "unmerged-step-removed", "item-moved-later"])
def test_edits_that_drop_nothing_pass(change, steps):
    assert at(change, "G1", steps, ("S", "R")) == []


def test_an_item_moved_forward_from_a_merged_step_passes(change):
    change.commit("item", {PATH: STEPS + "- O3 [R]: carried on\n"})
    assert at(change, "G1", STEPS + "- O3 [G2]: carried on\n", ("S", "R")) == []


def test_an_item_moved_to_another_change_passes_by_its_text(change):
    change.commit("wave", {WAVE: "## S: Spec\n\n## C: Close\n\n## Open items\n- O1 [C]: wave back\n"})
    moved = {WAVE: "## S: Spec\n\n## C: Close\n\n## Open items\n- O1 [C]: wave back\n- O2 [C]: names with spaces\n"}
    assert at(change, "G1", STEPS.replace(O2, ""), ("S", "R"), moved) == []


def test_an_item_moved_with_other_words_is_dropped(change):
    change.commit("wave", {WAVE: "## S: Spec\n\n## C: Close\n"})
    moved = {WAVE: "## S: Spec\n\n## C: Close\n\n## Open items\n- O1 [C]: names with blanks\n"}
    assert at(change, "G1", STEPS.replace(O2, ""), ("S", "R"), moved) == [
        "check-steps: steps.md: open item O2 dropped since the merge-base: - O2 [G2]: names with spaces"]


def test_another_change_the_pr_edits_is_compared_too(change):
    change.commit("wave", {WAVE: "## S: Spec\n\n## C: Close\n\n## Open items\n- O1 [C]: wave back\n"})
    assert at(change, "G1", STEPS, ("S", "R"), {WAVE: "## S: Spec\n\n## C: Close\n"}) == [
        "check-steps: add-wave: steps.md: open item O1 dropped since the merge-base: - O1 [C]: wave back"]


def test_a_change_with_no_steps_md_at_the_merge_base_gets_the_form_check_only(change):
    fresh_branch(change, "spec")
    change.commit("spec", {WAVE: "## S: Spec\n\n## C: Close\n\n## Open items\n- O1 [C]: later\n"})
    assert not [f for f in gates(change.path, "add-wave", "S") if f.startswith("check-steps")]


def test_the_command_compares_with_base(change, capsys):
    merge_step(change, "S")
    merge_step(change, "R")
    fresh_branch(change, "step")
    change.commit("edit", {PATH: NO_G2.replace("- O2 [G2]", "- O2 [C]")})  # no step given: G2 isn't merged
    assert check(change, capsys)[0] == 0
    change.commit("drop", {PATH: NO_G2.replace(O2, "")})
    code, out = check(change, capsys)
    assert code == 1 and "steps.md: open item O2 dropped since the merge-base" in out, out
    code = main(["check-steps", "add-greet", "--base", "step", "--repo", str(change.path)])
    assert code == 0, capsys.readouterr().out  # against itself nothing left


def test_ci_compares_with_the_merge_base(change, capsys):
    out = step_pr(change, capsys, "add-greet/G1", ("S", "R"), {PATH: STEPS.replace(O2, "")})
    assert "check-steps: steps.md: open item O2 dropped since the merge-base: - O2 [G2]: names with spaces" in out


def test_an_item_whose_text_another_change_already_had_is_dropped(change):
    change.commit("wave", {WAVE: "## S: Spec\n\n## C: Close\n\n## Open items\n- O1 [C]: names with spaces\n"})
    edit = {WAVE: "## S: Spec\n\n## C: Close\n\n## Open items\n- O1 [C]: names with spaces\n- O2 [C]: wave back\n"}
    assert at(change, "G1", STEPS.replace(O2, ""), ("S", "R"), edit) == [
        "check-steps: steps.md: open item O2 dropped since the merge-base: - O2 [G2]: names with spaces"]


def test_a_step_merged_in_another_change_isnt_this_ones(change):
    change.commit("wave G2 done\n\nRedline-Step: add-wave/G2")
    assert at(change, "G1", STEPS + "- O3 [G2]: later\n", ("S", "R")) == []
