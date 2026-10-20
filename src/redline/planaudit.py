"""Plan audits of a critical initiative, at each phase's start and end. See docs/design.md §4, §6, §9.

The plan-auditor's reply is redline/initiatives/<id>/audits/phase-<n>-start.md or phase-<n>-end.md,
in the form of audit.md (audit.py). An initiative is critical when any change it lists is. `start`
needs, on main, every earlier phase's end audit and its own phase's start audit. check-plan needs
the end audit of every phase complete on main, read from the tree it checks, so the PR that adds
one passes; it runs on every PR, which is how a stopping point refuses (`merged` only prints).
Once every phase is complete, it also needs the three end-of-initiative audits, initiative-<side>.md.
Each audit's second line, `Plan: <blob>`, is the plan it read. The newest audit each gate needs must be
current, its blob the plan's in the tree read: `start` the phase's start audit, check-plan the end audit
of the last complete phase and the three. Earlier audits need only be resolved.
"""

import re
from pathlib import Path

from redline.audit import read_findings
from redline.config import rigor
from redline.order import git
from redline.plan import ROOT, Plan, initiatives, read_plan
from redline.start import complete, merged_steps

AGENT = "redline-plan-auditor"
SIDES = ("security", "architecture", "process")
RECORDED = re.compile(r"\A.*\nPlan: (\S+)[ \t]*$", re.M)  # the second line


def audit_path(plan: Plan, number: int, when: str) -> str:
    return f"{ROOT}/{plan.name}/audits/phase-{number}-{when}.md"


def critical(repo: Path, plan: Plan, rev: str | None = None) -> bool:
    """Whether the plan's line or any change it lists, read at `rev`, else in the working tree, is critical."""
    return plan.rigor == "critical" or any(rigor(repo, c, rev) == "critical" for phase in plan.phases for c in phase.changes)


def blob(repo: Path, plan: Plan, rev: str | None = None) -> str:
    """The plan's blob at `rev`, else in the working tree."""
    path = f"{ROOT}/{plan.name}/plan.md"
    return (git(repo, "rev-parse", f"{rev}:{path}") if rev else git(repo, "hash-object", path)).stdout.strip()


def unresolved(repo: Path, plan: Plan, number: int, when: str, rev: str | None = None, current=False) -> list[str]:
    """Why the phase's audit is missing, unresolved or, if it must be `current`, stale; read from `rev`, else the tree."""
    run = f"the plan-auditor on `{plan.name} phase {number} {when}`"
    return unresolved_at(repo, plan, audit_path(plan, number, when), run, rev, current)


def side_path(plan: Plan, side: str) -> str:
    return f"{ROOT}/{plan.name}/audits/initiative-{side}.md"


def unresolved_at(repo: Path, plan: Plan, where: str, run: str, rev: str | None = None, current=False) -> list[str]:
    if rev:
        shown = git(repo, "show", f"{rev}:{where}")
        text = shown.stdout if shown.returncode == 0 else None
    else:
        text = (repo / where).read_text(encoding="utf-8") if (repo / where).is_file() else None
    run += f" with plan {(now := blob(repo, plan, rev))}"
    if text is None:
        return [f"{where}: missing; run {run}"]
    bad = read_findings(text, where).bad
    if current and not (read := RECORDED.search(text)):
        bad.append(f"{where}: no `Plan:` line; run {run} again")
    elif current and read[1] != now:
        bad.append(f"{where}: read plan {read[1]}, but {ROOT}/{plan.name}/plan.md is now {now}; run {run} again")
    return bad


def before_start(repo: Path, plan: Plan, index: int, rev: str = "main") -> list[str]:
    """What a step of the phase at `index` needs at `rev`: main for `start`, the merge-base in CI."""
    if not critical(repo, plan, rev):
        return []
    wanted = [(phase.number, "end", False) for phase in plan.phases[:index]] + [(plan.phases[index].number, "start", True)]
    return [bad for number, when, now in wanted for bad in unresolved(repo, plan, number, when, rev, now)]


def check_plan_audits(repo: Path, name: str | None = None) -> list[str]:
    """check-plan's part: the end audit of every phase complete on main, at critical, then the sides'."""
    bad: list[str] = []
    done = None
    for plan in [read_plan(repo, n) for n in ([name] if name else initiatives(repo))]:
        if not critical(repo, plan):
            continue
        done = merged_steps(repo) if done is None else done
        ended = [all(complete(repo, change, done) for change in phase.changes) for phase in plan.phases]
        last = max((i for i, end in enumerate(ended) if end), default=None)
        why = [w for i, (phase, end) in enumerate(zip(plan.phases, ended)) if end
               for w in unresolved(repo, plan, phase.number, "end", current=i == last)]
        if all(ended):
            why += [w for side in SIDES for w in unresolved_at(
                repo, plan, side_path(plan, side), f"redline-{side}-auditor on `{plan.name}`", current=True)]
        bad += [f"{plan.name}: {w}" for w in why]
    return bad


def due(repo: Path, plan: Plan, index: int) -> str:
    """What `merged` prints at a critical stopping point: the audits now due."""
    if not critical(repo, plan):
        return ""
    number = plan.phases[index].number
    said = (f"Its end audit is due: run {AGENT} on `{plan.name} phase {number} end`; write its reply unedited "
            f"to {audit_path(plan, number, 'end')}, in a PR outside any step. Until it lands with every finding "
            f"resolved, check-plan fails on every PR.\n"
            f"Give each auditor `with plan {blob(repo, plan, 'main')}` after its arguments: its `Plan:` line.\n")
    if index + 1 < len(plan.phases):
        following = plan.phases[index + 1].number
        said += (f"Before phase {following}'s first step, its start audit is due too: "
                 f"`{plan.name} phase {following} start` ({audit_path(plan, following, 'start')}).\n")
        return said
    said += ("The three end-of-initiative audits are due too, beside it and independently: none reads "
             "another's reply or the plan audits.\n")
    said += "".join(f"- run redline-{side}-auditor on `{plan.name}`; write its reply unedited to "
                    f"{side_path(plan, side)}\n" for side in SIDES)
    said += f"Give redline-process-auditor, after its arguments, the text `redline claims {plan.name}` prints.\n"
    return said + "Until all three land with every finding resolved, check-plan fails on every PR.\n"
