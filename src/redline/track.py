"""check-track: a Green PR changes only its own track. See specs/, §5.

A G step's track is the `Track:` line under its heading in steps.md, read at the merge-base with
main (as the auditor saw it), not from the PR. Each file the step's diff adds, edits or deletes
must match one of its globs, unless it is under redline/, a test file, a support file or a
generated file (those globs read at the merge-base too). A file outside needs a `Redline-Track: <reason>` trailer and a maintainer's label
(approval.py). At critical every G step must have a track; below it, a track that is there is
checked.
"""

from pathlib import Path

from redline.approval import TRACK, Approvals, claims
from redline.config import load_config, rigor
from redline.lines import is_generated
from redline.order import git
from redline.runner import RUNNERS
from redline.start import parse_steps

TESTS = tuple(glob for runner in RUNNERS for glob in runner.test_files)


def check_track(repo: Path, change: str, step: str, approvals: Approvals) -> list[str]:
    fork = git(repo, "merge-base", "main", "HEAD").stdout.strip()
    shown = git(repo, "show", f"{fork}:redline/changes/{change}/steps.md")
    steps = parse_steps(shown.stdout) if shown.returncode == 0 else []
    globs = next((s.track for s in steps if s.name == step), None)
    if not globs:
        critical = rigor(repo, change) == "critical"
        return [f"check-track: {change}/{step} has no Track: line; at critical every G step names its track"] if critical else []
    config = load_config(repo, fork)  # as the track: a PR can't exempt its own files
    exempt = [*TESTS, *config.support, *config.generated]
    diff = git(repo, "diff", "--name-only", "--no-renames", fork, "HEAD")
    outside = [p for p in diff.stdout.splitlines()
               if not p.startswith("redline/") and not is_generated(p, exempt) and not is_generated(p, globs)]
    claimed = claims(repo, fork, "Redline-Track")
    failures = []
    for path in outside:
        what = f"check-track: {path} is outside {change}/{step}'s track ({', '.join(globs)})"
        if not claimed:
            failures.append(what)
        elif why := approvals.approve(TRACK, what):
            failures.append(why)
    return failures
