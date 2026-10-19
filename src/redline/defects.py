"""The defect log, redline/changes/<change>/defects.md, and `redline retro`. See §4, §10.

Each defect is a `## D<n>: <what went wrong>` heading, one `Cause: <label>` line from CAUSES, and
a `Found-by:` line naming a step of any change (`<change>/<step>`) or a commit reachable from
main; other lines are free text. The cause sits on its own line so that blind relabelling can
hide it. A log is required at C, except at lite. retro groups a change's defects by cause and
proposes one rule per cause for the config's `rules:`; it writes nothing.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from redline.config import load_config, rigor
from redline.order import git
from redline.start import Refused, read_steps

CAUSES = ("premise", "spec", "test", "code", "handoff", "tooling")
DEFECT = re.compile(r"^## (D\d+): (.+)$")
CAUSE = re.compile(r"^Cause:(.*)$")
FOUND = re.compile(r"^Found-by:(.*)$")


@dataclass
class Defect:
    id: str
    what: str
    line: int
    causes: list[str] = field(default_factory=list)
    found: list[str] = field(default_factory=list)


@dataclass
class DefectReport:
    defects: list[Defect] = field(default_factory=list)
    bad: list[str] = field(default_factory=list)


def finder(repo: Path, name: str) -> bool:
    """Whether `name` is a step of some change's steps.md, or a commit reachable from main."""
    change, _, step = name.partition("/")
    if step:
        try:
            return any(s.name == step for s in read_steps(repo, change))
        except RuntimeError:
            return False
    return (re.fullmatch(r"[0-9a-f]{7,40}", name) is not None
            and git(repo, "merge-base", "--is-ancestor", name, "main").returncode == 0)


def check_defects(repo: Path, change: str, required: bool = True) -> DefectReport:
    if not (repo / "redline/changes" / change).is_dir():
        raise RuntimeError(f"no change redline/changes/{change}")
    where = f"redline/changes/{change}/defects.md"
    report = DefectReport()
    if not (repo / where).is_file():
        if required and rigor(repo, change) != "lite":
            report.bad.append(f"{where}: missing; at C a change keeps a defect log")
        return report
    seen: dict[str, int] = {}
    current = None
    for n, line in enumerate((repo / where).read_text(encoding="utf-8").splitlines(), 1):
        if line.startswith("## "):
            current = None
            if not (heading := DEFECT.match(line)):
                report.bad.append(f"{where}:{n}: not a defect; a defect is `## D<n>: <text>`")
            elif heading[1] in seen:
                report.bad.append(f"{where}:{n}: {heading[1]} is repeated (first at line {seen[heading[1]]})")
            else:
                seen[heading[1]] = n
                current = Defect(heading[1], heading[2].strip(), n)
                report.defects.append(current)
        elif current and (cause := CAUSE.match(line)):
            current.causes.append(cause[1].strip())
        elif current and (found := FOUND.match(line)):
            current.found.append(found[1].strip())
    for d in report.defects:
        at = f"{where}:{d.line}: {d.id}"
        if len(d.causes) != 1:
            report.bad.append(f"{at} has {'more than one' if d.causes else 'no'} Cause: line")
        elif d.causes[0] not in CAUSES:
            report.bad.append(f"{at}: Cause: {d.causes[0]} is not one of {', '.join(CAUSES)}")
        if not d.found:
            report.bad.append(f"{at} has no Found-by: line")
        report.bad += [f"{at}: Found-by: {f} names no step and no commit on main"
                       for f in d.found if not finder(repo, f)]
    return report


def retro(repo: Path, change: str) -> str:
    """The change's defects grouped by cause, most first, and one proposed rule per cause."""
    report = check_defects(repo, change)
    if report.bad or not (repo / f"redline/changes/{change}/defects.md").is_file():
        why = report.bad or [f"redline/changes/{change}/defects.md: missing; retro needs a defect log"]
        raise Refused("the defect log is not well formed:\n" + "\n".join(why))
    if not report.defects:
        return f"{change} has no defects; nothing to propose.\n"
    groups: dict[str, list[Defect]] = {}
    for d in report.defects:
        groups.setdefault(d.causes[0], []).append(d)
    order = sorted(groups, key=lambda c: (-len(groups[c]), CAUSES.index(c)))
    rules = load_config(repo).rules
    said = [f"retro {change}: {len(report.defects)} defect(s) by cause"]
    for cause in order:
        have = len(rules.get(cause) or [])
        ids = ", ".join(d.id for d in groups[cause])
        said.append(f"{cause}: {len(groups[cause])} ({ids}); {have} rule{'' if have == 1 else 's'} so far")
        said += [f"  {d.id}: {d.what}" for d in groups[cause]]
    said += ["", "Proposals, each its own small PR to redline/config.yaml; retro changes nothing:"]
    said += [f"{n}. Add a rule under rules.{c} against {', '.join(d.id for d in groups[c])}"
             for n, c in enumerate(order, 1)]
    return "\n".join(said) + "\n"
