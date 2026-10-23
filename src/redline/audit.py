"""Audit findings: a change's spec may not merge while the auditor has an unresolved finding.

Findings live in redline/changes/<change>/audit.md, one `## F<n> [open|closed|waived|deferred]: <text>`
heading each. A [closed] finding needs a `Resolution: <text>` line under it, a [waived] one a
`Waived-by: @person: <reason>` line, and a [deferred] one `Deferred-to: O-<ID>, by @person`. Only the auditor writes findings; a waiver line is the
approving person's. A missing audit.md, an [open] finding, a resolved one without its line, a
`## ` heading that isn't a finding, and a repeated ID are each reported with their file:line.
Before the first finding, a `Model:` line names the model the auditor ran on: Fable, or Opus when Fable
isn't available, never a weaker one (§9); `unnamed` reads it, and the relabel's `# Model:` line too.
A change's audit also names its `Round:`, at most its level's limit, and the commit it read, `Audited:`;
`brief` prints the next round's prompt, and refuses past the limit (§9, Rounds).
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from redline.config import rigor
from redline.order import git

FINDING = re.compile(r"^## (F\d+) \[(open|closed|waived|deferred)\]: (.+)$")
STRONG = re.compile(r"\b(?:fable|opus)\b", re.I)  # the models an audit may run on (§2.5)
NEEDS = {
    "closed": (re.compile(r"^Resolution: \S"), "`Resolution:`"),
    "waived": (re.compile(r"^Waived-by: @\S+: \S"), "`Waived-by: @person: <reason>`"),
    "deferred": (re.compile(r"^Deferred-to: O-[A-Z0-9-]+, by @\S+$"), "`Deferred-to: O-<ID>, by @person`"),
}
LIMITS = {"lite": 1, "standard": 2, "critical": 3}  # a change's audit rounds, by its level
HEADER = {"round": re.compile(r"^Round: ([1-9]\d*)(?: of \d+)?$"), "audited": re.compile(r"^Audited: ([0-9a-f]{40})$")}


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
    text = (repo / where).read_text(encoding="utf-8")
    report, found, level = read_findings(text, where), header(text), rigor(repo, change)
    run = f"run the auditor on `redline audit-brief {change}`"
    if "round" not in found:
        report.bad.append(f"{where}: no `Round: <n>` line; {run}")
    elif int(found["round"][1]) > LIMITS[level]:
        n, value = found["round"]
        report.bad.append(f"{where}:{n}: round {value} is past {change}'s limit of {LIMITS[level]} at {level}")
    if "audited" not in found:
        report.bad.append(f"{where}: no `Audited: <commit>` line; {run}")
    return report


def header(text: str) -> dict[str, tuple[int, str]]:
    """The audit's `Round:` and `Audited:` values before its first finding, each with its line number."""
    found: dict[str, tuple[int, str]] = {}
    for n, line in enumerate(text.splitlines(), 1):
        if line.startswith("## "):
            break
        for key, pattern in HEADER.items():
            if key not in found and (value := pattern.match(line)):
                found[key] = (n, value[1])
    return found


def brief(repo: Path, change: str) -> str:
    """The auditor's whole prompt for the change's next round: its number, the commit it reads, and the diff since
    the commit the last round read, or `Since: none` for a full read (§9, Rounds)."""
    if not (repo / "redline/changes" / change).is_dir():
        raise RuntimeError(f"no change redline/changes/{change}")
    if git(repo, "status", "--porcelain", "--untracked-files=no").stdout.strip():
        raise RuntimeError(f"{change}: the working tree has uncommitted changes; commit them, "
                           "since `Audited:` names the commit the auditor reads")
    where, limit = f"redline/changes/{change}/audit.md", LIMITS[rigor(repo, change)]
    since = None
    if not (repo / where).is_file():
        n = 1
    elif "round" in (found := header((repo / where).read_text(encoding="utf-8"))):
        n, since = int(found["round"][1]) + 1, found.get("audited", (0, None))[1]
    else:  # written before the limit: one last round, since the commit its last reply read
        n, last = limit, git(repo, "log", "-1", "--format=%H", "HEAD", "--", where).stdout.strip()
        since = git(repo, "rev-parse", "-q", "--verify", f"{last}^").stdout.strip() if last else None
    if n > limit:
        raise RuntimeError(f"{change}: round {n - 1} of {limit} has run; the maintainer waives or defers "
                           "each open finding (`Waived-by:`, `Deferred-to:`)")
    if since and git(repo, "merge-base", "--is-ancestor", since, "HEAD").returncode:
        since = None  # gone from HEAD's history, as after a rebase
    head = git(repo, "rev-parse", "HEAD").stdout.strip()
    text = f"Audit {change}\nRound: {n} of {limit}\nAudited: {head}\nSince: {since or 'none'}\n"
    return text + ("\n" + git(repo, "diff", since, "HEAD", "--", ".", f":(exclude){where}").stdout if since else "")


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
            report.bad.append(f"{where}:{n}: not a finding; a finding is `## F<n> [open|closed|waived|deferred]: <text>`")
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
