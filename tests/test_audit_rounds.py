"""Audit rounds (docs/design.md §9, Rounds; O-AUDIT2): `redline audit-brief` numbers each round, refuses past the
change's level, and gives a re-round only what changed since the commit the last one read; check-audit reads it."""

import pytest

from redline.cli import main

AUDIT = "redline/changes/add-login/audit.md"
DELTA = "redline/changes/add-login/specs/auth/delta.md"
PROPOSAL = "redline/changes/add-login/proposal.md"


def brief(repo, capsys) -> tuple[int, str]:
    code = main(["audit-brief", "add-login", "--repo", str(repo.path)])
    return code, capsys.readouterr().out


def audited(n: int, commit: str) -> str:
    return f"# Audit: add-login\nModel: claude-opus-5-5\nRound: {n}\nAudited: {commit}\n\n## F1 [open]: P1 is wrong\n"


@pytest.mark.parametrize(("level", "limit"), [("lite", 1), ("standard", 2), ("critical", 3)])
def test_the_first_round_reads_everything_and_names_the_limit_of_its_level(repo, capsys, level, limit):
    head = repo.commit("spec", {DELTA: "### Premises\n", PROPOSAL: f"# Proposal\n\nRigor: {level}\n"})
    assert brief(repo, capsys) == (0, f"Audit add-login\nRound: 1 of {limit}\nAudited: {head}\nSince: none\n")


def test_a_re_round_reads_only_the_diff_since_the_commit_the_last_one_read(repo, capsys):
    read = repo.commit("spec", {DELTA: "### Premises\n- P1: old\n"})
    head = repo.commit("audit and fix", {AUDIT: audited(1, read), DELTA: "### Premises\n- P1: new\n"})
    code, out = brief(repo, capsys)
    assert code == 0
    assert out.startswith(f"Audit add-login\nRound: 2 of 2\nAudited: {head}\nSince: {read}\n\ndiff --git")
    assert "+- P1: new" in out and "-- P1: old" in out
    assert "audit.md" not in out, "the auditor reads its old audit.md itself"


def test_the_brief_refuses_once_the_last_round_has_run(repo, capsys):
    read = repo.commit("spec", {DELTA: "### Premises\n", PROPOSAL: "Rigor: critical\n"})
    repo.commit("third audit", {AUDIT: audited(3, read)})
    assert brief(repo, capsys) == (2, "redline: add-login: round 3 of 3 has run; the maintainer waives or defers "
                                      "each open finding (`Waived-by:`, `Deferred-to:`)\n")
    repo.commit("second audit", {AUDIT: audited(2, read)})
    assert brief(repo, capsys)[1].startswith("Audit add-login\nRound: 3 of 3\n")


def test_a_last_read_commit_gone_from_history_reads_everything_again(repo, capsys):
    head = repo.commit("audit", {DELTA: "### Premises\n", AUDIT: audited(1, "0123456789" * 4)})
    assert brief(repo, capsys) == (0, f"Audit add-login\nRound: 2 of 2\nAudited: {head}\nSince: none\n")


def test_an_audit_from_before_the_limit_gets_one_last_round_since_its_last_reply(repo, capsys):
    read = repo.commit("spec", {DELTA: "### Premises\n- P1: old\n", PROPOSAL: "Rigor: critical\n"})
    repo.commit("fifth audit", {AUDIT: "# Audit: add-login\nModel: claude-opus-5-5\n\n## F1 [open]: x\n",
                                DELTA: "### Premises\n- P1: new\n"})
    head = repo.commit("unrelated", {"README.md": "hi\n"})
    code, out = brief(repo, capsys)
    assert code == 0
    assert out.startswith(f"Audit add-login\nRound: 3 of 3\nAudited: {head}\nSince: {read}\n\ndiff --git")
    assert "+- P1: new" in out


def test_the_brief_refuses_uncommitted_changes_and_an_unknown_change(repo, capsys):
    repo.commit("spec", {DELTA: "### Premises\n"})
    (repo.path / DELTA).write_text("### Premises\n- P1: unsaved\n", encoding="utf-8")
    assert brief(repo, capsys) == (2, "redline: add-login: the working tree has uncommitted changes; commit them, "
                                      "since `Audited:` names the commit the auditor reads\n")
    code = main(["audit-brief", "nope", "--repo", str(repo.path)])
    assert (code, capsys.readouterr().out) == (2, "redline: no change redline/changes/nope\n")


def check(repo, capsys, text: str) -> tuple[int, list[str]]:
    repo.commit("audit", {DELTA: "### Premises\n", AUDIT: text})
    code = main(["check-audit", "add-login", "--repo", str(repo.path)])
    return code, capsys.readouterr().out.splitlines()


SHA = "0123456789" * 4


@pytest.mark.parametrize(("header", "why"), [
    (f"Audited: {SHA}\n", f"{AUDIT}: no `Round: <n>` line; run the auditor on `redline audit-brief add-login`"),
    (f"Round: 0\nAudited: {SHA}\n", f"{AUDIT}: no `Round: <n>` line; run the auditor on `redline audit-brief add-login`"),
    ("Round: 1\n", f"{AUDIT}: no `Audited: <commit>` line; run the auditor on `redline audit-brief add-login`"),
    (f"Round: 3\nAudited: {SHA}\n", f"{AUDIT}:3: round 3 is past add-login's limit of 2 at standard"),
], ids=["no-round", "round-0", "no-audited", "past-the-limit"])
def test_check_audit_fails_an_audit_without_its_round_or_past_the_limit(repo, capsys, header, why):
    assert check(repo, capsys, f"# Audit: add-login\nModel: claude-opus-5-5\n{header}\nNo findings.\n") == (1, [why])


def test_a_deferred_finding_needs_its_open_problem_and_its_person(repo, capsys):
    head = f"# Audit: add-login\nModel: claude-opus-5-5\nRound: 2\nAudited: {SHA}\n"
    assert check(repo, capsys, head + "## F1 [deferred]: x\nDeferred-to: O-2FA3, by @maintainer\n") == (
        0, ["ok: 1 finding, none open"])
    assert check(repo, capsys, head + "## F1 [deferred]: x\nDeferred-to: later\n") == (
        1, [f"{AUDIT}:5: F1 is deferred with no `Deferred-to: O-<ID>, by @person` line"])
