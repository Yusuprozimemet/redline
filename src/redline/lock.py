"""The contract lock, redline/contracts/lock.yaml: hashes of each change's frozen `hold` tests.

`redline lock <change>` writes the change's entry from the tests check-break counts.
`redline check-lock <change>` prints each difference from the code: a hash differs, a locked test
is missing, or a hold test isn't locked. With a base (the G steps), an entry that changed since
the merge-base is a difference too, unless a `Redline-Departure: <test> approved-by @person:
<reason>` trailer in base..HEAD names the test. See docs/design.md, §4 and §5.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from redline.breaks import hold_tests
from redline.order import git

LOCK = "redline/contracts/lock.yaml"
DEPARTURE = re.compile(r"^(\S+) approved-by @\S+: \S")


@dataclass
class LockReport:
    locked: int = 0
    bad: list[str] = field(default_factory=list)


def entries(lock: dict | None, change: str) -> dict[tuple[str, str], str]:
    """(scenario, test) -> hash for one change's entry in a lock."""
    return {(sid, test): digest for sid, tests in ((lock or {}).get(change) or {}).items() for test, digest in tests.items()}


def read_lock(repo: Path) -> dict:
    path = repo / LOCK
    return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}) if path.is_file() else {}


def write_lock(repo: Path, change: str) -> int:
    lock = read_lock(repo)
    lock[change] = {sid: tests for sid, tests in hold_tests(repo, change).items() if tests}
    (repo / LOCK).parent.mkdir(parents=True, exist_ok=True)
    (repo / LOCK).write_text(yaml.safe_dump(lock), encoding="utf-8")
    return len(entries(lock, change))


def check_lock(repo: Path, change: str, base: str | None = None) -> LockReport:
    locked = entries(read_lock(repo), change)
    now = entries({change: hold_tests(repo, change)}, change)
    report = LockReport(len(locked))
    for sid, test in sorted(set(locked) | set(now)):
        if (sid, test) not in locked:
            report.bad.append(f"{sid}: {test} isn't in the lock")
        elif (sid, test) not in now:
            report.bad.append(f"{sid}: {test} is locked but missing")
        elif locked[sid, test] != now[sid, test]:
            report.bad.append(f"{sid}: {test} changed since it was locked")
    if base:
        fork = git(repo, "merge-base", base, "HEAD")
        if fork.returncode:
            raise RuntimeError(f"no merge-base with {base}: {fork.stderr.strip()}")
        shown = git(repo, "show", f"{fork.stdout.strip()}:{LOCK}")
        before = entries(yaml.safe_load(shown.stdout) if shown.returncode == 0 else None, change)
        log = git(repo, "log", f"{fork.stdout.strip()}..HEAD", "--format=%(trailers:key=Redline-Departure,valueonly)")
        approved = {m[1] for line in log.stdout.splitlines() if (m := DEPARTURE.match(line.strip()))}
        for sid, test in sorted(set(before) | set(locked)):
            if before.get((sid, test)) != locked.get((sid, test)) and test not in approved:
                report.bad.append(f"{sid}: {test}: its lock entry changed since {base}, with no approved departure")
    return report
