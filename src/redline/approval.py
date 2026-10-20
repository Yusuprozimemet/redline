"""A person's approval: a label on the PR, applied by a maintainer. See docs/design.md, §7.

A trailer in the PR's own commits makes a claim: `Redline-Departure` lets a frozen test's lock
entry change, `Oversized` lets the PR pass 400 lines, `Redline-Track` lets a G step change files
outside its track, `Redline-Rigor` lets the config's default level or a plan's level change, a plan be deleted or a change
be taken out of one. In CI the claim needs its label, read
through the `GitHub` seam. Locally there is no PR yet, so the claim is noted as pending instead.
"""

from pathlib import Path

from redline.order import git

DEPARTURE = "redline:departure"
OVERSIZED = "redline:oversized"
TRACK = "redline:track"
RIGOR = "redline:rigor"
MAINTAINER = ("admin", "maintain")


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
        self.applied: dict[str, str] | None = None

    def approve(self, label: str, what: str) -> str | None:
        """Why `what` isn't approved by `label`, or None if it is (or can't be yet, locally)."""
        if self.github is None:
            self.pending.append(f"{what}: CI will need the `{label}` label from a maintainer")
            return None
        if self.number is None:
            return f"{what}: no PR number to read the `{label}` label from"
        if self.applied is None:
            self.applied = self.github.labels(self.number)
        who = self.applied.get(label)
        if who is None:
            return f"{what}: needs the `{label}` label from a maintainer"
        if self.github.role(who) not in MAINTAINER:
            return f"{what}: `{label}` was applied by @{who}, who isn't a maintainer"
        return None
