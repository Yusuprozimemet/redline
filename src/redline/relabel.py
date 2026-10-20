"""Blind relabelling of a change's defects, at critical. See docs/design.md, §4 and §9.

`redline blind <change>` prints defects.md without its Cause: and Decided: lines, for the
relabeller agent, whose reply is relabel.yaml: per defect, a `cause` (a label or `unclear`) and a
`note`. check-relabel prints each disagreement with the log's Cause: and fails on a missing
relabel at C (critical), a defect with no label or a label with no defect, an unknown label or no
note, and a disagreement, or a Cause: changed since the relabel first labelled it, with no
Decided: line.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from redline.config import rigor
from redline.defects import CAUSE, CAUSES, DEFECT, check_defects
from redline.order import git
from redline.start import Refused

DECIDED = re.compile(r"^Decided:\s*\S")


@dataclass
class RelabelReport:
    labelled: int = 0
    disagreements: list[str] = field(default_factory=list)
    bad: list[str] = field(default_factory=list)


def causes(text: str) -> dict[str, tuple[str, bool]]:
    """Each defect's Cause:, and whether it has a Decided: line."""
    found: dict[str, tuple[str, bool]] = {}
    current = None
    for line in text.splitlines():
        if line.startswith("## "):
            current = heading[1] if (heading := DEFECT.match(line)) else None
            if current:
                found.setdefault(current, ("", False))
        elif current and (cause := CAUSE.match(line)):
            found[current] = (cause[1].strip(), found[current][1])
        elif current and DECIDED.match(line):
            found[current] = (found[current][0], True)
    return found


def blind(repo: Path, change: str) -> str:
    log = repo / f"redline/changes/{change}/defects.md"
    report = check_defects(repo, change)
    if report.bad or not log.is_file():
        raise Refused("the defect log is not well formed:\n" + "\n".join(report.bad or [f"{log.name}: missing"]))
    return "".join(f"{line}\n" for line in log.read_text(encoding="utf-8").splitlines()
                   if not CAUSE.match(line) and not line.startswith("Decided:"))


def firsts(repo: Path, change: str, log: str, path: str) -> dict[str, str]:
    """Each labelled defect's first label: its Cause: before the first commit that relabelled it."""
    found: dict[str, str] = {}
    for commit in git(repo, "log", "--reverse", "--format=%H", "HEAD", "--", path).stdout.split():
        shown = git(repo, "show", f"{commit}:{path}")
        labelled = (yaml.safe_load(shown.stdout) if shown.returncode == 0 else None) or {}
        was, now = (causes(git(repo, "show", f"{rev}:{log}").stdout) for rev in (f"{commit}^", commit))
        for d in labelled:
            if d not in found and (d in was or d in now):
                found[d] = (was.get(d) or now[d])[0]
    return found


def check_relabel(repo: Path, change: str, required: bool = True) -> RelabelReport:
    log, path = f"redline/changes/{change}/defects.md", f"redline/changes/{change}/relabel.yaml"
    report = RelabelReport()
    if not (repo / path).is_file():
        if required and rigor(repo, change) == "critical":
            report.bad.append(f"{path}: missing; at C a critical change has its defects relabelled blind")
        return report
    labels = yaml.safe_load((repo / path).read_text(encoding="utf-8")) or {}
    logged = causes((repo / log).read_text(encoding="utf-8")) if (repo / log).is_file() else {}
    first = firsts(repo, change, log, path)
    report.bad += [f"{d}: no label in relabel.yaml; run the relabeller again" for d in logged if d not in labels]
    for d, entry in labels.items():
        if d not in logged:
            report.bad.append(f"{d}: labelled, but the log has no {d}")
            continue
        entry = entry if isinstance(entry, dict) else {}
        second, note = str(entry.get("cause") or ""), entry.get("note")
        if second not in (*CAUSES, "unclear"):
            report.bad.append(f"{d}: `{second}` is not a cause or unclear")
        if not note:
            report.bad.append(f"{d}: no note")
        cause, decided = logged[d]
        report.labelled += 1
        if second != cause:
            report.disagreements.append(f"disagree {d}: Cause: {cause}, relabelled {second}: {note}")
            if not decided:
                report.bad.append(f"{d}: Cause: {cause} and the relabel's {second} disagree, with no Decided: line")
        if first.get(d, cause) != cause and not decided:
            report.bad.append(f"{d}: Cause: changed from {first[d]} to {cause} after the relabel, with no Decided: line")
    return report
