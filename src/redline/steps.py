"""`redline check-steps <change>`: the form of a change's steps.md, against its own deltas. See §4.

It fails on an open item that isn't `- <ID> [<step>]: <text>`, an ID given twice, an owner that
isn't one of the file's steps, or an item outside `## Open items`; on steps that aren't S, then R
if there is one, then G1…Gn, then C, or a `## ` heading that is neither a step nor `## Open
items`; on a step named twice; on an `Owns:` ID no delta of the change declares; and on a `new`
scenario no G step owns. It reads the tree, and the deltas even once the change is closed.
`since` compares the file with the merge-base: an open item dropped, an item given to a merged step, a
merged step or the PR's own removed (O-STEPS2).
`pr` and `redline ci pr` run it on the step's change and on each change whose steps.md or deltas
the PR changes (`edited`).
"""

import re
from pathlib import Path

from redline.close import tags
from redline.order import git, shown
from redline.start import ITEM, merged_steps, scan

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


def items(text: str) -> dict[str, tuple[int, str, str, str]]:
    """Each open item's ID: its line number, its line, its owner and its text."""
    return {item[1]: (n, line, item[2], item[3]) for n, line in enumerate(text.splitlines(), 1) if (item := ITEM.match(line))}


def arrived(repo: Path, change: str, fork: str, base: str) -> set[str]:
    """The text of each item another change the PR edits has gained since `fork`: where an item may move."""
    texts = set()
    for other in edited(repo, base) - {change}:
        path = f"redline/changes/{other}/steps.md"
        then = {text for *_, text in items(shown(repo, path, fork) or "").values()}
        texts |= {text for *_, text in items(shown(repo, path) or "").values()} - then
    return texts


def since(repo: Path, change: str, base: str = "main", own: str | None = None) -> list[str]:
    """What left the change's steps.md since the merge-base with `base`: an item dropped and not moved, an item
    given to a step merged on `base`, a merged step or the PR's `own` removed. See §4, across steps."""
    fork = git(repo, "merge-base", base, "HEAD").stdout.strip()
    path = f"redline/changes/{change}/steps.md"
    if (before := shown(repo, path, fork)) is None or (now := shown(repo, path)) is None:
        return []  # at S there is nothing to compare; a deleted steps.md fails check_steps
    merged = {name.partition("/")[2] for name in merged_steps(repo, base) if name.startswith(f"{change}/")}
    old, new, moved = items(before), items(now), arrived(repo, change, fork, base)
    bad = [f"steps.md: open item {sid} dropped since the merge-base: {line}"
           for sid, (_, line, _, text) in old.items() if sid not in new and text not in moved]
    bad += [f"steps.md:{n}: open item {sid} given to {owner}, which is merged on {base}"
            for sid, (n, _, owner, _) in new.items() if owner in merged and (sid not in old or old[sid][2] != owner)]
    kept = {step.name for step in scan(now)[0]}
    for step in (step.name for step in scan(before)[0] if step.name not in kept):
        if step in merged:
            bad.append(f"steps.md: step {step} removed since the merge-base, and it is merged on {base}")
        elif step == own:
            bad.append(f"steps.md: step {step} removed since the merge-base, and it is this PR's step")
    return bad
