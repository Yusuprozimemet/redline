"""A plan audit is tied to the plan it read, by the blob in its `Plan:` line. See specs/ §4, §9."""

from test_initiative_audit import SIDES, every_phase_audited, resolved
from test_plan import PLAN, VALID, check_plan
from test_plan_audit import AUDITS, CLEAN, NONE, critical, phase_one_complete, stamped  # noqa: F401 (critical is a fixture)
from test_start import change, fresh_branch, start  # noqa: F401 (change is a fixture)

START = f"{AUDITS}/phase-1-start.md"


def edit_plan(repo) -> tuple[str, str]:
    """A PR outside any step edits the plan on main: its blob before, and now."""
    repo.git("checkout", "-q", "main")
    before = repo.git("rev-parse", f"main:{PLAN}")
    repo.commit("edit the plan", {PLAN: VALID.replace("greeted by name", "greeted")})
    return before, repo.git("rev-parse", f"main:{PLAN}")


def test_start_refuses_a_start_audit_of_an_older_plan_until_it_is_run_again(critical, capsys):
    critical.commit("start audit", {START: stamped(critical, CLEAN)})
    before, now = edit_plan(critical)
    fresh_branch(critical, "spec")
    code, out = start(critical, capsys, "add-greet/S")
    assert code == 1
    assert (f"{START}: read plan {before}, but {PLAN} is now {now}; "
            f"run the plan-auditor on `greetings phase 1 start` with plan {now} again") in out
    critical.git("checkout", "-q", "main")
    critical.commit("the re-run", {START: stamped(critical, CLEAN)})
    fresh_branch(critical, "spec-2")
    assert start(critical, capsys, "add-greet/S")[0] == 0


def test_an_audit_with_no_plan_line_is_refused(critical, capsys):
    critical.commit("start audit", {START: CLEAN})
    fresh_branch(critical, "spec")
    code, out = start(critical, capsys, "add-greet/S")
    assert code == 1
    assert f"{START}: no `Plan:` line; run the plan-auditor on `greetings phase 1 start` with plan " in out


def test_check_plan_fails_on_a_stale_end_audit_of_the_last_complete_phase(critical, capsys):
    phase_one_complete(critical)
    critical.commit("end audit", {f"{AUDITS}/phase-1-end.md": stamped(critical, NONE)})
    before, now = edit_plan(critical)
    code, out = check_plan(critical, capsys)
    assert code == 1
    assert f"greetings: {AUDITS}/phase-1-end.md: read plan {before}, but {PLAN} is now {now}" in out
    critical.commit("the re-run", {f"{AUDITS}/phase-1-end.md": stamped(critical, NONE)})
    assert check_plan(critical, capsys)[0] == 0


def test_after_the_last_stop_a_plan_edit_makes_the_newest_four_stale(critical, capsys):
    every_phase_audited(critical)  # phase 1's end audit has no Plan: line: a newer audit read the plan since
    critical.commit("sides", {f"{AUDITS}/initiative-{s}.md": resolved(critical, s) for s in SIDES})
    assert check_plan(critical, capsys)[0] == 0
    before, _ = edit_plan(critical)
    code, out = check_plan(critical, capsys)
    assert code == 1
    assert len(out.splitlines()) == 4, out
    for stale in ["phase-2-end.md", *(f"initiative-{s}.md" for s in SIDES)]:
        assert f"greetings: {AUDITS}/{stale}: read plan {before}, but {PLAN} is now " in out
