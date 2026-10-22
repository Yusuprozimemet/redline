import pytest

from redline.audit import read_findings
from redline.cli import main

AUDIT = "redline/changes/add-login/audit.md"
DELTA = "redline/changes/add-login/specs/auth/delta.md"


def run(repo, capsys, change: str = "add-login") -> tuple[int, list[str]]:
    code = main(["check-audit", change, "--repo", str(repo.path)])
    return code, capsys.readouterr().out.splitlines()


def audit(text: str, model: str | None = "claude-fable-5-1") -> dict[str, str]:
    """The audit, its first line the model the auditor names (§9), or none."""
    return {DELTA: "### Premises\n", AUDIT: (f"Model: {model}\n" if model else "") + text}


@pytest.mark.parametrize("model", ["claude-fable-5-1", "claude-opus-5-5", "Claude Opus 5.5"])
def test_an_audit_by_fable_or_opus_passes(repo, capsys, model):
    repo.commit("audit", audit("# Audit: add-login\n\nNo findings.\n", model))
    assert run(repo, capsys) == (0, ["ok: 0 findings, none open"])


NAMES = "the auditor names the model it ran on in a `Model:` line before the first finding"
WEAKER = "is neither a Fable nor an Opus model; run the auditor on Fable, or on Opus at max effort"


@pytest.mark.parametrize(("text", "why"), [
    ("# Audit: add-login\n\nNo findings.\n", f"{AUDIT}: no `Model:` line; {NAMES}"),
    ("# Audit: add-login\n## F1 [closed]: fine\nResolution: fixed\nModel: claude-opus-5-5\n", f"{AUDIT}: no `Model:` line; {NAMES}"),
    ("# Audit: add-login\nModel: claude-sonnet-5-5\n\nNo findings.\n", f"{AUDIT}:2: Model: claude-sonnet-5-5 {WEAKER}"),
    ("# Audit: add-login\nModel: \n\nNo findings.\n", f"{AUDIT}:2: Model:  {WEAKER}"),
], ids=["none", "after-a-finding", "sonnet", "empty"])
def test_an_audit_with_no_model_or_a_weaker_one_fails(repo, capsys, text, why):
    repo.commit("audit", audit(text, None))
    assert run(repo, capsys) == (1, [why])


def test_plan_audits_are_read_for_their_model_too():
    plan_audit = "# Plan audit: greetings phase 1 end\nPlan: 3f2a9c1e\n\nNo findings.\n"
    assert read_findings(plan_audit, "phase-1-end.md").bad == [f"phase-1-end.md: no `Model:` line; {NAMES}"]
    assert read_findings(plan_audit.replace("\n\n", "\nModel: claude-opus-5-5\n\n"), "phase-1-end.md").bad == []


def test_resolved_findings_pass(repo, capsys):
    repo.commit("audit", audit(
        "# Audit: add-login\n\n"
        "## F1 [closed]: P1 cited the wrong line\n"
        "Resolution: P1 now cites `auth/session.py:42`\n\n"
        "## F2 [waived]: no test for the lockout timing\n"
        "Waived-by: @maintainer: timing is a manual check (O2)\n"
    ))
    code, out = run(repo, capsys)
    assert code == 0
    assert out == ["ok: 2 findings, none open"]


def test_an_audit_with_no_findings_passes(repo, capsys):
    repo.commit("audit", audit("# Audit: add-login\n\nNo findings.\n"))
    code, out = run(repo, capsys)
    assert code == 0
    assert out == ["ok: 0 findings, none open"]


def test_a_missing_audit_is_reported(repo, capsys):
    repo.commit("no audit", {DELTA: "### Premises\n"})
    code, out = run(repo, capsys)
    assert code == 1
    assert out == [f"{AUDIT}: missing; run the auditor on the change"]


def test_each_open_finding_is_reported_with_its_line(repo, capsys):
    repo.commit("audit", audit(
        "## F1 [open]: P2 is wrong; `auth/login.py:30` already calls `verify_code`\n"
        "## F2 [closed]: P1 cited the wrong line\n"
        "Resolution: fixed\n"
        "## F3 [open]: THEN clause of AUTH.S2 can't be checked\n"
    ))
    code, out = run(repo, capsys)
    assert code == 1
    assert out == [
        f"{AUDIT}:2: F1 is open: P2 is wrong; `auth/login.py:30` already calls `verify_code`",
        f"{AUDIT}:5: F3 is open: THEN clause of AUTH.S2 can't be checked",
    ]


def test_closed_needs_a_resolution_and_waived_needs_a_person(repo, capsys):
    repo.commit("audit", audit(
        "## F1 [closed]: P1 cited the wrong line\n"
        "Fixed it.\n\n"
        "## F2 [waived]: no test for the lockout timing\n"
        "Waived-by: timing is a manual check\n\n"
        "## F3 [closed]: an empty resolution\n"
        "Resolution:\n"
        "## F4 [waived]: the resolution of the finding above doesn't count here\n"
    ))
    code, out = run(repo, capsys)
    assert code == 1
    assert out == [
        f"{AUDIT}:2: F1 is closed with no `Resolution:` line",
        f"{AUDIT}:5: F2 is waived with no `Waived-by: @person: <reason>` line",
        f"{AUDIT}:8: F3 is closed with no `Resolution:` line",
        f"{AUDIT}:10: F4 is waived with no `Waived-by: @person: <reason>` line",
    ]


def test_a_malformed_or_repeated_finding_is_reported(repo, capsys):
    repo.commit("audit", audit(
        "## F1 [closed]: fine\n"
        "Resolution: fixed\n"
        "## F2 [opne]: a typo in the status\n"
        "## F1 [closed]: the same id again\n"
        "Resolution: fixed\n"
    ))
    code, out = run(repo, capsys)
    assert code == 1
    assert out == [
        f"{AUDIT}:4: not a finding; a finding is `## F<n> [open|closed|waived]: <text>`",
        f"{AUDIT}:5: F1 is repeated (first at line 2)",
    ]


def test_an_unknown_change_is_an_error(repo, capsys):
    repo.commit("empty")
    code, out = run(repo, capsys, "nope")
    assert code == 2
    assert out == ["redline: no change redline/changes/nope"]
