"""`redline check-steps <change>`: the form of a change's steps.md, against its own deltas. See §4.

It fails on an open item that isn't `- <ID> [<step>]: <text>`, an ID given twice, an owner that
isn't one of the file's steps, or an item outside `## Open items`; on steps that aren't S, then R
if there is one, then G1…Gn, then C, or a `## ` heading that is neither a step nor `## Open
items`; on a step named twice; on an `Owns:` ID no delta of the change declares; and on a `new`
scenario no G step owns. It reads the tree, and the deltas even once the change is closed.
`pr` and `redline ci pr` run it on the step's change and on each change whose steps.md or deltas
the PR changes (`edited`).
"""

import re
from pathlib import Path

from redline.close import tags
from redline.order import git
from redline.start import scan

EDITED = re.compile(r"^redline/changes/([^/]+)/(?:steps\.md|specs/.+/delta\.md)$")


def in_order(names: list[str]) -> bool:
    middle = names[1:-1]
    if middle[:1] == ["R"]:
        middle = middle[1:]
    return len(names) >= 2 and names[0] == "S" and names[-1] == "C" and middle == [f"G{i}" for i in range(1, len(middle) + 1)]


def check_steps(repo: Path, change: str) -> list[str]:
    path = repo / "redline/changes" / change / "steps.md"
    if not path.is_file():
        return [f"no steps file redline/changes/{change}/steps.md"]
    steps, bad, _ = scan(path.read_text(encoding="utf-8"))
    if not in_order(names := [s.name for s in steps]):
        bad.append(f"steps.md: {', '.join(names) or 'no steps'} aren't S, R, G1…Gn, C in order")
    kinds = tags(repo, change)  # ADDED and MODIFIED; a REMOVED entry is no heading
    bad += [f"steps.md:{step.owned_at[sid]}: {step.name} owns {sid}, which no delta of the change declares"
            for step in steps for sid in step.owns if sid not in kinds]
    owned = {sid for step in steps if step.name.startswith("G") for sid in step.owns}
    return bad + [f"{sid} is new, but no G step owns it" for sid, kind in kinds.items() if kind == "new" and sid not in owned]


def edited(repo: Path, base: str = "main") -> set[str]:
    """The changes whose steps.md or deltas differ from the merge-base with `base`."""
    fork = git(repo, "merge-base", base, "HEAD").stdout.strip()
    diff = git(repo, "diff", "--name-only", "--no-renames", fork, "HEAD").stdout.splitlines()
    return {found[1] for path in diff if (found := EDITED.match(path))}
