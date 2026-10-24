"""End-of-initiative audits of a critical initiative, once its last phase is complete. See specs/ §4, §6, §9."""

import re
from pathlib import Path

import pytest
import yaml

from redline.pr import gates
from test_merged import merged, on_step, remote  # noqa: F401 (remote is a fixture)
from test_plan import PLAN, check_plan, complete
from test_plan_audit import AUDITS, CLEAN, NONE, critical, phase_one_complete, stamped  # noqa: F401 (critical is a fixture)
from test_start import change  # noqa: F401 (change is a fixture)

SIDES = ("security", "architecture", "process")
AGENTS = Path(__file__).parent.parent / ".claude/agents"


def resolved(repo, side: str) -> str:
    return stamped(repo, f"# Initiative audit: greetings {side}\nModel: claude-opus-5-5\n\nNo findings.\n")


def every_phase_audited(repo) -> None:
    """Every phase complete on main, each with its plan audits resolved."""
    phase_one_complete(repo)
    complete(repo, "add-farewell", ("S", "C"))
    repo.commit("plan audits", {f"{AUDITS}/phase-1-end.md": NONE, f"{AUDITS}/phase-2-end.md": stamped(repo, NONE)})


@pytest.mark.parametrize("side", SIDES)
def test_each_end_auditor_is_read_only_on_the_strongest_model(side):
    _, front, body = (AGENTS / f"redline-{side}-auditor.md").read_text(encoding="utf-8").split("---\n", 2)
    front = yaml.safe_load(front)
    assert front["name"] == f"redline-{side}-auditor"
    tools = {tool.strip() for tool in front.get("tools", "").split(",")} - {""}
    assert tools and tools <= {"Read", "Grep", "Glob"}, tools
    assert (front["model"], front["effort"]) == ("fable", "max")
    assert f"REFUSED: the {side} auditor runs only on a Claude Fable or Opus model" in body
    assert f"initiative-{side}.md" in front["description"]


@pytest.mark.parametrize("side", SIDES)
def test_each_documented_output_is_an_audit_check_plan_reads(critical, capsys, side):
    text = (AGENTS / f"redline-{side}-auditor.md").read_text(encoding="utf-8")
    example = re.search(r"```markdown\n(# Initiative audit: .+?)```", text, re.S)
    assert example, "the definition shows an example audit in a ```markdown block"
    assert re.match(r".+\nPlan: ", example[1]), "the example's second line records the plan it read"
    every_phase_audited(critical)
    others = {f"{AUDITS}/initiative-{s}.md": resolved(critical, s) for s in SIDES if s != side}
    critical.commit("end-of-initiative audits", {**others, f"{AUDITS}/initiative-{side}.md": stamped(critical, example[1])})
    code, out = check_plan(critical, capsys)
    assert code == 1
    assert len(out.splitlines()) == 1 and f"initiative-{side}.md:" in out and ": F1 is open: " in out, out


def test_a_complete_initiative_needs_all_three(critical, capsys):
    every_phase_audited(critical)
    code, out = check_plan(critical, capsys)
    assert code == 1
    for side in SIDES:
        assert f"greetings: {AUDITS}/initiative-{side}.md: missing; run redline-{side}-auditor on `greetings`" in out
    for side in SIDES[:2]:
        critical.commit(side, {f"{AUDITS}/initiative-{side}.md": resolved(critical, side)})
    code, out = check_plan(critical, capsys)
    assert code == 1 and len(out.splitlines()) == 1 and "initiative-process.md: missing" in out, out
    critical.commit("process", {f"{AUDITS}/initiative-process.md": resolved(critical, "process")})
    assert check_plan(critical, capsys)[0] == 0


def test_an_unresolved_finding_fails(critical, capsys):
    every_phase_audited(critical)
    files = {f"{AUDITS}/initiative-{s}.md": resolved(critical, s) for s in SIDES}
    files[f"{AUDITS}/initiative-security.md"] = CLEAN.replace("[closed]", "[open]")
    critical.commit("audits", files)
    code, out = check_plan(critical, capsys)
    assert code == 1 and "initiative-security.md:4: F1 is open" in out, out


def test_an_initiative_with_a_phase_left_needs_none(critical, capsys):
    phase_one_complete(critical)
    critical.commit("phase 1 end audit", {f"{AUDITS}/phase-1-end.md": stamped(critical, NONE)})
    assert check_plan(critical, capsys)[0] == 0


def test_a_standard_initiative_needs_none(critical, capsys):
    critical.commit("standard", {"redline/changes/add-greet/proposal.md": "Rigor: standard\n"})
    phase_one_complete(critical)
    complete(critical, "add-farewell", ("S", "C"))
    assert check_plan(critical, capsys)[0] == 0


def test_every_pr_fails_until_they_land(critical):
    every_phase_audited(critical)
    failures = gates(critical.path, "add-farewell", "C")
    assert f"check-plan: greetings: {AUDITS}/initiative-architecture.md: missing; run redline-architecture-auditor on `greetings` with plan {critical.git('rev-parse', f'main:{PLAN}')}" in failures


def test_merged_at_the_last_stopping_point_says_all_three_are_due(critical, capsys, remote):
    phase_one_complete(critical)
    complete(critical, "add-farewell", ("S",))
    remote.landing = "add-farewell/C"
    critical.git("checkout", "-q", "-b", "close")
    critical.git("commit", "-q", "--allow-empty", "-m", "close")
    code, out = merged(critical, capsys, "add-farewell/C")
    assert code == 0, out
    assert "The initiative greetings is complete." in out
    for side in SIDES:
        assert f"run redline-{side}-auditor on `greetings`; write its reply unedited to {AUDITS}/initiative-{side}.md" in out
    assert "independently: none reads another's reply or the plan audits" in out
    assert "Until all three land with every finding resolved, check-plan fails on every PR." in out
