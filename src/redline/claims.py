"""`redline claims <initiative>`: the claims main's history holds, for the process auditor. See docs/design.md §4, §7, §9.

The commits are main's non-merge commits whose `Redline-Step` names a step of a change the plan on main
lists, or that touch the initiative's directory or redline/config.yaml, oldest first. Each with a claim
trailer (approval.py) is printed with its merged PR and, per claim, its label, who applied it last and
their role now, read through the `GitHub` seam (pr.py). It writes nothing and judges nothing.
"""

from pathlib import Path

from redline.approval import DEPARTURE, OVERSIZED, RIGOR, TRACK
from redline.order import git
from redline.plan import ROOT, parse_plan
from redline.pr import GitHub
from redline.start import TRAILER

LABELS = {"Oversized": OVERSIZED, "Redline-Track": TRACK, "Redline-Departure": DEPARTURE, "Redline-Rigor": RIGOR}
CONFIG = "redline/config.yaml"


def label(github, applied: dict[int, dict[str, str]], number: int | None, name: str) -> str:
    if number is None:
        return "Label: no merged PR found for this commit\n"
    if number not in applied:
        applied[number] = github.labels(number)
    if (who := applied[number].get(name)) is None:
        return f"Label: {name}: not on PR #{number}\n"
    return f"Label: {name}, applied by @{who}, now {github.role(who)}\n"


def claims(repo: Path, name: str) -> str:
    shown = git(repo, "show", f"main:{ROOT}/{name}/plan.md")
    if shown.returncode:
        raise RuntimeError(f"no plan {ROOT}/{name}/plan.md on main")
    changes = [c for phase in parse_plan(name, shown.stdout).phases for c in phase.changes]
    touching = set(git(repo, "log", "main", "--no-merges", "--full-history", "--format=%H",
                       "--", f"{ROOT}/{name}", CONFIG).stdout.split())
    log = git(repo, "log", "main", "--no-merges", "--reverse", "--format=%x1e%H%x1f%s%x1f%(trailers:only,unfold)")
    github, applied = GitHub(repo), {}
    commits = made = 0
    said = ""
    for record in log.stdout.split("\x1e")[1:]:
        sha, subject, block = record.split("\x1f")
        trailers = [(key, value.strip()) for key, _, value in (line.partition(":") for line in block.splitlines())]
        steps = [value for key, value in trailers if key == TRAILER]
        if sha not in touching and not any(s.partition("/")[0] in changes for s in steps):
            continue
        commits += 1
        if not (claimed := [(key, value) for key, value in trailers if key in LABELS]):
            continue
        number = next(iter(github.pulls(sha)), None)
        said += f"\n## {sha[:7]} {', '.join(steps) or 'outside any step'}{f' (PR #{number})' if number else ''}: {subject}\n"
        for key, value in claimed:
            said += f"{key}: {value}\n" + label(github, applied, number, LABELS[key])
        made += len(claimed)
    head = (f"# Claims: {name}\nFrom main: {made} claim{'' if made == 1 else 's'} on {commits} "
            f"commit{'' if commits == 1 else 's'}: the steps of {', '.join(changes)}, and every commit "
            f"that touches {ROOT}/{name}/ or {CONFIG}.\n")
    return head + (said or "\nNo claims.\n")
