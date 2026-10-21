"""A plan's own level, and a change's, changed (a change's lowered) only under the rigor claim. See docs/design.md §4, §7."""

import pytest

from redline.approval import Approvals
from redline.pr import gates, rigor_claim
from test_ci import ci, red_pr
from test_outside import OUTSIDE, outside
from test_plan import FAREWELL, PLAN, VALID, WAVE, check_plan
from test_pr import RED_TESTS, github  # noqa: F401 (a fixture)
from test_start import change, fresh_branch, start  # noqa: F401 (change is a fixture)

CRITICAL = VALID.replace("seen off\n", "seen off\nRigor: critical\n", 1)
CLAIM = f"rigor: the `Rigor:` line of {PLAN} changed from critical to "
DELETED = f"rigor: {PLAN} was deleted, taking add-greet, add-wave, add-farewell out of its initiative"
MORE = "redline/initiatives/more/plan.md"


@pytest.fixture
def planned(change):
    change.commit("a critical plan, no critical change", {PLAN: CRITICAL, **FAREWELL, **WAVE})
    return change


def test_a_plan_that_says_critical_needs_its_start_audit(planned, capsys):
    fresh_branch(planned, "spec")
    code, out = start(planned, capsys, "add-greet/S")
    assert code == 1
    assert "audits/phase-1-start.md: missing; run the plan-auditor on `greetings phase 1 start`" in out


def test_an_unknown_level_fails_check_plan(planned, capsys):
    planned.commit("high", {PLAN: CRITICAL.replace("critical", "high")})
    code, out = check_plan(planned, capsys)
    assert code == 1 and "greetings: unknown rigor level `high`" in out, out


@pytest.mark.parametrize(("plan", "now"), [
    (VALID, "none"),
    (CRITICAL.replace("critical", "standard"), "standard"),
], ids=["removed", "lowered"])
def test_changing_a_plans_level_needs_the_rigor_claim(planned, plan, now):
    fresh_branch(planned, "lower")
    planned.commit("lower", {PLAN: plan})
    assert rigor_claim(planned.path, Approvals()) == [f"{CLAIM}{now}, with no Redline-Rigor trailer"]
    planned.commit("why\n\nRedline-Rigor: greetings holds no secrets")
    approvals = Approvals()
    assert rigor_claim(planned.path, approvals) == []
    assert approvals.pending == [f"{CLAIM}{now}: CI will need the `redline:rigor` label from a maintainer"]


@pytest.fixture
def plain(change):
    change.commit("a plan with no Rigor: line", {PLAN: VALID, **FAREWELL, **WAVE})
    fresh_branch(change, "edit")
    return change


@pytest.mark.parametrize(("plan", "taken"), [
    (None, [DELETED]),
    (VALID.replace("add-greet, add-wave", "add-greet"), [f"rigor: add-wave was taken out of {PLAN}"]),
    (VALID.split("## Phase 2")[0], [f"rigor: add-farewell was taken out of {PLAN}"]),
], ids=["plan-deleted", "change-removed", "phase-removed"])
def test_taking_a_change_out_of_a_plan_needs_the_rigor_claim(plain, plan, taken):
    if plan is None:
        plain.git("rm", "-q", PLAN)
    plain.commit("take out", {PLAN: plan} if plan else None)
    assert rigor_claim(plain.path, Approvals()) == [f"{t}, with no Redline-Rigor trailer" for t in taken]
    plain.commit("why\n\nRedline-Rigor: greetings is shelved")
    approvals = Approvals()
    assert rigor_claim(plain.path, approvals) == []
    assert approvals.pending == [f"{t}: CI will need the `redline:rigor` label from a maintainer" for t in taken]


def test_deleting_a_critical_plan_claims_its_level_and_its_changes(planned):
    fresh_branch(planned, "delete")
    planned.git("rm", "-q", PLAN)
    planned.commit("delete")
    assert rigor_claim(planned.path, Approvals()) == [
        f"{CLAIM}none, with no Redline-Rigor trailer", f"{DELETED}, with no Redline-Rigor trailer"]


@pytest.mark.parametrize("plan", [
    VALID.replace("add-greet, add-wave", "add-greet, add-wave, add-hello"),
    VALID.replace("add-greet, add-wave", "add-greet").replace("Changes: add-farewell", "Changes: add-farewell, add-wave"),
], ids=["change-added", "change-moved-phase"])
def test_adding_or_moving_a_change_in_its_plan_is_no_claim(plain, plan):
    plain.commit("edit", {PLAN: plan})
    assert rigor_claim(plain.path, Approvals()) == []


def test_a_change_moved_to_another_plan_is_taken_out_of_its_own(plain):
    other = "# Initiative: more\nGoal: more\n\n## Phase 1: More\nChanges: add-wave\nStop: more\n"
    plain.commit("move", {PLAN: VALID.replace("add-greet, add-wave", "add-greet"), MORE: other})
    assert rigor_claim(plain.path, Approvals()) == [f"rigor: add-wave was taken out of {PLAN}, with no Redline-Rigor trailer"]


def test_ci_refuses_a_deleted_plan_outside_any_step_until_a_maintainer_labels_the_claim(change, capsys, github):
    change.commit("a plan with no Rigor: line", {PLAN: VALID, **FAREWELL, **WAVE})
    outside(change)
    change.git("rm", "-q", PLAN)
    change.commit("shelve greetings\n\nRedline-Rigor: greetings is shelved")
    code, out = ci(change, capsys, "pr", "--base", "main", "--pr", "1")
    assert code == 1
    assert f"{DELETED}: needs the `redline:rigor` label from a maintainer" in out
    github.applied["redline:rigor"] = "maintainer"
    code, out = ci(change, capsys, "pr", "--base", "main", "--pr", "1")
    assert code == 0, out
    assert OUTSIDE in out


def test_a_step_that_takes_a_change_out_of_its_plan_needs_the_claim_too(plain):
    plain.commit("take out", {PLAN: VALID.replace("add-greet, add-wave", "add-greet")})
    assert f"rigor: add-wave was taken out of {PLAN}, with no Redline-Rigor trailer" in gates(plain.path, "add-greet", "S")


def added(glob: str, key: str) -> str:
    return f"rigor: `{glob}` was added to `{key}:` in redline/config.yaml"


def test_ci_refuses_a_glob_added_to_generated_or_support_until_a_maintainer_labels_the_claim(change, capsys, github):
    outside(change, {"redline/config.yaml": 'generated:\n  - "*"\nsupport:\n  - "tests/*.py"\n'})
    code, out = ci(change, capsys, "pr", "--base", "main", "--pr", "1")
    assert code == 1
    assert f"{added('*', 'generated')}, with no Redline-Rigor trailer" in out
    assert f"{added('tests/*.py', 'support')}, with no Redline-Rigor trailer" in out
    change.commit("why\n\nRedline-Rigor: every file here is built")
    code, out = ci(change, capsys, "pr", "--base", "main", "--pr", "1")
    assert code == 1
    assert f"{added('*', 'generated')}: needs the `redline:rigor` label from a maintainer" in out
    github.applied["redline:rigor"] = "maintainer"
    code, out = ci(change, capsys, "pr", "--base", "main", "--pr", "1")
    assert code == 0, out
    assert OUTSIDE in out


def test_a_step_that_adds_a_glob_needs_the_claim_too(plain):
    plain.commit("widen", {"redline/config.yaml": 'generated:\n  - "*.json"\n'})
    assert f"{added('*.json', 'generated')}, with no Redline-Rigor trailer" in gates(plain.path, "add-greet", "S")


def test_removing_or_reordering_globs_is_no_claim(change):
    change.commit("globs", {"redline/config.yaml": 'generated:\n  - "*.lock"\n  - "*.json"\nsupport:\n  - "a.py"\n'})
    fresh_branch(change, "narrow")
    change.commit("narrow", {"redline/config.yaml": 'generated:\n  - "*.json"\n'})
    assert rigor_claim(change.path, Approvals()) == []


def test_a_new_plan_declares_its_level_without_a_claim(change):
    fresh_branch(change, "plan")
    change.commit("a new plan", {PLAN: CRITICAL, **FAREWELL, **WAVE})
    assert rigor_claim(change.path, Approvals()) == []


PROPOSAL = "redline/changes/add-greet/proposal.md"
CONFIG = "redline/config.yaml"


def proposed(level: str | None) -> str:
    return "# Proposal: add-greet\n" + (f"Rigor: {level}\n" if level else "")


def lowered(old: str, new: str) -> str:
    return f"rigor: add-greet's level was lowered from {old} to {new}"


@pytest.mark.parametrize(("config", "proposal", "now"), [
    ("", proposed("lite"), "lite"),
    ("", proposed(None), "standard"),
    ("rigor: lite\n", None, "lite"),
], ids=["line-lowered", "line-removed", "proposal-deleted"])
def test_lowering_a_changes_level_needs_the_rigor_claim(change, config, proposal, now):
    change.commit("critical", {PROPOSAL: proposed("critical"), **({CONFIG: config} if config else {})})
    fresh_branch(change, "lower")
    if proposal is None:
        change.git("rm", "-q", PROPOSAL)
    change.commit("lower", {PROPOSAL: proposal} if proposal else None)
    assert rigor_claim(change.path, Approvals()) == [f"{lowered('critical', now)}, with no Redline-Rigor trailer"]
    change.commit("why\n\nRedline-Rigor: add-greet touches no secrets")
    approvals = Approvals()
    assert rigor_claim(change.path, approvals) == []
    assert approvals.pending == [f"{lowered('critical', now)}: CI will need the `redline:rigor` label from a maintainer"]


@pytest.mark.parametrize(("before", "after"), [
    ({PROPOSAL: proposed("standard")}, {PROPOSAL: proposed("critical")}),
    ({}, {PROPOSAL: proposed("lite")}),
], ids=["raised", "new-proposal"])
def test_raising_a_changes_level_or_a_new_proposal_is_no_claim(change, before, after):
    if before:
        change.commit("before", before)
    fresh_branch(change, "edit")
    change.commit("edit", after)
    assert rigor_claim(change.path, Approvals()) == []


def test_lowering_the_configs_rigor_names_each_change_it_lowers(change):
    change.commit("critical", {CONFIG: "rigor: critical\n", PROPOSAL: proposed(None)})
    fresh_branch(change, "lower")
    change.commit("lower", {CONFIG: "rigor: standard\n"})
    assert rigor_claim(change.path, Approvals()) == [
        "rigor: `rigor:` in redline/config.yaml changed from critical to standard, with no Redline-Rigor trailer",
        f"{lowered('critical', 'standard')}, with no Redline-Rigor trailer"]


def test_an_unknown_level_fails_whatever_the_trailer(change):
    change.commit("standard", {PROPOSAL: proposed("standard")})
    fresh_branch(change, "high")
    change.commit("high\n\nRedline-Rigor: higher still", {PROPOSAL: proposed("high")})
    assert rigor_claim(change.path, Approvals()) == ["rigor: add-greet: unknown rigor level `high`"]


def test_ci_refuses_a_step_that_lowers_its_changes_level_until_a_maintainer_labels_the_claim(change, capsys, github):
    change.commit("standard", {PROPOSAL: proposed("standard")})
    red_pr(change, capsys, {"tests/test_greet.py": RED_TESTS, PROPOSAL: proposed("lite")})
    code, out = ci(change, capsys, "pr", "--base", "main", "--pr", "1")
    assert code == 1
    assert f"{lowered('standard', 'lite')}, with no Redline-Rigor trailer" in out
    change.commit("why\n\nRedline-Step: add-greet/R\nRedline-Rigor: greetings are harmless")
    code, out = ci(change, capsys, "pr", "--base", "main", "--pr", "1")
    assert code == 1
    assert f"{lowered('standard', 'lite')}: needs the `redline:rigor` label from a maintainer" in out
    github.applied["redline:rigor"] = "maintainer"
    code, out = ci(change, capsys, "pr", "--base", "main", "--pr", "1")
    assert code == 0, out
