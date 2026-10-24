"""The contract lock, redline/contracts/lock.yaml: hashes of each change's frozen `hold` tests.

`redline lock <change>` writes the change's entry from the tests check-break counts.
At critical rigor an entry also hashes what the test reaches (reach.py).
`redline check-lock <change>` prints each difference from the code: a hash differs, a locked test
is missing, a hold test isn't locked, or a critical entry has no `reach`; a closed change asks for no test to be locked.
`redline lock` moves each scenario the change's deltas name out of every closed change's entry, keeping `reach`.
`check_frozen`, at every step, compares the whole lock by test with the lock at the merge-base: a test frozen
there whose hashes changed or that left the lock (and, with a base, the G steps, an entry of the change added since)
needs a `Redline-Departure: <test> approved-by @person: <reason>` trailer in base..HEAD naming the test and the
label of the person it names, a maintainer (approval.py). See specs/, §4, §5 and §7.
"""

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from redline.approval import DEPARTED, DEPARTURE, Approvals, claims
from redline.breaks import hold_tests
from redline.config import rigor
from redline.links import closed
from redline.order import git
from redline.reach import reach
from redline.runner import PYTEST, runner_for
from redline.specs import parse

LOCK = "redline/contracts/lock.yaml"


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


def frozen(lock: dict | None) -> dict[str, tuple[str, dict[str, str]]]:
    """test -> (a scenario it is locked for, its hashes), across every change's entry."""
    found: dict[str, tuple[str, dict[str, str]]] = {}
    for change in sorted(lock or {}):
        for (sid, test), hashes in entries(lock, change).items():
            found.setdefault(test, (sid, {}))[1].update(hashes)
    return found


def named(repo: Path, change: str) -> set[str]:
    """Each scenario ID the change's deltas name, under ADDED, MODIFIED or REMOVED."""
    ids: set[str] = set()
    for delta in (repo / "redline/changes" / change / "specs").glob("**/delta.md"):
        scenarios, removed = parse(delta.read_text(encoding="utf-8"))
        ids |= {s[0] for s in scenarios} | set(removed)
    return ids


def write_lock(repo: Path, change: str) -> int:
    lock = read_lock(repo)
    critical = rigor(repo, change) == "critical"
    kept = {test for test, (_, hashes) in frozen(lock).items() if "reach" in hashes}  # a move never checks less
    names = named(repo, change)
    for other in sorted(closed(repo) & set(lock) - {change}):  # the scenario's entry is the change's that declares it last
        lock[other] = {sid: tests for sid, tests in (lock[other] or {}).items() if sid not in names}
        if not lock[other]:
            del lock[other]
    lock[change] = {
        sid: {test: {"test": digest, "reach": reach(repo, test)} if (critical or test in kept) and runner_for(test) is PYTEST else digest
              for test, digest in tests.items()}
        for sid, tests in hold_tests(repo, change).items() if tests
    }
    (repo / LOCK).parent.mkdir(parents=True, exist_ok=True)
    (repo / LOCK).write_text(yaml.safe_dump(lock), encoding="utf-8")
    return len(entries(lock, change))


def check_lock(repo: Path, change: str, base: str | None = None, approvals: Approvals | None = None) -> LockReport:
    approvals = approvals or Approvals()
    critical = rigor(repo, change) == "critical"
    done = change in closed(repo)  # its delta declares nothing, so it asks for no test to be locked
    locked = entries(read_lock(repo), change)
    now = entries({change: hold_tests(repo, change)}, change)
    report = LockReport(len(locked))
    for sid, test in sorted(set(locked) | set(now)):
        if (sid, test) not in locked:
            if not done:
                report.bad.append(f"{sid}: {test} isn't in the lock")
        elif (sid, test) not in now:
            report.bad.append(f"{sid}: {test} is locked but missing")
        elif locked[sid, test]["test"] != now[sid, test]["test"]:
            report.bad.append(f"{sid}: {test} changed since it was locked")
        elif "reach" in locked[sid, test]:  # checked whatever the level, so lowering it checks no less
            if locked[sid, test]["reach"] != reach(repo, test):
                report.bad.append(f"{sid}: {test}: a fixture, helper, mark or setting it reaches changed since it was locked")
        elif critical:
            why = "the change is critical, so re-run `redline lock`" if runner_for(test) is PYTEST else "a Jest test has no reach yet (O-RUN3)"
            report.bad.append(f"{sid}: {test} is locked without what it reaches; {why}")
    if base:
        report.bad += check_frozen(repo, base, approvals, change)
    return report


def check_frozen(repo: Path, base: str, approvals: Approvals | None = None, own: str | None = None) -> list[str]:
    """Each test frozen at the merge-base with `base`, in any change's entry, whose hashes changed or that left
    the lock, and each entry of `own` added since: each needs an approved departure naming its test."""
    approvals = approvals or Approvals()
    fork = git(repo, "merge-base", base, "HEAD")
    if fork.returncode:
        raise RuntimeError(f"no merge-base with {base}: {fork.stderr.strip()}")
    shown = git(repo, "show", f"{fork.stdout.strip()}:{LOCK}")
    then, lock = (yaml.safe_load(shown.stdout) if shown.returncode == 0 else None), read_lock(repo)
    before, now = frozen(then), frozen(lock)
    moved = [(sid, test) for test, (sid, old) in sorted(before.items())  # a reach added checks further, changing nothing
             if not (test in now and all(now[test][1].get(kind) == digest for kind, digest in old.items()))]
    if own:  # at G: tests are locked at R
        had = entries(then, own)
        moved += [key for key in sorted(entries(lock, own)) if key not in had]
    claimed: dict[str, list[str]] = {}  # test -> each person a departure of it names
    for line in claims(repo, fork.stdout.strip(), "Redline-Departure"):
        if found := DEPARTED.match(line):
            claimed.setdefault(found[1], []).append(found[2])
    bad = []
    for sid, test in dict.fromkeys(moved):
        what = f"{sid}: {test}: its lock entry changed since {base}"
        if test not in claimed:
            bad.append(f"{what}, with no approved departure")
        else:
            bad += [why for who in claimed[test] if (why := approvals.approve(DEPARTURE, what, who))]
    return bad
