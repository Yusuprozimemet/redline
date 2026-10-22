"""`redline check-close`: the C step, checked against the evidence on main. See §5.

check-ledger only says the committed ledger matches main's history. This rebuilds it and asks
whether that history is enough to close: each `new` scenario a red and a green, each `hold`
scenario a break, each with `result: pass`. A scenario is `new`, `hold` or `manual` by its tag in the delta;
a `manual` one needs a person's check instead: a `Redline-Manual: <ID> checked-by @person: <what was seen>`
trailer in the C PR's own commits (base..HEAD) and, in CI, a maintainer's label (approval.py). A trailer
that isn't in that form, or names no manual scenario of the change, fails, and so does one in any other
PR (`misplaced`). `unverified` refuses too, with a line saying the PR is waiting for CI's note, not wrong.
"""

import re
from pathlib import Path

from redline.approval import MANUAL, Approvals, claims
from redline.ledger import rebuild

TAG = re.compile(r"^#### Scenario (\S+) \[(new|hold|manual)\]:")
KEY = "Redline-Manual"
CHECK = re.compile(r"^(\S+) checked-by @(\S+): \S")


def misplaced(repo: Path, base: str) -> list[str]:
    """Each manual check in base..HEAD, outside a C step, where no gate reads it."""
    return [f"manual: {KEY}: {value}: a person's check counts at the C step only" for value in claims(repo, base, KEY)]


def tags(repo: Path, change: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for delta in sorted((repo / "redline/changes" / change / "specs").glob("**/delta.md")):
        for line in delta.read_text(encoding="utf-8").splitlines():
            if tag := TAG.match(line):
                found.setdefault(tag[1], tag[2])
    return found


def check_close(repo: Path, change: str, main: str = "main", approvals: Approvals | None = None,
                base: str = "main") -> list[str]:
    approvals = approvals or Approvals()
    scenarios = rebuild(repo, change, main)["scenarios"]
    kinds = tags(repo, change)
    bad, waiting, checked = [], False, {}
    for value in claims(repo, base, KEY):
        if not (check := CHECK.match(value)):
            bad.append(f"{KEY}: {value}: allows nothing: it needs `<ID> checked-by @person: <what was seen>`")
        elif kinds.get(check[1]) != "manual":
            bad.append(f"{KEY}: {value}: {check[1]} is no manual scenario of {change}")
        else:
            checked.setdefault(check[1], []).append(check[2])
    for sid, entry in scenarios.items():
        if kinds.get(sid) == "manual":
            if sid not in checked:
                bad.append(f"{sid}: manual, with no person's check in this PR: add "
                           f"`{KEY}: {sid} checked-by @person: <what was seen>` to one of its commits")
            bad += [why for who in checked.get(sid, []) if (why := approvals.approve(MANUAL, f"{sid}: manual, checked by @{who}"))]
            continue
        for kind in ("break",) if kinds.get(sid) == "hold" else ("red", "green"):
            if (evidence := entry[kind]) is None:
                bad.append(f"{sid}: no {kind} on main")
            elif evidence["result"] == "unverified":
                waiting = True
                bad.append(f"{sid}: {kind} is unverified: no CI note on {evidence['merged'][:7]} yet")
            elif evidence["result"] != "pass":
                bad.append(f"{sid}: {kind} failed: the CI note on {evidence['merged'][:7]} says {evidence['result']}")
    if waiting:
        bad.append("waiting, not wrong: once CI's push run notes those commits, fetch the notes "
                   "(git fetch origin 'refs/notes/*:refs/notes/*'), "
                   f"run redline ledger {change}, commit and push; nothing else needs to change")
    return bad
