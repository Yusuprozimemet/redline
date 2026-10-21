"""The 400-line gate: insertions plus deletions between a base and HEAD.

Specs and tests count. Files matching a `generated` glob in redline/config.yaml, as it is at the
base, don't. A glob
without a slash matches the file name in any directory; one with a slash matches the whole path.
"""

from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath

from redline.config import load_config
from redline.order import git

LIMIT = 400


@dataclass
class LineCount:
    base: str
    total: int = 0
    excluded: list[str] = field(default_factory=list)


def is_generated(path: str, globs: list[str]) -> bool:
    name = PurePosixPath(path).name
    return any(fnmatchcase(path, g) or ("/" not in g and fnmatchcase(name, g)) for g in globs)


def check_lines(repo: Path, base: str | None = None) -> LineCount:
    if base is None:
        found = git(repo, "merge-base", "main", "HEAD")
        if found.returncode:
            raise RuntimeError(f"no merge-base with main: {found.stderr.strip()}")
        base = found.stdout.strip()
    diff = git(repo, "diff", "--numstat", "-z", "-M", base, "HEAD")
    if diff.returncode:
        raise RuntimeError(diff.stderr.strip())
    globs = load_config(repo, base).generated  # at the base, so a PR can't exempt its own files
    result = LineCount(base)
    # -z records: "added\tdeleted\tpath\0", or "added\tdeleted\t\0old\0new\0" for a rename.
    fields = iter(diff.stdout.split("\0"))
    for record in fields:
        if not record:
            continue
        added, deleted, path = record.split("\t", 2)
        if not path:
            next(fields)
            path = next(fields)
        if is_generated(path, globs):
            result.excluded.append(path)
        elif added != "-":  # binary files have no line count
            result.total += int(added) + int(deleted)
    return result
