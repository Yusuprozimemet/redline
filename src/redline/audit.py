"""Audit findings: a change's spec may not merge while the auditor has an unresolved finding.

Findings live in redline/changes/<change>/audit.md, one `## F<n> [open|closed|waived]: <text>`
heading each. A [closed] finding needs a `Resolution: <text>` line under it, and a [waived] one a
`Waived-by: @person: <reason>` line. Only the auditor writes findings; a waiver line is the
approving person's. A missing audit.md, an [open] finding, a resolved one without its line, a
`## ` heading that isn't a finding, and a repeated ID are each reported with their file:line.
Before the first finding, a `Model:` line names the model the auditor ran on: Fable, or Opus when Fable
isn't available, never a weaker one (§9); `unnamed` reads it, and the relabel's `# Model:` line too.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

FINDING = re.compile(r"^## (F\d+) \[(open|closed|waived)\]: (.+)$")
STRONG = re.compile(r"\b(?:fable|opus)\b", re.I)  # the models an audit may run on (§2.5)
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


def unnamed(text: str, where: str, prefix: str = "Model:", agent: str = "the auditor", first: str = "finding") -> list[str]:
    """Why the lines before the first finding (or relabel entry) name no Fable or Opus model, or nothing."""
    for n, line in enumerate(text.splitlines(), 1):
        if line.startswith(prefix):
            name = line[len(prefix):].strip()
            return [] if STRONG.search(name) else [
                f"{where}:{n}: {prefix} {name} is neither a Fable nor an Opus model; run {agent} on Fable, or on Opus at max effort"]
        if line.startswith("## ") if first == "finding" else line.strip() and not line.startswith("#"):
            break
    return [f"{where}: no `{prefix}` line; {agent} names the model it ran on in a `{prefix}` line before the first {first}"]


def read_findings(text: str, where: str) -> AuditReport:
    """The findings of an audit file's text, and what is wrong with them; plan audits use it too."""
    report = AuditReport(bad=unnamed(text, where))
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
