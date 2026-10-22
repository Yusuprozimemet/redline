from pathlib import Path

import pytest
import yaml

import redline.pr
from redline.pr import GitHub
from test_check_break import PASSING, holds, mutator  # noqa: F401 (fixtures)
from test_ci import WORKFLOW, ci, red_pr
from test_lock import APPROVED, WEAKENED, lock
from test_pr import AUDIT, HEAD, LABELLED, PUSHED, RED_TESTS, begin, github, pr  # noqa: F401 (github is a fixture)
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


BEFORE = "2026-10-22T09:59:59Z"


@pytest.mark.parametrize(("at", "head", "failure"), [
    (BEFORE, HEAD, f"`redline:oversized` was applied at {BEFORE}, before fffffff was pushed at {PUSHED}; apply it again"),
    (PUSHED, HEAD, f"`redline:oversized` was applied at {PUSHED}, before fffffff was pushed at {PUSHED}; apply it again"),
    ("2026-10-22T10:00:01Z", HEAD, None),
    ("2026-10-22T10:00:00.500Z", HEAD, None),  # instants, not text: "." sorts before "Z"
    (LABELLED, None, "`redline:oversized` approves nothing: no push of the PR's head was found to check it against"),
])
def test_a_label_counts_only_when_it_was_applied_after_the_heads_push(change, capsys, github, at, head, failure):
    red_pr(change, capsys, {"tests/test_greet.py": RED_TESTS})
    change.commit(f"big\n\nRedline-Step: add-greet/R\n{OVERSIZED}", BIG)
    github.applied["redline:oversized"], github.head = ("maintainer", at), head
    code, out = ci(change, capsys, "pr", "--base", "main", "--pr", "1")
    if failure:
        assert code == 1
        assert f"over the limit of 400: {failure}" in out, out
    else:
        assert code == 0, out
    assert [call for fake in github.fakes for call in fake.calls if call[0] == "pushed"] == [("pushed", 1)]


SHA, OTHER = "a" * 40, "b" * 40
ANSWERS = {
    "issues/7/events": "labeled\tredline:track\talice\t2026-10-22T09:00:00Z\n"
                       "labeled\tredline:rigor\tbob\t2026-10-22T09:10:00Z\n"
                       "unlabeled\tredline:rigor\tbob\t2026-10-22T09:20:00Z\n"
                       "labeled\tredline:track\tcarol\t2026-10-22T11:00:00Z",
    "pulls/7": f"{SHA}\tfeature/x\ttoy/fork",
    "activity": f"merge_queue_merge\t{SHA}\t2026-10-22T11:30:00Z\n"  # only a push makes the head
                f"branch_deletion\t{'0' * 40}\t2026-10-22T12:00:00Z\n"
                f"push\t{OTHER}\t2026-10-22T10:50:00Z\n"
                f"force_push\t{SHA}\t2026-10-22T10:45:00Z\n"
                f"push\t{SHA}\t2026-10-22T10:00:00Z\n"
                f"branch_creation\t{OTHER}\t2026-10-22T09:30:00Z",
}


def test_the_seam_reads_when_each_label_was_applied_and_when_the_head_was_last_pushed(monkeypatch, tmp_path):
    asked, answers = [], dict(ANSWERS)

    def run(self, *command: str) -> str:
        asked.append(command)
        return next(answer for key, answer in answers.items() if any(key in part for part in command))

    monkeypatch.setattr(GitHub, "run", run)
    github = GitHub(tmp_path)
    assert github.labels(7) == {"redline:track": ("carol", "2026-10-22T11:00:00Z")}
    assert github.pushed(7) == (SHA, "2026-10-22T10:45:00Z"), "the latest push that made the head, not one of another commit"
    assert any("repos/toy/fork/activity?ref=refs/heads/feature/x" in part for part in asked[-1]), "the head's own repository"
    answers["activity"] = f"push\t{OTHER}\t2026-10-22T10:50:00Z"
    assert github.pushed(7) is None


def test_issue_events_are_split_on_an_escape_not_a_literal_tab():
    assert "\t" not in Path(redline.pr.__file__).read_text(encoding="utf-8")


def test_the_workflow_passes_the_pr_number_and_reruns_on_a_label():
    flow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    triggers = flow.get("on", flow.get(True))
    assert {"opened", "synchronize", "reopened", "labeled", "unlabeled"} <= set(triggers["pull_request"]["types"])
    assert flow["jobs"]["redline"]["permissions"]["pull-requests"] == "read"
    step = next(s for job in flow["jobs"].values() for s in job["steps"] if "redline ci pr" in s.get("run", ""))
    assert "--pr ${{ github.event.pull_request.number }}" in step["run"]
    assert step["env"]["GH_TOKEN"] == "${{ github.token }}"
