"""`redline ci`: what the GitHub Action runs (.github/workflows/redline.yml).

On a pull request, the step comes from the `Redline-Step` trailers of the PR's commits (base..HEAD),
which must name exactly one step. Then the step's gates, the test suite and check-ledger against
the base run, and every failure is reported. On a push to main, the suite runs and its result is
recorded as a git note on the merged commit under refs/notes/redline-ci, which is then pushed.
Pushing sits behind `Remote`, which tests replace.
"""

import os
import subprocess
import sys
from pathlib import Path

from redline.ledger import NOTES, check_ledger
from redline.order import git
from redline.pr import gates
from redline.start import TRAILER, Refused


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
    log = git(repo, "log", f"{base}..HEAD", f"--format=%(trailers:key={TRAILER},valueonly,separator=|)")
    if log.returncode:
        raise RuntimeError(log.stderr.strip())
    steps = sorted({s.strip() for line in log.stdout.splitlines() for s in line.split("|") if s.strip()})
    if not steps:
        raise Refused(f"no commit in {base}..HEAD carries a {TRAILER} trailer")
    if len(steps) > 1:
        raise Refused(f"more than one step in {base}..HEAD: {', '.join(steps)}")
    if "/" not in steps[0]:
        raise Refused(f"{TRAILER}: {steps[0]} is not <change>/<step>")
    return steps[0]


def ci_pr(repo: Path, base: str) -> tuple[str, list[str]]:
    name = pr_step(repo, base)
    change, _, step = name.partition("/")
    failures = gates(repo, change, step) + suite(repo)
    failures += [f"check-ledger: {p}" for p in check_ledger(repo, change, base)]
    return name, failures


def ci_push(repo: Path, run_url: str, rev: str = "HEAD") -> list[str]:
    failures = suite(repo)
    message = f"result: {'fail' if failures else 'pass'}\nrun: {run_url}\n"
    noted = git(repo, "-c", "user.name=redline-ci", "-c", "user.email=redline-ci@users.noreply.github.com",
                "notes", f"--ref={NOTES}", "add", "-f", "-m", message, rev)
    if noted.returncode:
        raise RuntimeError(f"could not write the CI note: {noted.stderr.strip()}")
    Remote(repo).push_notes()
    return failures
