"""`redline check-close`: the C step, checked against the evidence on main. See §5.

check-ledger only says the committed ledger matches main's history. This rebuilds it and asks
whether that history is enough to close: each `new` scenario a red and a green, each `hold`
scenario a break, each with `result: pass`. A scenario is `new`, `hold` or `manual` by its tag in the delta;
a `manual` one refuses until a person's check of it can be recorded (O-SPEC3).
`unverified` refuses too, with a line saying the PR is waiting for CI's note, not wrong.
"""

import re
from pathlib import Path

from redline.ledger import rebuild

TAG = re.compile(r"^#### Scenario (\S+) \[(new|hold|manual)\]:")


def tags(repo: Path, change: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for delta in sorted((repo / "redline/changes" / change / "specs").glob("**/delta.md")):
        for line in delta.read_text(encoding="utf-8").splitlines():
            if tag := TAG.match(line):
                found.setdefault(tag[1], tag[2])
    return found


def check_close(repo: Path, change: str, main: str = "main") -> list[str]:
    scenarios = rebuild(repo, change, main)["scenarios"]
    kinds = tags(repo, change)
    bad, waiting = [], False
    for sid, entry in scenarios.items():
        if kinds.get(sid) == "manual":
            bad.append(f"{sid}: manual, and a person's check of it can't be recorded yet (O-SPEC3)")
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
