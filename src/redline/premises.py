"""Premise citations: every premise in a change's delta points at code that is really there.

Premises are the `- ` lines under a `### Premises` heading in a delta. A citation is a
backquoted `path:line` or `path:first-last`, relative to the repository root, optionally followed
by a quoted symbol in brackets: `auth/session.py:42` (`create_session`). It resolves when the
file exists inside the repository, the lines are within it, and the symbol (if given) appears on
the cited lines. A premise with no citation is reported too.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from redline.links import closed

CITATION = re.compile(r"`([^`\s:]+):(\d+)(?:-(\d+))?`(?:\s*\(`([^`]+)`\))?")
PREMISE = re.compile(r"^- (\S+?):")


@dataclass
class PremiseReport:
    citations: int = 0
    bad: list[str] = field(default_factory=list)


def premise_lines(repo: Path, change: str | None = None) -> list[tuple[str, int, str]]:
    """(delta path, line number, text) for each premise, in one change or in every change not closed."""
    changes = repo / "redline/changes"
    if change is not None and not (changes / change).is_dir():
        raise RuntimeError(f"no change redline/changes/{change}")
    done = closed(repo) if change is None else set()
    found = []
    for path in sorted(changes.glob(f"{change or '*'}/specs/**/delta.md")):
        if path.relative_to(changes).parts[0] in done:
            continue
        inside = False
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.startswith("#"):
                inside = line == "### Premises"
            elif inside and line.startswith("- "):
                found.append((path.relative_to(repo).as_posix(), n, line))
    return found


def resolve(repo: Path, path: str, first: int, last: int, symbol: str | None) -> str | None:
    """Why the citation doesn't resolve, or None if it does."""
    target = (repo / path).resolve()
    if not target.is_relative_to(repo.resolve()) or not target.is_file():
        return "no such file"
    if first < 1:
        return "lines start at 1"
    if last < first:
        return "the range runs backwards"
    lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
    if last > len(lines):
        return f"line {last} is past the end of the file ({len(lines)} lines)"
    if symbol and not any(symbol in line for line in lines[first - 1:last]):
        where = f"line {first}" if first == last else f"lines {first}-{last}"
        return f"`{symbol}` is not on {where}"
    return None


def check_premises(repo: Path, change: str | None = None) -> PremiseReport:
    report = PremiseReport()
    for delta, n, text in premise_lines(repo, change):
        citations = CITATION.findall(text)
        if not citations:
            premise = PREMISE.match(text)
            report.bad.append(f"{delta}:{n}: {premise[1] if premise else text} cites no `file:line`")
        for path, first, last, symbol in citations:
            report.citations += 1
            cited = f"{path}:{first}" + (f"-{last}" if last else "")
            if reason := resolve(repo, path, int(first), int(last or first), symbol or None):
                report.bad.append(f"{delta}:{n}: {cited}: {reason}")
    return report
