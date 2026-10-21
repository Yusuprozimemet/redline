"""Scenario-to-test linking, both ways.

Every scenario declared in a living spec or a change delta needs a test with a matching spec
marker, and every spec marker must name a declared scenario. An ID declared twice in specs/, or
in more than one change, is a duplicate; a change may restate a living scenario (MODIFIED).
A closed change's delta doesn't count: its C step is merged on main, so specs/ holds what it said.
A `#### Scenario` line not in the form `HEADING` reads is a gap, not nothing (O-SPEC1).
Tracked and untracked files count; ignored ones don't.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from redline.order import git
from redline.runner import RUNNERS, markers

SPEC_PATHS = [":(glob)redline/specs/**/spec.md", ":(glob)redline/changes/*/specs/**/delta.md"]
HEADING = re.compile(r"^#### Scenario (\S+) \[(?:new|hold)\]:")
FORM = "not a scenario heading `#### Scenario <ID> [new|hold]: <title>`"


def malformed(line: str) -> bool:
    """A `#### Scenario` line no gate would read as a scenario, so it would be none, silently (O-SPEC1)."""
    return line.startswith("#### Scenario") and not HEADING.match(line)


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
    return [hit for hit in grep(repo, r"^#### Scenario", *SPEC_PATHS)
            if not (hit[0].startswith("redline/changes/") and hit[0].split("/")[2] in done)]


def check_links(repo: Path) -> LinkReport:
    declared: dict[str, list[tuple[str, int]]] = {}
    bad = []
    for path, line, text in declarations(repo):
        if heading := HEADING.match(text):
            declared.setdefault(heading[1], []).append((path, line))
        elif malformed(text):
            bad.append(f"{FORM} ({path}:{line}): {text}")
    linked: dict[str, list[tuple[str, int]]] = {}
    unreadable = []
    for runner in RUNNERS:
        for path in sorted({path for path, _, _ in grep(repo, runner.grep, *runner.paths)}):
            try:
                found = markers(runner, path, (repo / path).read_text(encoding="utf-8"))
            except RuntimeError as error:
                unreadable.append(f"unreadable test file {path}: {str(error).removeprefix(f'{path}: ')}")
                continue
            for mark in found:
                linked.setdefault(mark.sid, []).append((path, mark.line))

    report = LinkReport(len(declared), unreadable + bad)
    for sid, places in sorted(declared.items()):
        living = [p for p in places if p[0].startswith("redline/specs/")]
        changes = {p.split("/")[2] for p, _ in places if p.startswith("redline/changes/")}
        if len(living) > 1 or len(changes) > 1 or len(places) - len(living) > len(changes):
            report.gaps.append(f"duplicate scenario {sid}: " + ", ".join(f"{p}:{n}" for p, n in places))
    for sid, places in sorted(declared.items()):
        if sid not in linked:
            path, line = places[0]
            report.gaps.append(f"unlinked scenario {sid} ({path}:{line}): no test has a spec marker for it")
    for sid, places in sorted(linked.items()):
        if sid not in declared:
            for path, line in places:
                report.gaps.append(f"unknown scenario {sid} ({path}:{line}): no spec declares it")
    return report
