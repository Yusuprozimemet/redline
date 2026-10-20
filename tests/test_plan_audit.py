"""Plan audits at each phase's start and end of a critical initiative. See docs/design.md §4, §6, §9."""

import re
from pathlib import Path

import pytest
import yaml

from redline.pr import gates
from test_merged import merged, on_step, remote  # noqa: F401 (remote is a fixture)
from test_plan import FAREWELL, PLAN, VALID, WAVE, check_plan, complete
from test_start import CHANGE, change, fresh_branch, merge_step, start  # noqa: F401 (change is a fixture)

AGENT = Path(__file__).parent.parent / ".claude/agents/redline-plan-auditor.md"
AUDITS = "redline/initiatives/greetings/audits"
CLEAN = "# Plan audit: greetings phase 1 start\n\n## F1 [closed]: the stop names no test\nResolution: it names GREET.S1\n"
NONE = "# Plan audit: greetings phase 1 end\n\nNo findings.\n"


def stamped(repo, text: str) -> str:
    """The audit as the auditor writes it: its `Plan:` line, the second, the blob of the plan it read."""
    title, rest = text.split("\n", 1)
    return f"{title}\nPlan: {repo.git('hash-object', PLAN)}\n" + re.sub(r"\APlan: .*\n", "", rest)


@pytest.fixture
def critical(change):
    change.commit("a critical initiative", {PLAN: VALID, **FAREWELL, **WAVE, f"{CHANGE}/proposal.md": "Rigor: critical\n"})
    return change


def phase_one_complete(repo) -> None:
    complete(repo, "add-greet", ("S", "R", "G1", "G2", "C"))
    complete(repo, "add-wave", ("S", "C"))


def test_the_plan_auditor_is_read_only_on_the_strongest_model():
    _, front, body = AGENT.read_text(encoding="utf-8").split("---\n", 2)
    front = yaml.safe_load(front)
    assert front["name"] == "redline-plan-auditor"
    tools = {tool.strip() for tool in front.get("tools", "").split(",")} - {""}
    assert tools and tools <= {"Read", "Grep", "Glob"}, tools
    assert front["model"] == "fable"
    assert "REFUSED: the plan-auditor runs only on a Claude Fable model" in body
    for duty in ("## At the phase's start", "## At the phase's end"):
        assert duty in body


def test_the_documented_output_is_an_audit_check_plan_reads(critical, capsys):
    example = re.search(r"```markdown\n(# Plan audit: .+?)```", AGENT.read_text(encoding="utf-8"), re.S)
    assert example, "the definition shows an example audit in a ```markdown block"
    assert re.match(r".+\nPlan: ", example[1]), "the example's second line records the plan it read"
    phase_one_complete(critical)
    critical.commit("end audit", {f"{AUDITS}/phase-1-end.md": stamped(critical, example[1])})
    code, out = check_plan(critical, capsys)
    assert code == 1
    assert len(out.splitlines()) == 1 and ": F1 is open: " in out, out


def test_start_refuses_a_phase_with_no_start_audit(critical, capsys):
    fresh_branch(critical, "spec")
    code, out = start(critical, capsys, "add-greet/S")
    assert code == 1
    assert f"{AUDITS}/phase-1-start.md: missing; run the plan-auditor on `greetings phase 1 start`" in out


@pytest.mark.parametrize(("audit", "passes"), [
    (CLEAN, True),
    (CLEAN.replace("[closed]", "[open]"), False),
    (CLEAN.replace("Resolution: it names GREET.S1\n", ""), False),
], ids=["resolved", "open", "closed-without-resolution"])
def test_start_needs_the_start_audit_resolved_on_main(critical, capsys, audit, passes):
    critical.commit("start audit", {f"{AUDITS}/phase-1-start.md": stamped(critical, audit)})
    fresh_branch(critical, "spec")
    code, out = start(critical, capsys, "add-greet/S")
    assert (code == 0) == passes, out


def test_a_start_audit_that_is_not_on_main_does_not_count(critical, capsys):
    fresh_branch(critical, "spec")
    (critical.path / AUDITS).mkdir(parents=True)
    (critical.path / AUDITS / "phase-1-start.md").write_text(CLEAN, encoding="utf-8")
    assert start(critical, capsys, "add-greet/S")[0] == 1


def test_a_standard_initiative_needs_no_plan_audit(critical, capsys):
    critical.commit("standard", {f"{CHANGE}/proposal.md": "Rigor: standard\n"})
    fresh_branch(critical, "spec")
    assert start(critical, capsys, "add-greet/S")[0] == 0


def test_check_plan_fails_on_a_complete_phase_with_no_end_audit(critical, capsys):
    complete(critical, "add-greet", ("S", "R", "G1", "G2", "C"))
    assert check_plan(critical, capsys)[0] == 0  # add-wave isn't complete yet
    complete(critical, "add-wave", ("S", "C"))
    code, out = check_plan(critical, capsys)
    assert code == 1
    assert f"greetings: {AUDITS}/phase-1-end.md: missing; run the plan-auditor on `greetings phase 1 end`" in out
    critical.commit("end audit", {f"{AUDITS}/phase-1-end.md": stamped(critical, NONE)})
    assert check_plan(critical, capsys)[0] == 0


def test_the_next_phase_waits_for_the_end_audit(critical, capsys):
    phase_one_complete(critical)
    critical.commit("phase 2 start audit", {f"{AUDITS}/phase-2-start.md": stamped(critical, CLEAN)})
    fresh_branch(critical, "farewell")
    code, out = start(critical, capsys, "add-farewell/S")
    assert code == 1
    assert f"{AUDITS}/phase-1-end.md: missing" in out
    critical.git("checkout", "-q", "main")
    critical.commit("end audit", {f"{AUDITS}/phase-1-end.md": NONE})
    fresh_branch(critical, "farewell-2")
    assert start(critical, capsys, "add-farewell/S")[0] == 0


def test_every_pr_fails_until_the_end_audit_lands(critical):
    phase_one_complete(critical)
    failures = gates(critical.path, "add-farewell", "S")
    assert f"check-plan: greetings: {AUDITS}/phase-1-end.md: missing; run the plan-auditor on `greetings phase 1 end` with plan {critical.git('rev-parse', f'main:{PLAN}')}" in failures


def test_merged_at_a_critical_stopping_point_says_which_audits_are_due(critical, capsys, remote):
    critical.commit("start audit", {f"{AUDITS}/phase-1-start.md": stamped(critical, CLEAN)})
    complete(critical, "add-wave", ("S", "C"))
    for step in ("S", "R", "G1", "G2"):
        merge_step(critical, step)
    remote.landing = "add-greet/C"
    on_step(critical, capsys, "C", "close")
    code, out = merged(critical, capsys, "add-greet/C")
    assert code == 0, out
    assert "is at a stopping point" in out
    assert f"redline-plan-auditor on `greetings phase 1 end`; write its reply unedited to {AUDITS}/phase-1-end.md" in out
    assert "Until it lands with every finding resolved, check-plan fails on every PR." in out
    assert f"`greetings phase 2 start` ({AUDITS}/phase-2-start.md)" in out
    assert f"Give each auditor `with plan {critical.git('rev-parse', f'main:{PLAN}')}`" in out
