"""`redline check-specs`: at the C step, the deltas reach the living specs and nothing else does. See §5.

A delta's `## ADDED`, `## MODIFIED` and `## REMOVED Requirements` sections say what C does to
`redline/specs/<domain>/spec.md` (§4). Each scenario of the living specs at the merge-base with
main is compared with the same scenario now: its text, heading to the next heading, and the
`### Requirement:` it sits under. So is the text outside scenarios: each requirement's prose, which
only a delta's prose under it may change, and a file's text under no requirement.
"""

import re
from pathlib import Path

from redline.order import git

SCENARIO = re.compile(r"^#### Scenario (\S+) \[(?:new|hold|manual)\]:")
SECTION = re.compile(r"^## (ADDED|MODIFIED|REMOVED) Requirements\s*$")
REQUIREMENT = re.compile(r"^### Requirement: (.+?)\s*$")
REMOVAL = re.compile(r"^- ([^\s:]+): \S")

Scenario = tuple[str, str | None, str | None, str, int]  # ID, section, requirement, text, line
Block = tuple[str | None, str | None, str, int, int]  # section, requirement, prose, scenarios, line


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


def trim(lines: list[str]) -> str:
    """The lines joined, blank lines at either end dropped."""
    kept = [n for n, line in enumerate(lines) if line.strip()]
    return "\n".join(lines[kept[0]:kept[-1] + 1]) if kept else ""


def blocks(text: str) -> list[Block]:
    """The text outside scenarios, cut at each `## ` and `### ` heading: a requirement's block holds
    its prose, any other its heading and text; the first holds what comes before every heading."""
    found: list[list] = [[None, None, [], 0, 1]]
    section = None
    inside = False  # in a scenario's block, which runs to the next `#` line
    for n, line in enumerate(text.splitlines(), 1):
        if line.startswith("#"):
            inside = bool(SCENARIO.match(line))
            if inside:
                found[-1][3] += 1
                continue
            if line.startswith("## "):
                section = heading[1] if (heading := SECTION.match(line)) else None
                found.append([section, None, [line], 0, n])
                continue
            if heading := REQUIREMENT.match(line):
                found.append([section, heading[1], [], 0, n])
                continue
            if line.startswith("### "):
                found.append([section, None, [line], 0, n])
                continue
        if not inside:
            found[-1][2].append(line)
    return [(section, requirement, trim(lines), count, n) for section, requirement, lines, count, n in found]


def files(repo: Path, ref: str | None) -> dict[str, str]:
    """Each spec path in redline/specs at `ref`, or in the tree, and its text."""
    if ref is None:
        return {p.relative_to(repo).as_posix(): p.read_text(encoding="utf-8")
                for p in sorted((repo / "redline/specs").glob("**/spec.md"))}
    listed = git(repo, "ls-tree", "-r", "--name-only", ref, "--", "redline/specs").stdout.split()
    return {p: git(repo, "show", f"{ref}:{p}").stdout for p in sorted(listed) if p.endswith("/spec.md")}


def living(texts: dict[str, str]) -> dict[str, tuple[str, str | None, str]]:
    """Scenario ID -> (spec path, requirement, text)."""
    found: dict[str, tuple[str, str | None, str]] = {}
    for path, text in texts.items():
        for sid, _, requirement, block, _ in parse(text)[0]:
            found.setdefault(sid, (path, requirement, block))
    return found


def outside(texts: dict[str, str]) -> dict[tuple[str, str | None], tuple[str, int]]:
    """(spec path, requirement or None) -> (its text outside scenarios, its scenario count)."""
    found: dict[tuple[str, str | None], tuple[str, int]] = {}
    for path, text in texts.items():
        for _, requirement, prose, count, _ in blocks(text):
            was, had = found.get((path, requirement), ("", 0))
            found[path, requirement] = ("\n".join(p for p in (was, prose) if p), had + count)
    return found


def prose_changes(before: dict[str, str], now: dict[str, str], given: dict[tuple[str, str], str],
                  change: str) -> list[str]:
    """Each way the text outside scenarios differs from what the deltas' prose (`given`) says (§4)."""
    was, is_ = outside(before), outside(now)
    bad: list[str] = []
    for path, requirement in sorted(is_, key=lambda key: (key[0], key[1] or "")):
        (prose, count), old = is_[path, requirement], was.get((path, requirement))
        if requirement is None:
            if old is not None and old[0] != prose:
                bad.append(f"{path}: text under no requirement changed since the merge-base; "
                           "only a spec file C creates or deletes may change it")
            continue
        where = f"Requirement: {requirement} in {path}"
        if (path, requirement) in given:
            if prose != given[path, requirement]:
                bad.append(f"{where}: prose other than the delta's")
        elif prose != (old[0] if old else ""):
            bad.append(f"{where}: prose changed since the merge-base, but no delta of {change} gives prose under it")
        if not count and (old is None or old[1]):
            bad.append(f"{where}: no scenario under it; remove it, heading and prose")
    def scenarios(found: dict[tuple[str, str | None], tuple[str, int]], path: str) -> int:
        return sum(count for (where, _), (_, count) in found.items() if where == path)
    for path in sorted(set(before) & set(now)):
        if scenarios(was, path) and not scenarios(is_, path):
            bad.append(f"{path}: no scenario left; delete it")
    return bad


def check_specs(repo: Path, change: str, base: str = "main") -> tuple[list[str], dict[str, int]]:
    """Each way the living specs differ from what the change's deltas say, and a count per section."""
    fork = git(repo, "merge-base", base, "HEAD")
    if fork.returncode:
        raise RuntimeError(f"no merge-base with {base}: {fork.stderr.strip()}")
    root = repo / "redline/changes" / change / "specs"
    deltas = sorted(root.glob("**/delta.md"))
    if not deltas:
        raise RuntimeError(f"no deltas in redline/changes/{change}/specs")
    texts_before, texts_now = files(repo, fork.stdout.strip()), files(repo, None)
    before, now = living(texts_before), living(texts_now)
    bad: list[str] = []
    named: set[str] = set()
    given: dict[tuple[str, str], str] = {}  # (spec path, requirement) -> the prose a delta gives it
    counts = {"ADDED": 0, "MODIFIED": 0, "REMOVED": 0}
    for delta in deltas:
        path = delta.relative_to(repo).as_posix()
        spec = f"redline/specs/{delta.parent.relative_to(root).as_posix()}/spec.md"
        text = delta.read_text(encoding="utf-8")
        scenarios, removed = parse(text)
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
        for section, requirement, prose, _, n in blocks(text):
            if section in ("ADDED", "MODIFIED") and requirement and prose:
                if given.setdefault((spec, requirement), prose) != prose:
                    bad.append(f"{path}:{n}: Requirement: {requirement} gives prose other than "
                               f"another block of {change} gives it")
    for sid in sorted(set(before) | set(now), key=lambda s: ((now.get(s) or before[s])[0], s)):
        was, is_ = before.get(sid), now.get(sid)
        if sid in named or was == is_:
            continue
        what = "added to" if was is None else "removed from" if is_ is None else "changed in"
        bad.append(f"{sid}: {what} {(is_ or was)[0]} since the merge-base, but no delta of {change} names it")
    return bad + prose_changes(texts_before, texts_now, given, change), counts
