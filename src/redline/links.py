"""Scenario-to-test linking, both ways.

Every scenario declared in a living spec or a change delta needs a test with a matching spec
marker, and every spec marker must name a declared scenario. An ID declared twice in specs/, or
in more than one change, is a duplicate; a change may restate a living scenario (MODIFIED).
A closed change's delta doesn't count: its C step is merged on main, so specs/ holds what it said.
A `#### Scenario` line not in the form `HEADING` reads is a gap, not nothing (O-SPEC1).
A `[manual]` scenario has no test, a linked one is a gap, and its block says why in one `Manual:` line (O-SPEC2).
A change with only its S merged on main, or the gated step's own at S, has no tests yet, so no unlinked gaps (O-LINK1).
Tracked and untracked files count; ignored ones don't.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from redline.order import git
from redline.runner import RUNNERS, markers

SPEC_PATHS = [":(glob)redline/specs/**/spec.md", ":(glob)redline/changes/*/specs/**/delta.md"]
HEADING = re.compile(r"^#### Scenario (\S+) \[(new|hold|manual)\]:")
FORM = "not a scenario heading `#### Scenario <ID> [new|hold|manual]: <title>`"


def malformed(line: str) -> bool:
    """A `#### Scenario` line no gate would read as a scenario, so it would be none, silently (O-SPEC1)."""
    return line.startswith("#### Scenario") and not HEADING.match(line)


def unreasoned(lines: Iterable[tuple[int, str]]) -> list[tuple[int, str]]:
    """(line, why) for each `Manual:` line missing, empty, repeated or outside a manual scenario's block,
    from a file's numbered lines; a block runs from its heading to the next `#` line (O-SPEC2)."""
    bad: list[tuple[int, str]] = []
    block = None  # [ID, tag, heading line, Manual: lines]

    def end():
        if block and block[1] == "manual" and not block[3]:
            bad.append((block[2], f"manual scenario {block[0]} has no `Manual: <reason>` line"))

    for n, line in lines:
        if line.startswith("#"):
            end()
            block = [heading[1], heading[2], n, 0] if (heading := HEADING.match(line)) else None
        elif line.startswith("Manual:"):
            if block is None or block[1] != "manual":
                bad.append((n, "`Manual:` line outside a manual scenario"))
            elif block[3]:
                bad.append((n, f"manual scenario {block[0]} has a second `Manual:` line"))
            elif not line[len("Manual:"):].strip():
                bad.append((n, "`Manual:` line with no reason"))
            if block is not None:
                block[3] += 1
    end()
    return bad


@dataclass
class LinkReport:
    scenarios: int = 0
    manual: int = 0
    gaps: list[str] = field(default_factory=list)
    waiting: dict[str, int] = field(default_factory=dict)  # each change before its R step: its unlinked scenarios


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


def stepped(repo: Path, revs: str = "main") -> set[str]:
    """The steps the `Redline-Step` trailers of `revs` name."""
    log = git(repo, "log", revs, "--format=%(trailers:key=Redline-Step,valueonly)")
    return {step for line in log.stdout.splitlines() if (step := line.strip())}


def closed(repo: Path) -> set[str]:
    """The changes whose C step is merged on main: their deltas are a record, not declarations (§4)."""
    return {step[:-2] for step in stepped(repo) if step.endswith("/C")}


def current(repo: Path) -> str:
    """The step main..HEAD's trailers name, else the open step, else "": check-links on its own."""
    if len(named := stepped(repo, "main..HEAD")) == 1:
        return named.pop()
    from redline.start import open_step_file  # start imports premises, which imports this module
    opened = open_step_file(repo)
    return opened.read_text(encoding="utf-8").strip() if opened.is_file() else ""


def waiting(repo: Path, step: str) -> set[str]:
    """The changes with no tests yet by design (O-LINK1): those with only their S merged on main, unless `step`
    is theirs from R on, and the change of a `step` at S."""
    merged = stepped(repo)
    changes = {name.partition("/")[0] for name in merged}
    early = {c for c in changes if {n for n in merged if n.startswith(f"{c}/")} == {f"{c}/S"}}
    own, _, at = step.partition("/")
    return early | {own} if at == "S" else early - {own}


def declarations(repo: Path, pattern: str = r"^#### Scenario") -> list[tuple[str, int, str]]:
    """Each scenario heading line, or each `pattern` line, in the living specs and the deltas of changes not closed."""
    done = closed(repo)
    return [hit for hit in grep(repo, pattern, *SPEC_PATHS)
            if not (hit[0].startswith("redline/changes/") and hit[0].split("/")[2] in done)]


def check_links(repo: Path, step: str | None = None) -> LinkReport:
    """`step`: the step gated, `<change>/<step>`; None reads it as check-links on its own does (`current`)."""
    early = waiting(repo, current(repo) if step is None else step)
    declared: dict[str, list[tuple[str, int]]] = {}
    manual: set[str] = set()
    bad = []
    files: dict[str, list[tuple[int, str]]] = {}
    for path, line, text in declarations(repo, r"^(#|Manual:)"):
        files.setdefault(path, []).append((line, text))
        if heading := HEADING.match(text):
            declared.setdefault(heading[1], []).append((path, line))
            if heading[2] == "manual":
                manual.add(heading[1])
        elif malformed(text):
            bad.append(f"{FORM} ({path}:{line}): {text}")
    bad += [f"{why} ({path}:{n})" for path, lines in files.items() for n, why in unreasoned(lines)]
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

    report = LinkReport(len(declared), len(manual), unreadable + bad)
    for sid, places in sorted(declared.items()):
        living = [p for p in places if p[0].startswith("redline/specs/")]
        changes = {p.split("/")[2] for p, _ in places if p.startswith("redline/changes/")}
        if len(living) > 1 or len(changes) > 1 or len(places) - len(living) > len(changes):
            report.gaps.append(f"duplicate scenario {sid}: " + ", ".join(f"{p}:{n}" for p, n in places))
    for sid, places in sorted(declared.items()):
        if sid in manual:  # its evidence is a person's check, never a test's
            report.gaps += [f"manual scenario {sid} ({places[0][0]}:{places[0][1]}): a test links it ({path}:{line}); "
                            "tag it new or hold" for path, line in linked.get(sid, [])]
        elif sid not in linked:
            owners = {p.split("/")[2] if p.startswith("redline/changes/") else "" for p, _ in places}
            if len(owners) == 1 and (owner := owners.pop()) in early:  # its tests come at its R step
                report.waiting[owner] = report.waiting.get(owner, 0) + 1
                continue
            path, line = places[0]
            report.gaps.append(f"unlinked scenario {sid} ({path}:{line}): no test has a spec marker for it")
    for sid, places in sorted(linked.items()):
        if sid not in declared:
            for path, line in places:
                report.gaps.append(f"unknown scenario {sid} ({path}:{line}): no spec declares it")
    return report
