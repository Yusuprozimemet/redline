import subprocess
from pathlib import Path

import pytest
import yaml

from redline.cli import main
from test_ledger import LEDGER, RED, land
from test_pr import RED_TESTS
from test_start import STEPS, change, fresh_branch, merge_step  # noqa: F401 (change is a fixture)

RUN = "https://github.com/toy/toy/actions/runs/7"
WORKFLOW = Path(__file__).parent.parent / ".github/workflows/redline.yml"
BROKEN = "def test_broken():\n    assert False\n"


class FakeRemote:
    """Stands in for pushing refs/notes/redline-ci: records the note as it stood at each push."""

    def __init__(self):
        self.fail = False
        self.pushed: list[str] = []

    def __call__(self, repo):
        self.repo = repo
        return self

    def push_notes(self) -> None:
        if self.fail:
            raise RuntimeError("git push: refs/notes/redline-ci was rejected")
        shown = subprocess.run(["git", "notes", "--ref=redline-ci", "show", "HEAD"], cwd=self.repo, capture_output=True, text=True)
        self.pushed.append(shown.stdout.strip())


@pytest.fixture
def remote(monkeypatch) -> FakeRemote:
    fake = FakeRemote()
    monkeypatch.setattr("redline.ci.Remote", fake, raising=False)
    return fake


def ci(repo, capsys, *args: str) -> tuple[int, str]:
    code = main(["ci", *args, "--repo", str(repo.path)])
    return code, capsys.readouterr().out


def red_pr(repo, capsys, files: dict[str, str], trailers: tuple[str, ...] = ("add-greet/R",), ledger: bool = True) -> None:
    """The R step's branch, its commits carrying `trailers`, with the ledger as main stands."""
    merge_step(repo, "S")
    fresh_branch(repo, "r-step")
    if ledger:
        assert main(["ledger", "add-greet", "--repo", str(repo.path)]) == 0
        capsys.readouterr()
    repo.commit(f"red tests\n\nRedline-Step: {trailers[0]}" if trailers[0] else "red tests", files)
    for trailer in trailers[1:]:
        repo.commit(f"more\n\nRedline-Step: {trailer}")


def test_a_pr_that_passes_the_gates_the_suite_and_check_ledger(change, capsys):
    red_pr(change, capsys, {"tests/test_greet.py": RED_TESTS})
    code, out = ci(change, capsys, "pr", "--base", "main")
    assert code == 0, out
    assert "ok: add-greet/R passes the gates, the test suite and check-ledger" in out


def test_a_pr_is_at_most_one_step(change, capsys):  # no step at all: test_outside.py
    red_pr(change, capsys, {"tests/test_greet.py": RED_TESTS}, ("add-greet/R", "add-greet/G1"))
    code, out = ci(change, capsys, "pr", "--base", "main")
    assert code == 1
    assert "refused: more than one step in main..HEAD: add-greet/G1, add-greet/R" in out
    assert "check-" not in out


def step_pr(repo, capsys, trailer: str, merged: tuple[str, ...] = (), files: dict[str, str] | None = None) -> str:
    """A branch whose one commit carries `trailer`, with `merged` steps landed on main first; CI's output."""
    for step in merged:
        merge_step(repo, step)
    fresh_branch(repo, "step")
    repo.commit(f"work\n\nRedline-Step: {trailer}", files or {"redline/specs/greet/spec.md": "# Greet\n"})
    code, out = ci(repo, capsys, "pr", "--base", "main")
    assert code == 1
    return out


@pytest.mark.parametrize(("trailer", "files"), [
    ("add-greet/X", None),
    ("add-greet/G3", {"redline/changes/add-greet/steps.md": STEPS.replace("## C:", "## G3: More\n\n## C:")}),
], ids=["unknown", "added-by-the-pr"])
def test_a_step_that_steps_md_lacks_at_the_merge_base_is_refused_before_any_gate(change, capsys, trailer, files):
    out = step_pr(change, capsys, trailer, ("S", "R", "G1", "G2"), files)
    step = trailer.partition("/")[2]
    assert f"refused: {trailer}: redline/changes/add-greet/steps.md at the merge-base has no step {step}" in out
    assert "check-" not in out and "suite:" not in out


@pytest.mark.parametrize(("merged", "missing"), [
    (("S",), "add-greet/R"),
    ((), "add-greet/S, add-greet/R"),  # invariant 1: the spec before the code
], ids=["R", "S-and-R"])
def test_a_step_whose_earlier_steps_arent_merged_is_refused(change, capsys, merged, missing):
    out = step_pr(change, capsys, "add-greet/G1", merged)
    assert f"refused: add-greet/G1 isn't next; not merged on main: {missing}" in out
    assert "check-" not in out


def test_a_step_already_merged_is_refused(change, capsys):
    out = step_pr(change, capsys, "add-greet/R", ("S", "R"))
    assert "refused: add-greet/R is already merged on main: a step is one PR" in out
    assert "check-" not in out


def test_a_change_with_no_steps_md_at_the_merge_base_can_only_be_at_its_s_step(change, capsys):
    wave = {"redline/changes/add-wave/steps.md": STEPS}
    out = step_pr(change, capsys, "add-wave/G1", files=wave)
    assert ("refused: add-wave/G1: redline/changes/add-wave has no steps.md at the merge-base, "
            "so it can only be at its S step, which writes it") in out
    change.git("commit", "-q", "--amend", "-m", "the spec\n\nRedline-Step: add-wave/S")
    code, out = ci(change, capsys, "pr", "--base", "main")
    assert "refused" not in out
    assert "check-audit:" in out  # S's own gates ran


def test_a_pr_prints_every_failure(change, capsys):
    half = RED_TESTS.split('@pytest.mark.spec("GREET.S2"')[0] + BROKEN
    red_pr(change, capsys, {"tests/test_greet.py": half}, ledger=False)
    code, out = ci(change, capsys, "pr", "--base", "main")
    assert code == 1
    assert "check-links: unlinked scenario GREET.S2" in out
    assert "suite: the test suite failed" in out
    assert f"check-ledger: {LEDGER}: missing; run `redline ledger add-greet`" in out
    assert "ok:" not in out


def test_a_pr_checks_the_ledger_against_its_base(change, capsys):
    red_pr(change, capsys, {"tests/test_greet.py": RED_TESTS})
    before = change.git("rev-parse", "main")
    land(change, "red-elsewhere", {"tests/test_other.py": RED})  # main gains red evidence for GREET.S1
    change.git("checkout", "-q", "r-step")
    code, out = ci(change, capsys, "pr", "--base", "main")
    assert code == 1
    assert f"check-ledger: {LEDGER}: GREET.S1 doesn't match the history of main" in out
    code, out = ci(change, capsys, "pr", "--base", before)
    assert code == 0, out


def test_a_push_to_main_notes_the_suite_result_on_the_merged_commit(change, capsys, remote):
    _, merge = land(change, "red", {"tests/test_greet.py": RED})
    code, out = ci(change, capsys, "push", "--run-url", RUN)
    assert code == 0, out
    assert change.git("notes", "--ref=redline-ci", "show", merge) == f"result: pass\nrun: {RUN}"
    assert remote.pushed == [f"result: pass\nrun: {RUN}"]
    assert main(["ledger", "add-greet", "--repo", str(change.path)]) == 0
    ledger = yaml.safe_load((change.path / LEDGER).read_text(encoding="utf-8"))
    assert ledger["scenarios"]["GREET.S1"]["red"]["result"] == "pass"


def test_a_push_records_a_failed_run_and_fails(change, capsys, remote):
    _, merge = land(change, "broken", {"tests/test_broken.py": BROKEN})
    code, out = ci(change, capsys, "push", "--run-url", RUN)
    assert code == 1
    assert "suite: the test suite failed" in out
    assert change.git("notes", "--ref=redline-ci", "show", merge) == f"result: fail\nrun: {RUN}"
    assert remote.pushed == [f"result: fail\nrun: {RUN}"]


def test_a_rejected_notes_push_is_an_error(change, capsys, remote):
    remote.fail = True
    land(change, "red", {"tests/test_greet.py": RED})
    code, out = ci(change, capsys, "push", "--run-url", RUN)
    assert code == 2
    assert "refs/notes/redline-ci was rejected" in out


def test_the_workflow_runs_redline_ci_on_prs_and_on_pushes_to_main():
    flow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    triggers = flow.get("on", flow.get(True))  # YAML 1.1 reads a bare `on` key as true
    assert triggers["pull_request"]["branches"] == ["main"]
    assert triggers["push"]["branches"] == ["main"]
    runs = [step.get("run", "") for job in flow["jobs"].values() for step in job["steps"]]
    assert any("redline ci pr" in run for run in runs)
    assert any("redline ci push" in run for run in runs)
