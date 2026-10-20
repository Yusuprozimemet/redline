"""Scenario-to-test linking, both ways.

Every scenario declared in a living spec or a change delta needs a test with a matching spec
marker, and every spec marker must name a declared scenario. An ID declared twice in specs/, or
in more than one change, is a duplicate; a change may restate a living scenario (MODIFIED).
A closed change's delta doesn't count: its C step is merged on main, so specs/ holds what it said.
Tracked and untracked files count; ignored ones don't.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from redline.order import git
from redline.runner import RUNNERS

SPEC_PATHS = [":(glob)redline/specs/**/spec.md", ":(glob)redline/changes/*/specs/**/delta.md"]
HEADING = re.compile(r"^#### Scenario (\S+) \[(?:new|hold)\]:")


@dataclass
class LinkReport:
    scenarios: int = 0
    gaps: list[str] = field(default_factory=list)


def grep(repo: Path, pattern: str, *paths: str) -> list[tuple[str, int, str]]:
    """(path, line number, text) for each matching line in tracked and untracked files."""
    found = git(repo, "grep", "--untracked", "-n", "-E", pattern, "--", *paths)
    if found.returncode > 1:
        raise RuntimeError(found.stderr.strip())
    hits = []
    for record in found.stdout.splitlines():
        path, line, text = record.split(":", 2)
        hits.append((path, int(line), text))
    return sorted(hits)


def closed(repo: Path) -> set[str]:
    """The changes whose C step is merged on main: their deltas are a record, not declarations (§4)."""
    log = git(repo, "log", "main", "--format=%(trailers:key=Redline-Step,valueonly)")
    return {step[:-2] for line in log.stdout.splitlines() if (step := line.strip()).endswith("/C")}


def declarations(repo: Path) -> list[tuple[str, int, str]]:
    """Each scenario heading line in the living specs and the deltas of changes not closed."""
    done = closed(repo)
    return [hit for hit in grep(repo, r"^#### Scenario ", *SPEC_PATHS)
            if not (hit[0].startswith("redline/changes/") and hit[0].split("/")[2] in done)]


def check_links(repo: Path) -> LinkReport:
    declared: dict[str, list[tuple[str, int]]] = {}
    for path, line, text in declarations(repo):
        if heading := HEADING.match(text):
            declared.setdefault(heading[1], []).append((path, line))
    markers: dict[str, list[tuple[str, int]]] = {}
    for runner in RUNNERS:
        for path, line, text in grep(repo, runner.grep, *runner.paths):
            for sid in runner.ids.findall(text):
                markers.setdefault(sid, []).append((path, line))

    report = LinkReport(len(declared))
    for sid, places in sorted(declared.items()):
        living = [p for p in places if p[0].startswith("redline/specs/")]
        changes = {p.split("/")[2] for p, _ in places if p.startswith("redline/changes/")}
        if len(living) > 1 or len(changes) > 1 or len(places) - len(living) > len(changes):
            report.gaps.append(f"duplicate scenario {sid}: " + ", ".join(f"{p}:{n}" for p, n in places))
    for sid, places in sorted(declared.items()):
        if sid not in markers:
            path, line = places[0]
            report.gaps.append(f"unlinked scenario {sid} ({path}:{line}): no test has a spec marker for it")
    for sid, places in sorted(markers.items()):
        if sid not in declared:
            for path, line in places:
                report.gaps.append(f"unknown scenario {sid} ({path}:{line}): no spec declares it")
    return report
