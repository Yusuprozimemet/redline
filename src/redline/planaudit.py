"""Plan audits of a critical initiative, at each phase's start and end. See docs/design.md §4, §6, §9.

The plan-auditor's reply is redline/initiatives/<id>/audits/phase-<n>-start.md or phase-<n>-end.md,
in the form of audit.md (audit.py). An initiative is critical when any change it lists is. `start`
needs, on main, every earlier phase's end audit and its own phase's start audit. check-plan needs
the end audit of every phase complete on main, read from the tree it checks, so the PR that adds
one passes; it runs on every PR, which is how a stopping point refuses (`merged` only prints).
"""

from pathlib import Path

from redline.audit import read_findings
from redline.config import rigor
from redline.order import git
from redline.plan import ROOT, Plan, initiatives, read_plan
from redline.start import complete, merged_steps

AGENT = "redline-plan-auditor"


def audit_path(plan: Plan, number: int, when: str) -> str:
    return f"{ROOT}/{plan.name}/audits/phase-{number}-{when}.md"


def critical(repo: Path, plan: Plan) -> bool:
    return any(rigor(repo, change) == "critical" for phase in plan.phases for change in phase.changes)


def unresolved(repo: Path, plan: Plan, number: int, when: str, rev: str | None = None) -> list[str]:
    """Why the phase's audit is missing or unresolved, read from `rev`, else the working tree."""
    where = audit_path(plan, number, when)
    if rev:
        shown = git(repo, "show", f"{rev}:{where}")
        text = shown.stdout if shown.returncode == 0 else None
    else:
        text = (repo / where).read_text(encoding="utf-8") if (repo / where).is_file() else None
    if text is None:
        return [f"{where}: missing; run the plan-auditor on `{plan.name} phase {number} {when}`"]
    return read_findings(text, where).bad


def before_start(repo: Path, plan: Plan, index: int) -> list[str]:
    """What `start` needs on main before a step of the phase at `index`."""
    if not critical(repo, plan):
        return []
    wanted = [(phase.number, "end") for phase in plan.phases[:index]] + [(plan.phases[index].number, "start")]
    return [bad for number, when in wanted for bad in unresolved(repo, plan, number, when, "main")]


def check_plan_audits(repo: Path, name: str | None = None) -> list[str]:
    """check-plan's part: the end audit of every phase complete on main, at critical."""
    bad: list[str] = []
    done = None
    for plan in [read_plan(repo, n) for n in ([name] if name else initiatives(repo))]:
        if not critical(repo, plan):
            continue
        done = merged_steps(repo) if done is None else done
        for phase in plan.phases:
            if all(complete(repo, change, done) for change in phase.changes):
                bad += [f"{plan.name}: {why}" for why in unresolved(repo, plan, phase.number, "end")]
    return bad


def due(repo: Path, plan: Plan, index: int) -> str:
    """What `merged` prints at a critical stopping point: the audits now due."""
    if not critical(repo, plan):
        return ""
    number = plan.phases[index].number
    said = (f"Its end audit is due: run {AGENT} on `{plan.name} phase {number} end`; write its reply unedited "
            f"to {audit_path(plan, number, 'end')}, in a PR outside any step. Until it lands with every finding "
            f"resolved, check-plan fails on every PR.\n")
    if index + 1 < len(plan.phases):
        following = plan.phases[index + 1].number
        said += (f"Before phase {following}'s first step, its start audit is due too: "
                 f"`{plan.name} phase {following} start` ({audit_path(plan, following, 'start')}).\n")
    return said
