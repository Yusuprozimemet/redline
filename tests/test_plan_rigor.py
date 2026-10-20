"""The plan's own level, changed only under the rigor claim. See docs/design.md §4, §7."""

import pytest

from redline.approval import Approvals
from redline.pr import rigor_claim
from test_plan import FAREWELL, PLAN, VALID, WAVE, check_plan
from test_start import change, fresh_branch, start  # noqa: F401 (change is a fixture)

CRITICAL = VALID.replace("seen off\n", "seen off\nRigor: critical\n", 1)
CLAIM = f"rigor: the `Rigor:` line of {PLAN} changed from critical to "


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
    (None, "none"),
], ids=["removed", "lowered", "plan-deleted"])
def test_changing_a_plans_level_needs_the_rigor_claim(planned, plan, now):
    fresh_branch(planned, "lower")
    if plan is None:
        planned.git("rm", "-q", PLAN)
    planned.commit("lower", {PLAN: plan} if plan else None)
    assert rigor_claim(planned.path, Approvals()) == [f"{CLAIM}{now}, with no Redline-Rigor trailer"]
    planned.commit("why\n\nRedline-Rigor: greetings holds no secrets")
    approvals = Approvals()
    assert rigor_claim(planned.path, approvals) == []
    assert approvals.pending == [f"{CLAIM}{now}: CI will need the `redline:rigor` label from a maintainer"]


def test_a_new_plan_declares_its_level_without_a_claim(change):
    fresh_branch(change, "plan")
    change.commit("a new plan", {PLAN: CRITICAL, **FAREWELL, **WAVE})
    assert rigor_claim(change.path, Approvals()) == []
