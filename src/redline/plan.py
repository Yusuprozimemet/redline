"""Initiatives: redline/initiatives/<id>/plan.md, a goal reached in phases. See §3, §4, §6.

A plan has a `Goal:` line, then `## Phase <n>: <name>` headings numbered 1, 2, … in order, each
with a `Changes: a, b` line and a `Stop:` line, its stopping point. The plan is the only place
that puts a change in an initiative, and a change may be listed once across every plan.
"""

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

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


@dataclass
class Report:
    plans: int
    phases: int
    bad: list[str]


def initiatives(repo: Path) -> list[str]:
    return sorted(path.parent.name for path in (repo / ROOT).glob("*/plan.md"))


def read_plan(repo: Path, name: str) -> Plan:
    path = f"{ROOT}/{name}/plan.md"
    if not (repo / path).is_file():
        raise RuntimeError(f"no plan {path}")
    plan = Plan(name)
    for line in (repo / path).read_text(encoding="utf-8").splitlines():
        if heading := PHASE.match(line):
            plan.phases.append(Phase(int(heading[1]), heading[2].strip()))
        elif not plan.phases and (goal := GOAL.match(line)):
            plan.goal = goal[1].strip()
        elif plan.phases and (listed := CHANGES.match(line)):
            plan.phases[-1].changes += [c.strip() for c in listed[1].split(",") if c.strip()]
        elif plan.phases and (stop := STOP.match(line)):
            plan.phases[-1].stop = stop[1].strip()
    return plan


def placed(repo: Path, change: str) -> tuple[Plan, int] | None:
    """The plan that lists the change, and the index of its phase there."""
    for name in initiatives(repo):
        plan = read_plan(repo, name)
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
