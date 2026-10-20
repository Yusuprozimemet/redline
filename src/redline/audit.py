"""Audit findings: a change's spec may not merge while the auditor has an unresolved finding.

Findings live in redline/changes/<change>/audit.md, one `## F<n> [open|closed|waived]: <text>`
heading each. A [closed] finding needs a `Resolution: <text>` line under it, and a [waived] one a
`Waived-by: @person: <reason>` line. Only the auditor writes findings; a waiver line is the
approving person's. A missing audit.md, an [open] finding, a resolved one without its line, a
`## ` heading that isn't a finding, and a repeated ID are each reported with their file:line.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

FINDING = re.compile(r"^## (F\d+) \[(open|closed|waived)\]: (.+)$")
NEEDS = {
    "closed": (re.compile(r"^Resolution: \S"), "`Resolution:`"),
    "waived": (re.compile(r"^Waived-by: @\S+: \S"), "`Waived-by: @person: <reason>`"),
}


@dataclass
class AuditReport:
    findings: int = 0
    bad: list[str] = field(default_factory=list)


def check_audit(repo: Path, change: str) -> AuditReport:
    if not (repo / "redline/changes" / change).is_dir():
        raise RuntimeError(f"no change redline/changes/{change}")
    where = f"redline/changes/{change}/audit.md"
    if not (repo / where).is_file():
        return AuditReport(bad=[f"{where}: missing; run the auditor on the change"])
    return read_findings((repo / where).read_text(encoding="utf-8"), where)


def read_findings(text: str, where: str) -> AuditReport:
    """The findings of an audit file's text, and what is wrong with them; plan audits use it too."""
    report = AuditReport()
    lines = text.splitlines()
    seen: dict[str, int] = {}
    for n, line in enumerate(lines, 1):
        if not line.startswith("## "):
            continue
        if not (finding := FINDING.match(line)):
            report.bad.append(f"{where}:{n}: not a finding; a finding is `## F<n> [open|closed|waived]: <text>`")
            continue
        fid, status, text = finding.groups()
        report.findings += 1
        if fid in seen:
            report.bad.append(f"{where}:{n}: {fid} is repeated (first at line {seen[fid]})")
            continue
        seen[fid] = n
        if status == "open":
            report.bad.append(f"{where}:{n}: {fid} is open: {text}")
            continue
        body = []
        for rest in lines[n:]:
            if rest.startswith("#"):
                break
            body.append(rest)
        pattern, wanted = NEEDS[status]
        if not any(pattern.match(rest) for rest in body):
            report.bad.append(f"{where}:{n}: {fid} is {status} with no {wanted} line")
    return report
