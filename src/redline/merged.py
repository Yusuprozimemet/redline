"""`redline merged <change>/<step>`: confirm the step merged, sync main and hand off the next step.

Main is synced first (fetch, then fast-forward local main), so the check sees what GitHub merged.
The step is merged when its `Redline-Step` trailer is reachable from main; if not, nothing else
happens. Once it is, the checkout switches to main (the step branch is done, and the next step
starts fresh from main) and the open-step record is cleared if the step it names is merged. Then
the next step's brief is printed, or, after the last step, that the change is complete, and, if
that completes its initiative's phase, the stopping point and the next phase.
Uncommitted changes refuse before anything syncs. Fetching sits behind `Remote`, which tests
replace.
"""

import subprocess
from pathlib import Path

from redline.order import git
from redline.plan import placed
from redline.planaudit import due
from redline.start import Refused, brief, complete, find_step, merged_steps, open_step_file


class Remote:
    """Everything that goes over the network."""

    def __init__(self, repo: Path):
        self.repo = repo

    def run(self, *command: str) -> None:
        done = subprocess.run(command, cwd=self.repo, capture_output=True, text=True)
        if done.returncode:
            raise RuntimeError(f"{' '.join(command[:3])}: {done.stderr.strip()}")

    def sync(self) -> None:
        """Fetch origin, then fast-forward local main to origin/main (never a merge or reset)."""
        self.run("git", "fetch", "-q", "origin")
        if git(self.repo, "branch", "--show-current").stdout.strip() == "main":
            self.run("git", "merge", "-q", "--ff-only", "origin/main")
        else:
            self.run("git", "fetch", "-q", ".", "origin/main:main")


def stopping_point(repo: Path, change: str, done: set[str]) -> str:
    """When the change completes its initiative's phase: the stop, then what comes next, if anything."""
    if not (found := placed(repo, change)):
        return ""
    plan, index = found
    phase = plan.phases[index]
    if not all(complete(repo, c, done) for c in phase.changes):
        return ""
    said = (f"The initiative {plan.name} is at a stopping point: phase {phase.number} ({phase.name}) "
            f"is complete.\nStop: {phase.stop}\n") + due(repo, plan, index)
    if index == len(plan.phases) - 1:
        return said + f"The initiative {plan.name} is complete.\n"
    following = plan.phases[index + 1]
    return said + (f"Next: phase {following.number} ({following.name}): {', '.join(following.changes)}. "
                   f"Going on is the maintainer's call.\n")


def merged(repo: Path, name: str) -> str:
    """Return the hand-off for the step after `name`, once `name` is merged on main."""
    change, steps, index = find_step(repo, name)
    if git(repo, "status", "--porcelain").stdout.strip():
        raise Refused("there are uncommitted changes; commit or stash them first")
    Remote(repo).sync()
    done = merged_steps(repo)
    if name not in done:
        raise Refused(f"{name} is not merged on main; merge its PR, then run this again")
    switched = git(repo, "checkout", "-q", "main")
    if switched.returncode:
        raise RuntimeError(f"could not switch to main: {switched.stderr.strip()}")
    state = open_step_file(repo)
    if state.is_file() and state.read_text().strip() in done:
        state.unlink()
    said = f"ok: {name} is merged on main; switched to main.\n"
    if index == len(steps) - 1:
        retro = f"Run `redline retro {change}` to propose rule changes from its defect log.\n"
        return said + f"The change {change} is complete.\n" + retro + stopping_point(repo, change, done)
    following = steps[index + 1]
    return said + (
        f"This session is over. In a new session, on a new branch fresh from main, run "
        f"`redline start {change}/{following.name}`. Its brief:\n\n" + brief(repo, change, following)
    )
