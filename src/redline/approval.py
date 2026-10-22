"""A person's approval: a label on the PR, applied by a maintainer. See docs/design.md, §7.

A trailer in the PR's own commits makes a claim: `Redline-Departure` lets a frozen test's lock
entry change, `Oversized` lets the PR pass 400 lines, `Redline-Track` lets a G step change files
outside its track, `Redline-Rigor` lets the config's default level or a plan's level change, a plan be deleted or a change
be taken out of one, and `Redline-Manual` lets a `manual` scenario close at the C step with a person's check
(close.py). One label covers every claim of its kind. In CI the claim needs its label, read
through the `GitHub` seam, applied after the PR's head was last pushed: a label isn't tied to a commit,
so one applied before a push would cover what the push added. Locally there is no PR yet, so the claim
is noted as pending instead.
"""

from datetime import datetime
from pathlib import Path

from redline.order import git

DEPARTURE = "redline:departure"
OVERSIZED = "redline:oversized"
TRACK = "redline:track"
RIGOR = "redline:rigor"
MANUAL = "redline:manual"
MAINTAINER = ("admin", "maintain")


def moment(at: str) -> datetime:
    """One of GitHub's ISO 8601 times, so two compare as instants, not as text."""
    return datetime.fromisoformat(at)


def claims(repo: Path, base: str, key: str) -> list[str]:
    """The values of every `key` trailer in base..HEAD."""
    log = git(repo, "log", f"{base}..HEAD", f"--format=%(trailers:key={key},valueonly)")
    return [line.strip() for line in log.stdout.splitlines() if line.strip()]


class Approvals:
    """The PR's labels, read once and only when a claim needs one. With no `github`, a local run."""

    def __init__(self, github=None, number: int | None = None):
        self.github = github
        self.number = number
        self.pending: list[str] = []
        self.applied: dict[str, tuple[str, str]] | None = None
        self.head: tuple[str, str] | None = None

    def approve(self, label: str, what: str) -> str | None:
        """Why `what` isn't approved by `label`, or None if it is (or can't be yet, locally)."""
        if self.github is None:
            self.pending.append(f"{what}: CI will need the `{label}` label from a maintainer")
            return None
        if self.number is None:
            return f"{what}: no PR number to read the `{label}` label from"
        if self.applied is None:
            self.applied, self.head = self.github.labels(self.number), self.github.pushed(self.number)
        if label not in self.applied:
            return f"{what}: needs the `{label}` label from a maintainer"
        who, at = self.applied[label]
        if self.github.role(who) not in MAINTAINER:
            return f"{what}: `{label}` was applied by @{who}, who isn't a maintainer"
        if self.head is None:
            return f"{what}: `{label}` approves nothing: no push of the PR's head was found to check it against"
        sha, pushed = self.head
        if moment(at) <= moment(pushed):  # a label covers only the head it was applied after (O-APPR1)
            return f"{what}: `{label}` was applied at {at}, before {sha[:7]} was pushed at {pushed}; apply it again"
        return None
