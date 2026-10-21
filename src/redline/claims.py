"""`redline claims <initiative>`: the claims main's history holds, for the process auditor. See docs/design.md §4, §7, §9.

The changes are every change any version of the plan on main's first-parent line listed (`listed`), so a
change taken out of the plan keeps its claims; those it no longer lists are named, with where they left.
The commits are main's non-merge commits whose `Redline-Step` names a step of one of those, or that
touch the initiative's directory or redline/config.yaml, oldest first. Each with a claim trailer
(approval.py) is printed with its merged PR and, per claim, its label, who applied it last and their
role at the merge, from the record `redline ci push` left in the CI note on the commit where it merged
(`record`). Without a note or a record it says so, and reads them now through the `GitHub` seam
(pr.py). It writes nothing and judges nothing.
"""

from pathlib import Path

import yaml

from redline.approval import DEPARTURE, OVERSIZED, RIGOR, TRACK
from redline.ledger import NOTES
from redline.order import git, merged_into
from redline.plan import ROOT, parse_plan
from redline.pr import GitHub
from redline.start import TRAILER

LABELS = {"Oversized": OVERSIZED, "Redline-Track": TRACK, "Redline-Departure": DEPARTURE, "Redline-Rigor": RIGOR}
CONFIG = "redline/config.yaml"


def commits(repo: Path, revs: str) -> list[tuple[str, str, list[tuple[str, str]]]]:
    """Each non-merge commit of `revs`, oldest first, with its subject and trailers."""
    log = git(repo, "log", revs, "--no-merges", "--reverse", "--format=%x1e%H%x1f%s%x1f%(trailers:only,unfold)")
    found = []
    for entry in log.stdout.split("\x1e")[1:]:
        sha, subject, block = entry.split("\x1f")
        found.append((sha, subject, [(key, value.strip()) for key, _, value in (line.partition(":") for line in block.splitlines())]))
    return found


def note(repo: Path, commit: str) -> dict | None:
    """The CI note on `commit`, or None when it has none."""
    shown = git(repo, "notes", f"--ref={NOTES}", "show", commit)
    if shown.returncode:
        return None
    data = yaml.safe_load(shown.stdout)
    return data if isinstance(data, dict) else {}


def record(repo: Path, rev: str, github) -> list[dict]:
    """Each claim merged at `rev` (rev^..rev), with its label on the merged PR, who applied it last and their role."""
    made = [(sha, key, value) for sha, _, trailers in commits(repo, f"{rev}^..{rev}") for key, value in trailers if key in LABELS]
    if not made:
        return []
    number = next(iter(github.pulls(made[0][0])), None)
    applied = github.labels(number) if number else {}
    entries = []
    for sha, key, value in made:
        who = applied.get(LABELS[key])
        entries.append({"commit": sha, "claim": f"{key}: {value}", "pr": number, "label": LABELS[key],
                        "by": who, "role": github.role(who) if who else None})
    return entries


def listed(repo: Path, name: str) -> tuple[list[str], dict[str, str], str | None]:
    """Every change a version of the plan on main's first-parent line listed, in the order each first appears;
    the commit where each the plan now doesn't list last left it; and the commit that deleted the plan, if it is gone."""
    path = f"{ROOT}/{name}/plan.md"
    versions = git(repo, "log", "--first-parent", "--reverse", "--format=%H", "main", "--", path).stdout.split()
    if not versions:
        raise RuntimeError(f"no plan {path} on main")
    changes, left, now, deleted = [], {}, [], None
    for sha in versions:
        shown = git(repo, "show", f"{sha}:{path}")
        before, now = now, [] if shown.returncode else [c for phase in parse_plan(name, shown.stdout).phases for c in phase.changes]
        deleted = sha if shown.returncode else None
        changes += [c for c in now if c not in changes]
        left |= {c: sha for c in before if c not in now}
    return changes, {c: sha for c, sha in left.items() if c not in now}, deleted


def at_merge(entry: dict, merged: str) -> str:
    where = f"(CI note on {merged[:7]})"
    if entry.get("pr") is None:
        return f"Label at the merge: no merged PR found {where}\n"
    if entry.get("by") is None:
        return f"Label at the merge: {entry.get('label')}: not on PR #{entry['pr']} {where}\n"
    return f"Label at the merge: {entry.get('label')}, applied by @{entry['by']}, {entry.get('role')} {where}\n"


def label(github, applied: dict[int, dict[str, str]], number: int | None, name: str) -> str:
    if number is None:
        return "Label now: no merged PR found for this commit\n"
    if number not in applied:
        applied[number] = github.labels(number)
    if (who := applied[number].get(name)) is None:
        return f"Label now: {name}: not on PR #{number}\n"
    return f"Label now: {name}, applied by @{who}, now {github.role(who)}\n"


def claims(repo: Path, name: str) -> str:
    changes, left, deleted = listed(repo, name)
    touching = set(git(repo, "log", "main", "--no-merges", "--full-history", "--format=%H",
                       "--", f"{ROOT}/{name}", CONFIG).stdout.split())
    line = git(repo, "rev-list", "--first-parent", "--reverse", "main").stdout.split()
    github, applied = GitHub(repo), {}
    count = made = 0
    said = ""
    for sha, subject, trailers in commits(repo, "main"):
        steps = [value for key, value in trailers if key == TRAILER]
        if sha not in touching and not any(s.partition("/")[0] in changes for s in steps):
            continue
        count += 1
        if not (claimed := [(key, value) for key, value in trailers if key in LABELS]):
            continue
        merged = merged_into(repo, sha, line, "main")
        noted = note(repo, merged)
        kept = {e.get("claim"): e for e in (noted or {}).get("claims") or [] if isinstance(e, dict) and e.get("commit") == sha}
        found = [kept.get(f"{key}: {value}") for key, value in claimed]
        prs = [e.get("pr") for e in found if e]
        number = prs[0] if prs else next(iter(github.pulls(sha)), None)
        said += f"\n## {sha[:7]} {', '.join(steps) or 'outside any step'}{f' (PR #{number})' if number else ''}: {subject}\n"
        for (key, value), entry in zip(claimed, found):
            said += f"{key}: {value}\n"
            if entry:
                said += at_merge(entry, merged)
                continue
            why = f"no CI note on {merged[:7]}" if noted is None else f"the CI note on {merged[:7]} has no record of it"
            said += f"Label at the merge: not recorded: {why}\n" + label(github, applied, number, LABELS[key])
        made += len(claimed)
    head = (f"# Claims: {name}\nFrom main: {made} claim{'' if made == 1 else 's'} on {count} "
            f"commit{'' if count == 1 else 's'}: the steps of {', '.join(changes)}, and every commit "
            f"that touches {ROOT}/{name}/ or {CONFIG}.\n")
    gone = {}
    for c in (c for c in changes if c in left):
        gone.setdefault(left[c], []).append(c)
    if gone:
        head += "Left the plan: " + "; ".join(f"{', '.join(cs)} in {sha[:7]}" for sha, cs in gone.items()) + ".\n"
    if deleted:
        head += f"The plan was deleted from main in {deleted[:7]}.\n"
    return head + (said or "\nNo claims.\n")
