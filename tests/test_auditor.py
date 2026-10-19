"""The auditor agent definition: read-only, on the strongest model, writing findings check-audit reads."""

import re
from pathlib import Path

import yaml

from redline.audit import check_audit

AGENT = Path(__file__).parent.parent / ".claude/agents/redline-auditor.md"
READ_ONLY = {"Read", "Grep", "Glob"}


def definition() -> tuple[dict, str]:
    _, front, body = AGENT.read_text(encoding="utf-8").split("---\n", 2)
    return yaml.safe_load(front), body


def test_the_auditor_is_read_only():
    front, _ = definition()
    assert front["name"] == "redline-auditor"
    tools = {tool.strip() for tool in front.get("tools", "").split(",")} - {""}
    assert tools, "with no tools line the agent inherits every tool, Write and Bash included"
    assert tools <= READ_ONLY, f"write-capable tools: {tools - READ_ONLY}"


def test_the_auditor_runs_on_the_strongest_model_and_refuses_any_other():
    front, body = definition()
    assert front["model"] == "fable"
    assert "REFUSED: the auditor runs only on a Claude Fable model" in body


def test_the_auditor_checks_premises_then_clauses_and_rigor():
    _, body = definition()
    for duty in ("## 1. Premises", "## 2. THEN clauses", "## 3. Rigor"):
        assert duty in body
    assert "never lower" in body


def test_the_documented_output_is_an_audit_check_audit_reads(repo):
    _, body = definition()
    example = re.search(r"```markdown\n(# Audit: .+?)```", body, re.S)
    assert example, "the definition shows an example audit.md in a ```markdown block"
    repo.commit("audit", {"redline/changes/add-2fa/audit.md": example[1]})
    report = check_audit(repo.path, "add-2fa")
    assert report.findings == 3
    assert [bad.split(": ", 1)[1] for bad in report.bad] == [
        "F1 is open: P2 is wrong; `auth/login.py:30` already calls `verify_code`",
    ]
