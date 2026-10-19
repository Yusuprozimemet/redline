"""The contract lock, redline/contracts/lock.yaml: hashes of each change's frozen `hold` tests.

`redline lock <change>` writes the change's entry from the tests check-break counts.
At critical rigor an entry also hashes what the test reaches (reach.py).
`redline check-lock <change>` prints each difference from the code: a hash differs, a locked test
is missing, a hold test isn't locked, or a critical entry has no `reach`. With a base (the G steps), an entry that changed since
the merge-base is a difference too, unless a `Redline-Departure: <test> approved-by @person:
<reason>` trailer in base..HEAD names the test and a maintainer's label approves it (approval.py).
See docs/design.md, §4, §5 and §7.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from redline.approval import DEPARTURE, Approvals, claims
from redline.breaks import hold_tests
from redline.config import rigor
from redline.order import git
from redline.reach import reach

LOCK = "redline/contracts/lock.yaml"
CLAIM = re.compile(r"^(\S+) approved-by @\S+: \S")


@dataclass
class LockReport:
    locked: int = 0
    bad: list[str] = field(default_factory=list)


def entries(lock: dict | None, change: str) -> dict[tuple[str, str], dict[str, str]]:
    """(scenario, test) -> its hashes in one change's entry: {test, reach}, or {test} if plain."""
    tests = ((lock or {}).get(change) or {}).items()
    return {(sid, t): v if isinstance(v, dict) else {"test": v} for sid, found in tests for t, v in found.items()}


def read_lock(repo: Path) -> dict:
    path = repo / LOCK
    return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}) if path.is_file() else {}


def write_lock(repo: Path, change: str) -> int:
    lock = read_lock(repo)
    critical = rigor(repo, change) == "critical"
    lock[change] = {
        sid: {test: {"test": digest, "reach": reach(repo, test)} if critical else digest for test, digest in tests.items()}
        for sid, tests in hold_tests(repo, change).items() if tests
    }
    (repo / LOCK).parent.mkdir(parents=True, exist_ok=True)
    (repo / LOCK).write_text(yaml.safe_dump(lock), encoding="utf-8")
    return len(entries(lock, change))


def check_lock(repo: Path, change: str, base: str | None = None, approvals: Approvals | None = None) -> LockReport:
    approvals = approvals or Approvals()
    critical = rigor(repo, change) == "critical"
    locked = entries(read_lock(repo), change)
    now = entries({change: hold_tests(repo, change)}, change)
    report = LockReport(len(locked))
    for sid, test in sorted(set(locked) | set(now)):
        if (sid, test) not in locked:
            report.bad.append(f"{sid}: {test} isn't in the lock")
        elif (sid, test) not in now:
            report.bad.append(f"{sid}: {test} is locked but missing")
        elif locked[sid, test]["test"] != now[sid, test]["test"]:
            report.bad.append(f"{sid}: {test} changed since it was locked")
        elif "reach" in locked[sid, test]:  # checked whatever the level, so lowering it checks no less
            if locked[sid, test]["reach"] != reach(repo, test):
                report.bad.append(f"{sid}: {test}: a fixture, helper, mark or setting it reaches changed since it was locked")
        elif critical:
            report.bad.append(f"{sid}: {test} is locked without what it reaches; the change is critical, so re-run `redline lock`")
    if base:
        fork = git(repo, "merge-base", base, "HEAD")
        if fork.returncode:
            raise RuntimeError(f"no merge-base with {base}: {fork.stderr.strip()}")
        shown = git(repo, "show", f"{fork.stdout.strip()}:{LOCK}")
        before = entries(yaml.safe_load(shown.stdout) if shown.returncode == 0 else None, change)
        claimed = {m[1] for line in claims(repo, fork.stdout.strip(), "Redline-Departure") if (m := CLAIM.match(line))}
        for sid, test in sorted(set(before) | set(locked)):
            old, new = before.get((sid, test)), locked.get((sid, test))
            if old and new and all(new.get(kind) == digest for kind, digest in old.items()):
                continue  # a reach added where the merge-base had none checks further, changing nothing
            if test not in claimed:
                report.bad.append(f"{sid}: {test}: its lock entry changed since {base}, with no approved departure")
            elif why := approvals.approve(DEPARTURE, f"{sid}: {test}: its lock entry changed since {base}"):
                report.bad.append(why)
    return report
