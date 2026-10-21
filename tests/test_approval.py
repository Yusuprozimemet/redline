import pytest
import yaml

from test_check_break import PASSING, holds, mutator  # noqa: F401 (fixtures)
from test_ci import WORKFLOW, ci, red_pr
from test_lock import APPROVED, WEAKENED, lock
from test_pr import AUDIT, RED_TESTS, begin, github, pr  # noqa: F401 (github is a fixture)
from test_start import change, fresh_branch, merge_step  # noqa: F401 (change is a fixture)

BIG = {"data.md": "x\n" * 401}
OVERSIZED = "Oversized: a vendored data file"


def test_pr_lets_an_oversized_step_through_and_says_ci_needs_the_label(change, capsys, github):
    begin(change, capsys, "S", "spec")
    change.commit("big\n\nOversized:", {**AUDIT, **BIG})  # gives no reason
    code, out = pr(change, capsys)
    assert code == 1
    assert "over the limit of 400" in out
    change.git("commit", "-q", "--amend", "-m", f"big\n\n{OVERSIZED}")
    code, out = pr(change, capsys)
    assert code == 0, out
    assert "CI will need the `redline:oversized` label from a maintainer" in out
    assert ("labels", 1) not in github.fakes[-1].calls


@pytest.mark.parametrize(("applied", "args", "failure"), [
    ({}, ("--pr", "1"), "needs the `redline:oversized` label from a maintainer"),
    ({"redline:departure": "maintainer"}, ("--pr", "1"), "needs the `redline:oversized` label from a maintainer"),
    ({"redline:oversized": "agent"}, ("--pr", "1"), "`redline:oversized` was applied by @agent, who isn't a maintainer"),
    ({"redline:oversized": "maintainer"}, (), "no PR number to read the `redline:oversized` label from"),
    ({"redline:oversized": "maintainer"}, ("--pr", "1"), None),
])
def test_ci_needs_a_maintainers_label_on_an_oversized_pr(change, capsys, github, applied, args, failure):
    red_pr(change, capsys, {"tests/test_greet.py": RED_TESTS})
    change.commit(f"big\n\nRedline-Step: add-greet/R\n{OVERSIZED}", BIG)
    github.applied.update(applied)
    code, out = ci(change, capsys, "pr", "--base", "main", *args)
    if failure:
        assert code == 1
        assert f"over the limit of 400: {failure}" in out
    else:
        assert code == 0, out


@pytest.mark.parametrize(("applied", "approved"), [
    ({}, False),
    ({"redline:oversized": "maintainer"}, False),
    ({"redline:departure": "maintainer"}, True),
])
def test_ci_needs_a_maintainers_label_on_a_departure(holds, capsys, github, applied, approved):
    merge_step(holds, "S")
    holds.commit("red tests", {"tests/test_greet.py": RED_TESTS, "test_hold.py": PASSING})
    lock(holds, capsys)
    holds.commit("R\n\nRedline-Step: add-greet/R")
    fresh_branch(holds, "g1")
    holds.commit("weaken", {"test_hold.py": WEAKENED})
    lock(holds, capsys)
    holds.commit(f"relock\n\nRedline-Step: add-greet/G1\n{APPROVED}")
    github.applied.update(applied)
    code, out = ci(holds, capsys, "pr", "--base", "main", "--pr", "1")
    failure = ("check-lock: GREET.H1: test_hold.py::test_h1: its lock entry changed since main: "
               "needs the `redline:departure` label from a maintainer")
    assert (failure in out) is not approved, out
    assert ("check-lock" in out) is not approved


def test_the_workflow_passes_the_pr_number_and_reruns_on_a_label():
    flow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    triggers = flow.get("on", flow.get(True))
    assert {"opened", "synchronize", "reopened", "labeled", "unlabeled"} <= set(triggers["pull_request"]["types"])
    assert flow["jobs"]["redline"]["permissions"]["pull-requests"] == "read"
    step = next(s for job in flow["jobs"].values() for s in job["steps"] if "redline ci pr" in s.get("run", ""))
    assert "--pr ${{ github.event.pull_request.number }}" in step["run"]
    assert step["env"]["GH_TOKEN"] == "${{ github.token }}"
