"""`redline ci`: what the GitHub Action runs (.github/workflows/redline.yml).

On a pull request, the step comes from the `Redline-Step` trailers of the PR's commits (base..HEAD),
which must name at most one step. Then the step's gates, the test suite and check-ledger against
the base run, and every failure is reported. A PR with no trailer is outside any step: it may not
touch a change, the lock or the specs, and gets check-lines, the rigor claim, check-plan, check-lock
on every locked change and the suite. A departure or an Oversized trailer needs its label
on the PR (`--pr <number>`), read through `GitHub`. On a push to main, the suite runs and its result is
recorded as a git note on the merged commit under refs/notes/redline-ci, which is then pushed.
When the push merged an R step, check-break runs too, and the note gets each `hold` scenario's
result under `break:`; a failed break fails the run.
Pushing sits behind `Remote`, which tests replace.
"""

import os
import subprocess
import sys
from pathlib import Path

import yaml

from redline.breaks import check_break
from redline.ledger import NOTES, check_ledger
from redline.lock import check_lock, read_lock
from redline.order import git
from redline.approval import Approvals
from redline.plan import check_plan
from redline.planaudit import check_plan_audits
from redline.pr import GitHub, gates, rigor_claim, size
from redline.start import TRAILER, Refused

STEPS_ONLY = ("redline/changes/", "redline/contracts/", "redline/specs/")  # written only by a step's gates


class Remote:
    """Everything that goes over the network."""

    def __init__(self, repo: Path):
        self.repo = repo

    def push_notes(self) -> None:
        done = git(self.repo, "push", "origin", f"refs/notes/{NOTES}")
        if done.returncode:
            raise RuntimeError(f"git push refs/notes/{NOTES}: {done.stderr.strip()}")


def suite(repo: Path) -> list[str]:
    """Run the repository's tests; a failure is the one line that says so."""
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    done = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        cwd=repo, capture_output=True, text=True, env=env,
    )
    if done.returncode == 0:
        return []
    last = next((line for line in reversed(done.stdout.splitlines()) if line.strip()), "")
    return [f"suite: the test suite failed (pytest exit {done.returncode}): {last.strip('= ')}"]


def pr_step(repo: Path, base: str) -> str:
    """The one step base..HEAD's trailers name, or "" when no commit carries one."""
    log = git(repo, "log", f"{base}..HEAD", f"--format=%(trailers:key={TRAILER},valueonly,separator=|)")
    if log.returncode:
        raise RuntimeError(log.stderr.strip())
    steps = sorted({s.strip() for line in log.stdout.splitlines() for s in line.split("|") if s.strip()})
    if not steps:
        return ""
    if len(steps) > 1:
        raise Refused(f"more than one step in {base}..HEAD: {', '.join(steps)}")
    if "/" not in steps[0]:
        raise Refused(f"{TRAILER}: {steps[0]} is not <change>/<step>")
    return steps[0]


def outside(repo: Path, base: str, approvals: Approvals) -> list[str]:
    """A PR outside any step: refused if it touches a step's files, else the gates for any PR."""
    fork = git(repo, "merge-base", base, "HEAD")
    if fork.returncode:
        raise RuntimeError(f"no merge-base with {base}: {fork.stderr.strip()}")
    diff = git(repo, "diff", "--name-only", "--no-renames", fork.stdout.strip(), "HEAD")
    if touched := [p for p in diff.stdout.splitlines() if p.startswith(STEPS_ONLY)]:
        raise Refused(f"outside any step a PR can't touch a change, the lock or the specs: {', '.join(touched)}")
    failures = size(repo, approvals) + rigor_claim(repo, approvals)
    failures += [f"check-plan: {bad}" for bad in check_plan(repo).bad + check_plan_audits(repo)]
    for change in sorted(read_lock(repo)):  # no Redline-Step, so no departure: the lock can't change here
        failures += [f"check-lock: {change}: {bad}" for bad in check_lock(repo, change).bad]
    return failures + suite(repo)


def ci_pr(repo: Path, base: str, number: int | None = None) -> tuple[str, list[str]]:
    name = pr_step(repo, base)
    approvals = Approvals(GitHub(repo), number)
    if not name:
        return "", outside(repo, base, approvals)
    change, _, step = name.partition("/")
    failures = gates(repo, change, step, approvals) + suite(repo)
    failures += [f"check-ledger: {p}" for p in check_ledger(repo, change, base)]
    return name, failures


def ci_push(repo: Path, run_url: str, rev: str = "HEAD") -> list[str]:
    failures = suite(repo)
    message = f"result: {'fail' if failures else 'pass'}\nrun: {run_url}\n"
    change, _, step = pr_step(repo, f"{rev}^").partition("/")  # "" when no step merged here
    if step == "R":
        report = check_break(repo, change)
        failures += [f"check-break: {sid}: {why}" for sid, why in report.bad.items()]
        failures += [f"check-break: {sid}: not mutated: {report.skipped}" for sid in report.results if report.skipped]
        broken = {sid: "fail" if why or report.skipped else "pass" for sid, why in report.results.items()}
        message += yaml.safe_dump({"break": broken}, sort_keys=False) if broken else ""
    noted = git(repo, "-c", "user.name=redline-ci", "-c", "user.email=redline-ci@users.noreply.github.com",
                "notes", f"--ref={NOTES}", "add", "-f", "-m", message, rev)
    if noted.returncode:
        raise RuntimeError(f"could not write the CI note: {noted.stderr.strip()}")
    Remote(repo).push_notes()
    return failures
