"""Initiatives: redline/initiatives/<id>/plan.md, a goal reached in phases. See §3, §4, §6.

A plan has a `Goal:` line, then `## Phase <n>: <name>` headings numbered 1, 2, … in order, each
with a `Changes: a, b` line and a `Stop:` line, its stopping point. The plan is the only place
that puts a change in an initiative, and a change may be listed once across every plan. An
optional `Rigor:` line before the first phase is the initiative's own level (planaudit.py).
"""

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from redline.config import LEVELS, RIGOR
from redline.order import git, shown

ROOT = "redline/initiatives"
PHASE = re.compile(r"^## Phase (\d+): (.+)$")
GOAL = re.compile(r"^Goal:(.*)$")
CHANGES = re.compile(r"^Changes:(.*)$")
STOP = re.compile(r"^Stop:(.*)$")


@dataclass
class Phase:
    number: int
    name: str
    changes: list[str] = field(default_factory=list)
    stop: str = ""


@dataclass
class Plan:
    name: str
    goal: str = ""
    phases: list[Phase] = field(default_factory=list)
    rigor: str = ""  # its `Rigor:` line; "" when it has none


@dataclass
class Report:
    plans: int
    phases: int
    bad: list[str]


def initiatives(repo: Path, rev: str | None = None) -> list[str]:
    """The initiatives with a plan in the working tree, or at `rev`."""
    if rev is None:
        return sorted(path.parent.name for path in (repo / ROOT).glob("*/plan.md"))
    listed = git(repo, "ls-tree", "-r", "--name-only", rev, "--", ROOT).stdout.split()
    return sorted(p.split("/")[2] for p in listed if p.endswith("/plan.md") and p.count("/") == 3)


def read_plan(repo: Path, name: str, rev: str | None = None) -> Plan:
    path = f"{ROOT}/{name}/plan.md"
    if (text := shown(repo, path, rev)) is None:
        raise RuntimeError(f"no plan {path}")
    return parse_plan(name, text)


def parse_plan(name: str, text: str) -> Plan:
    plan = Plan(name)
    for line in text.splitlines():
        if heading := PHASE.match(line):
            plan.phases.append(Phase(int(heading[1]), heading[2].strip()))
        elif not plan.phases and (goal := GOAL.match(line)):
            plan.goal = goal[1].strip()
        elif not plan.phases and (level := RIGOR.match(line)):
            plan.rigor = level[1]
        elif plan.phases and (listed := CHANGES.match(line)):
            plan.phases[-1].changes += [c.strip() for c in listed[1].split(",") if c.strip()]
        elif plan.phases and (stop := STOP.match(line)):
            plan.phases[-1].stop = stop[1].strip()
    return plan


def placed(repo: Path, change: str, rev: str | None = None) -> tuple[Plan, int] | None:
    """The plan that lists the change, and the index of its phase there, in the working tree or at `rev`."""
    for name in initiatives(repo, rev):
        plan = read_plan(repo, name, rev)
        for index, phase in enumerate(plan.phases):
            if change in phase.changes:
                return plan, index
    return None


def check_plan(repo: Path, name: str | None = None) -> Report:
    every = [read_plan(repo, n) for n in initiatives(repo)]
    plans = [read_plan(repo, name)] if name else every
    listed = Counter(c for plan in every for phase in plan.phases for c in phase.changes)
    bad = []
    for plan in plans:
        why = [] if plan.goal else ["no Goal: line"]
        why += [f"unknown rigor level `{plan.rigor}`"] if plan.rigor and plan.rigor not in LEVELS else []
        why += [] if plan.phases else ["no phases"]
        for number, phase in enumerate(plan.phases, 1):
            if phase.number != number:
                why.append(f"phase {phase.number} is out of order; expected phase {number}")
            if not phase.changes:
                why.append(f"phase {phase.number} has no changes")
            if not phase.stop:
                why.append(f"phase {phase.number} has no Stop: line")
        mine = sorted({c for phase in plan.phases for c in phase.changes})
        why += [f"{c} is listed twice" for c in mine if listed[c] > 1]
        bad += [f"{plan.name}: {w}" for w in why]
    return Report(len(plans), sum(len(plan.phases) for plan in plans), bad)
