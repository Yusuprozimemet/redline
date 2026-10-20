"""`redline check-specs`: at the C step, the deltas reach the living specs and nothing else does. See §5.

A delta's `## ADDED`, `## MODIFIED` and `## REMOVED Requirements` sections say what C does to
`redline/specs/<domain>/spec.md` (§4). Each scenario of the living specs at the merge-base with
main is compared with the same scenario now: its text, heading to the next heading, and the
`### Requirement:` it sits under. A requirement's own prose isn't compared.
"""

import re
from pathlib import Path

from redline.order import git

SCENARIO = re.compile(r"^#### Scenario (\S+) \[(?:new|hold)\]:")
SECTION = re.compile(r"^## (ADDED|MODIFIED|REMOVED) Requirements\s*$")
REQUIREMENT = re.compile(r"^### Requirement: (.+?)\s*$")
REMOVAL = re.compile(r"^- ([^\s:]+): \S")

Scenario = tuple[str, str | None, str | None, str, int]  # ID, section, requirement, text, line


def parse(text: str) -> tuple[list[Scenario], list[str]]:
    """Each scenario heading, and the IDs of the `- <ID>: <reason>` lines directly under REMOVED."""
    scenarios: list[Scenario] = []
    removed: list[str] = []
    section = requirement = None
    direct = False
    lines = text.splitlines()
    for n, line in enumerate(lines):
        if not line.startswith("#"):
            if direct and section == "REMOVED" and (entry := REMOVAL.match(line)):
                removed.append(entry[1])
            continue
        direct = line.startswith("## ")
        if direct:
            section, requirement = (heading[1] if (heading := SECTION.match(line)) else None), None
        elif heading := REQUIREMENT.match(line):
            requirement = heading[1]
        elif heading := SCENARIO.match(line):
            end = next((i for i in range(n + 1, len(lines)) if lines[i].startswith("#")), len(lines))
            scenarios.append((heading[1], section, requirement, "\n".join(lines[n:end]).rstrip(), n + 1))
        elif line.startswith("### "):  # e.g. Premises
            requirement = None
    return scenarios, removed


def living(repo: Path, ref: str | None) -> dict[str, tuple[str, str | None, str]]:
    """Scenario ID -> (spec path, requirement, text) in redline/specs at `ref`, or in the tree."""
    if ref is None:
        files = {p.relative_to(repo).as_posix(): p.read_text(encoding="utf-8")
                 for p in sorted((repo / "redline/specs").glob("**/spec.md"))}
    else:
        listed = git(repo, "ls-tree", "-r", "--name-only", ref, "--", "redline/specs").stdout.split()
        files = {p: git(repo, "show", f"{ref}:{p}").stdout for p in sorted(listed) if p.endswith("/spec.md")}
    found: dict[str, tuple[str, str | None, str]] = {}
    for path, text in files.items():
        for sid, _, requirement, block, _ in parse(text)[0]:
            found.setdefault(sid, (path, requirement, block))
    return found


def check_specs(repo: Path, change: str, base: str = "main") -> tuple[list[str], dict[str, int]]:
    """Each way the living specs differ from what the change's deltas say, and a count per section."""
    fork = git(repo, "merge-base", base, "HEAD")
    if fork.returncode:
        raise RuntimeError(f"no merge-base with {base}: {fork.stderr.strip()}")
    root = repo / "redline/changes" / change / "specs"
    deltas = sorted(root.glob("**/delta.md"))
    if not deltas:
        raise RuntimeError(f"no deltas in redline/changes/{change}/specs")
    before, now = living(repo, fork.stdout.strip()), living(repo, None)
    bad: list[str] = []
    named: set[str] = set()
    counts = {"ADDED": 0, "MODIFIED": 0, "REMOVED": 0}
    for delta in deltas:
        path = delta.relative_to(repo).as_posix()
        spec = f"redline/specs/{delta.parent.relative_to(root).as_posix()}/spec.md"
        scenarios, removed = parse(delta.read_text(encoding="utf-8"))
        for sid, section, requirement, block, n in scenarios:
            named.add(sid)
            if section == "REMOVED":
                bad.append(f"{path}:{n}: {sid} is a heading under REMOVED; "
                           "a removed scenario is an `- <ID>: <reason>` line")
                continue
            if section is None:
                bad.append(f"{path}:{n}: {sid} is in no ADDED or MODIFIED section")
                continue
            counts[section] += 1
            had = sid in before and before[sid][0] == spec
            if section == "ADDED" and had:
                bad.append(f"{sid}: ADDED, but {spec} already had it at the merge-base")
            if section == "MODIFIED" and not had:
                bad.append(f"{sid}: MODIFIED, but {spec} didn't have it at the merge-base")
            if sid not in now or now[sid][0] != spec:
                bad.append(f"{sid}: {section}, but {spec} doesn't have it")
                continue
            if now[sid][1] != requirement:
                bad.append(f"{sid}: {spec} has it under Requirement: {now[sid][1]}, not {requirement}")
            if now[sid][2] != block:
                bad.append(f"{sid}: {spec} has it with text other than the delta's")
        for sid in removed:
            named.add(sid)
            counts["REMOVED"] += 1
            if sid not in before or before[sid][0] != spec:
                bad.append(f"{sid}: REMOVED, but {spec} didn't have it at the merge-base")
            if sid in now and now[sid][0] == spec:
                bad.append(f"{sid}: REMOVED, but {spec} still has it")
    for sid in sorted(set(before) | set(now), key=lambda s: ((now.get(s) or before[s])[0], s)):
        was, is_ = before.get(sid), now.get(sid)
        if sid in named or was == is_:
            continue
        what = "added to" if was is None else "removed from" if is_ is None else "changed in"
        bad.append(f"{sid}: {what} {(is_ or was)[0]} since the merge-base, but no delta of {change} names it")
    return bad, counts
