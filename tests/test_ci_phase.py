"""`redline ci pr` repeats `start`'s phase and plan-audit refusals, read at the merge-base. See specs/ §6, §7."""

from test_ci import ci
from test_plan import PLAN, VALID, complete, planned  # noqa: F401 (planned is a fixture)
from test_plan_audit import AUDITS, CLEAN, critical, stamped  # noqa: F401 (critical is a fixture)
from test_plan_blob import edit_plan
from test_start import CHANGE, change, fresh_branch, merge_step  # noqa: F401 (change is a fixture)

START = f"{AUDITS}/phase-1-start.md"
WAITS = "refused: phase 2 of greetings waits for phase 1: add-greet not complete"
MISSING = f"{START}: missing; run the plan-auditor on `greetings phase 1 start`"


def phase_pr(repo, capsys, trailer: str, files: dict[str, str] | None = None) -> str:
    """A branch fresh from main whose one commit carries `trailer`; CI's output."""
    fresh_branch(repo, trailer.replace("/", "-"))
    repo.commit(f"work\n\nRedline-Step: {trailer}", files or {"notes.txt": "work\n"})
    return ci(repo, capsys, "pr", "--base", "main")[1]


def test_a_step_whose_earlier_phase_isnt_complete_is_refused_before_any_gate(planned, capsys):
    complete(planned, "add-wave", ("S", "C"))
    out = phase_pr(planned, capsys, "add-farewell/S")
    assert WAITS in out
    assert "check-" not in out and "suite:" not in out
    complete(planned, "add-greet", ("S", "R", "G1", "G2", "C"))  # merged on main after the fork counts
    planned.git("checkout", "-q", "add-farewell-S")
    out = ci(planned, capsys, "pr", "--base", "main")[1]
    assert "refused" not in out and "waits for" not in out  # on to S's gates


def test_a_pr_that_moves_its_change_to_an_earlier_phase_is_still_refused(planned, capsys):
    complete(planned, "add-wave", ("S", "C"))
    moved = VALID.replace("add-greet, add-wave", "add-greet, add-wave, add-farewell").replace("Changes: add-farewell", "Changes: add-later")
    out = phase_pr(planned, capsys, "add-farewell/S", {PLAN: moved})
    assert WAITS in out


def test_a_pr_that_trims_an_earlier_changes_steps_is_still_refused(planned, capsys):
    complete(planned, "add-wave", ("S", "C"))
    merge_step(planned, "S")
    out = phase_pr(planned, capsys, "add-farewell/S", {f"{CHANGE}/steps.md": "# Steps: add-greet\n\n## S: Spec for greeting\n"})
    assert WAITS in out


def test_a_critical_step_with_no_start_audit_on_main_is_refused(critical, capsys):
    out = phase_pr(critical, capsys, "add-greet/S")
    assert "refused: greetings needs its plan audits on main first:" in out and MISSING in out
    assert "check-" not in out and "suite:" not in out


def test_a_start_audit_the_step_adds_itself_does_not_count(critical, capsys):
    out = phase_pr(critical, capsys, "add-greet/S", {START: stamped(critical, CLEAN)})
    assert MISSING in out


def test_a_start_audit_on_main_lets_the_step_through(critical, capsys):
    critical.commit("start audit", {START: stamped(critical, CLEAN)})
    out = phase_pr(critical, capsys, "add-greet/S")
    assert "refused" not in out
    assert "check-audit:" in out


def test_a_stale_start_audit_is_refused(critical, capsys):
    critical.commit("start audit", {START: stamped(critical, CLEAN)})
    before, now = edit_plan(critical)
    out = phase_pr(critical, capsys, "add-greet/S")
    assert f"{START}: read plan {before}, but {PLAN} is now {now}" in out


def test_a_plan_edited_on_main_after_the_fork_isnt_read(critical, capsys):  # by design, §7
    critical.commit("start audit", {START: stamped(critical, CLEAN)})
    phase_pr(critical, capsys, "add-greet/S")
    edit_plan(critical)
    critical.git("checkout", "-q", "add-greet-S")
    out = ci(critical, capsys, "pr", "--base", "main")[1]
    assert "refused" not in out


def test_a_pr_that_lowers_its_own_rigor_still_needs_the_audit(critical, capsys):
    out = phase_pr(critical, capsys, "add-greet/S", {f"{CHANGE}/proposal.md": "Rigor: standard\n"})
    assert MISSING in out
