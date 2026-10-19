"""`redline pr`: run the local gates for the open step, then open its pull request.

check-lines always runs. check-premises and check-audit run at the S step, on the step's own
change. check-links
and check-order run from the R step on: at S the delta declares scenarios that have no tests yet.
check-order skips `hold` scenarios, which have no red by design. check-break runs at R only.
If every gate passes, each commit of the step gets the `Redline-Step: <change>/<step>` trailer
(once), the branch is pushed, the PR is opened with `gh`, and the step stops being open. Pushing and `gh` sit behind `GitHub`, which tests replace.
"""

import subprocess
from pathlib import Path

from redline.audit import check_audit
from redline.breaks import check_break, holds
from redline.lines import LIMIT, check_lines
from redline.links import check_links
from redline.order import check_order, git
from redline.premises import check_premises
from redline.start import TRAILER, Refused, open_step_file, read_steps


class GitHub:
    """Everything that goes over the network."""

    def __init__(self, repo: Path):
        self.repo = repo

    def run(self, *command: str) -> str:
        done = subprocess.run(command, cwd=self.repo, capture_output=True, text=True)
        if done.returncode:
            raise RuntimeError(f"{' '.join(command[:3])}: {done.stderr.strip()}")
        return done.stdout.strip()

    def push(self, branch: str) -> None:
        self.run("git", "push", "-u", "origin", branch)

    def create_pr(self, title: str, body: str) -> str:
        return self.run("gh", "pr", "create", "--title", title, "--body", body)


def gates(repo: Path, change: str, step: str) -> list[str]:
    failures = []
    count = check_lines(repo)
    if count.total > LIMIT:
        failures.append(f"check-lines: {count.total} changed lines, over the limit of {LIMIT}")
    if step == "S":
        failures += [f"check-premises: {bad}" for bad in check_premises(repo, change).bad]
        failures += [f"check-audit: {bad}" for bad in check_audit(repo, change).bad]
    else:
        failures += [f"check-links: {gap}" for gap in check_links(repo).gaps]
        held = set(holds(repo))  # a hold test has no red by design
        failures += [
            f"check-order: {r.scenario}: green {r.green[:7]} has no red commit among its ancestors"
            for r in check_order(repo)
            if r.status == "fail" and r.scenario not in held
        ]
    if step == "R":
        failures += [f"check-break: {sid}: {why}" for sid, why in check_break(repo, change).bad.items()]
    return failures


def stamp(repo: Path, base: str, name: str) -> None:
    """Give every commit since `base` the step's trailer, unless they all have it already."""
    log = git(repo, "log", f"{base}..HEAD", f"--format=%(trailers:key={TRAILER},valueonly,separator=|)")
    if all(name in line.split("|") for line in log.stdout.splitlines()):
        return
    amend = f"git -c trailer.ifexists=addIfDifferent commit -q --amend --no-edit --trailer '{TRAILER}: {name}'"
    done = git(repo, "rebase", "-q", "--exec", amend, base)
    if done.returncode:
        git(repo, "rebase", "--abort")
        raise RuntimeError(f"could not add the {TRAILER} trailer: {done.stderr.strip()}")


def pr(repo: Path, body: str = "") -> str:
    """Open the PR for the open step and return its URL."""
    state = open_step_file(repo)
    name = state.read_text().strip() if state.is_file() else ""
    if not name:
        raise Refused("no step is open; begin one with `redline start <change>/<step>`")
    change, _, step_name = name.partition("/")
    step = next((s for s in read_steps(repo, change) if s.name == step_name), None)
    if step is None:
        raise RuntimeError(f"no step {step_name} in redline/changes/{change}/steps.md")
    base = git(repo, "merge-base", "main", "HEAD").stdout.strip()
    if git(repo, "rev-parse", "HEAD").stdout.strip() == base:
        raise Refused("the branch has no commits of its own to put in a PR")
    if git(repo, "status", "--porcelain").stdout.strip():
        raise Refused("there are uncommitted changes; commit or stash them first")
    if failures := gates(repo, change, step_name):
        raise Refused("the local gates failed:\n" + "\n".join(failures))
    stamp(repo, base, name)
    github = GitHub(repo)
    github.push(git(repo, "branch", "--show-current").stdout.strip())
    url = github.create_pr(f"{name}: {step.goal}", f"{body}\n\n{TRAILER}: {name}\n".lstrip())
    state.unlink()
    return url
