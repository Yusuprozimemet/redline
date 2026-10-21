"""`redline start <change>/<step>`: refuse unless the step may begin, then print its brief.

A change's steps come from redline/changes/<change>/steps.md, in order: a `## <step>: <goal>`
heading for each, with an `Owns: ID, ID` line for the scenarios it owns and, for a G step, a
`Track: glob, glob` line for the code it may change (track.py). Under `## Open items`,
each `- <ID> [<step>]: <text>` line is a deferred item owned by that step. Any other line there,
and the rest of what check-steps fails on line by line, `scan` collects (steps.py).

A step is merged on main when a commit reachable from main carries the trailer
`Redline-Step: <change>/<step>`. The open step is kept in the git directory, and stops being open
once it is merged. A change is complete once its last step is merged. A change in an
initiative's phase waits until every change of the earlier phases is complete (plan.py), and, in
a critical initiative, until its plan audits are on main (planaudit.py). `may_begin` makes both
refusals from one tree: `start` reads main, and `redline ci pr` the merge-base.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from redline.config import load_config
from redline.order import git, shown
from redline.plan import placed
from redline.premises import premise_lines

STEP = re.compile(r"^## (S|R|G\d+|C): (.+)$")
OWNS = re.compile(r"^Owns: (.+)$")
TRACK = re.compile(r"^Track:(.*)$")
ITEM = re.compile(r"^- (\S+) \[(\S+)\]: (.+)$")
HEADING = re.compile(r"^#### Scenario (\S+) \[(?:new|hold|manual)\]:")
TRAILER = "Redline-Step"


class Refused(Exception):
    """The step may not start yet."""


@dataclass
class Step:
    name: str
    goal: str
    owns: list[str] = field(default_factory=list)
    items: list[str] = field(default_factory=list)
    track: list[str] | None = None  # None: no Track: line
    owned_at: dict[str, int] = field(default_factory=dict)  # each owned ID's line


def read_steps(repo: Path, change: str, rev: str | None = None) -> list[Step]:
    path = f"redline/changes/{change}/steps.md"
    if (text := shown(repo, path, rev)) is None:
        raise RuntimeError(f"no steps file {path}")
    return parse_steps(text)


def scan(text: str) -> tuple[list[Step], list[str], list[str]]:
    """The steps, what check-steps fails on line by line, and each open item's line that names no step."""
    steps: list[Step] = []
    items, bad = [], []
    in_items = False
    for n, line in enumerate(text.splitlines(), 1):
        if heading := STEP.match(line):
            if any(s.name == heading[1] for s in steps):
                bad.append(f"steps.md:{n}: step {heading[1]} named twice")
            steps.append(Step(heading[1], heading[2]))
            in_items = False
        elif line.startswith("## "):
            in_items = line == "## Open items"
            if not in_items:
                bad.append(f"steps.md:{n}: neither a step nor `## Open items`: {line}")
        elif in_items:
            if item := ITEM.match(line):
                items.append((n, line, item))
            elif line.strip():
                bad.append(f"steps.md:{n}: not an open item `- <ID> [<step>]: <text>`: {line}")
        elif ITEM.match(line):
            bad.append(f"steps.md:{n}: an open item outside `## Open items`: {line}")
        elif steps and (owns := OWNS.match(line)):
            for sid in (sid.strip() for sid in owns[1].split(",") if sid.strip()):
                steps[-1].owns.append(sid)
                steps[-1].owned_at.setdefault(sid, n)
        elif steps and (track := TRACK.match(line)):
            steps[-1].track = [glob.strip() for glob in track[1].split(",") if glob.strip()]
    seen, orphans = set(), []
    for n, line, item in items:  # after every step, so an item may come before the step that owns it
        if item[1] in seen:
            bad.append(f"steps.md:{n}: open item {item[1]} given twice")
        seen.add(item[1])
        if (owner := next((s for s in steps if s.name == item[2]), None)) is None:
            bad.append(f"steps.md:{n}: open item {item[1]} names no step of steps.md: [{item[2]}]")
            orphans.append(f"open item {item[1]} names no step: {line}")
        else:
            owner.items.append(f"- {item[1]}: {item[3]}")
    return steps, bad, orphans


def parse_steps(text: str) -> list[Step]:
    steps, _, orphans = scan(text)
    if orphans:
        raise RuntimeError(orphans[0])
    return steps


def spec_files(repo: Path, change: str) -> list[Path]:
    """The change's own deltas first, then the living specs."""
    return sorted((repo / "redline/changes" / change / "specs").glob("**/delta.md")) + sorted(
        (repo / "redline/specs").glob("**/spec.md")
    )


def scenario(repo: Path, change: str, sid: str) -> str:
    for path in spec_files(repo, change):
        lines = path.read_text(encoding="utf-8").splitlines()
        for n, line in enumerate(lines):
            if (heading := HEADING.match(line)) and heading[1] == sid:
                block = [line]
                for rest in lines[n + 1:]:
                    if rest.startswith("#"):
                        break
                    block.append(rest)
                where = path.relative_to(repo).as_posix()
                return "\n".join(block).rstrip() + f"\n(from {where}:{n + 1})"
    raise RuntimeError(f"scenario {sid} is not declared in any spec")


def premises(repo: Path, change: str) -> list[str]:
    return [text for _, _, text in premise_lines(repo, change)]


def brief(repo: Path, change: str, step: Step, done: set[str]) -> str:
    """The step's hand-off, ending with the change's progress given the steps `done` on main."""
    from redline.progress import progress  # progress imports this module
    parts = [f"# Brief: {change}/{step.name}", f"Goal: {step.goal}", "", "## Owned scenarios"]
    parts += [scenario(repo, change, sid) + "\n" for sid in step.owns] or ["(none)", ""]
    parts += ["## Cited files (premises)"] + (premises(repo, change) or ["(none)"])
    parts += ["", "## Open items"] + (step.items or ["(none)"])
    if step.track:
        parts += ["", "## Track", ", ".join(step.track)]
    if rules := load_config(repo).rules:
        parts += ["", "## Rules"] + [f"- {cause}: {rule}" for cause, lines in rules.items() for rule in lines]
    if found := placed(repo, change):
        plan, index = found
        phase = plan.phases[index]
        parts += ["", f"## Initiative: {plan.name}", f"Goal: {plan.goal}",
                  f"Phase {phase.number} of {len(plan.phases)}: {phase.name}", f"Stop: {phase.stop}"]
    return "\n".join(parts) + "\n\n" + progress(repo, change, done)


def complete(repo: Path, change: str, done: set[str], rev: str | None = None) -> bool:
    """Whether the last step of the change's steps.md (at `rev`) is merged; a change with no steps yet isn't."""
    try:
        steps = read_steps(repo, change, rev)
    except RuntimeError:
        return False
    return bool(steps) and f"{change}/{steps[-1].name}" in done


def waiting(repo: Path, change: str, done: set[str], rev: str | None = None) -> str:
    """Why the change's phase can't begin yet, or nothing; the plan and steps.md read at `rev`."""
    if not (found := placed(repo, change, rev)):
        return ""
    plan, index = found
    for phase in plan.phases[:index]:
        if behind := [c for c in phase.changes if not complete(repo, c, done, rev)]:
            return (f"phase {plan.phases[index].number} of {plan.name} waits for phase {phase.number}: "
                    f"{', '.join(behind)} not complete")
    return ""


def may_begin(repo: Path, change: str, merged: set[str], rev: str) -> None:
    """Refuse a step of the change while an earlier phase isn't complete or, at critical, its plan audits aren't
    there; every file read at `rev` (main for `start`, the merge-base in CI), what is `merged` passed in."""
    if why := waiting(repo, change, merged, rev):
        raise Refused(why)
    if found := placed(repo, change, rev):
        from redline.planaudit import before_start  # planaudit imports this module
        if bad := before_start(repo, *found, rev):
            raise Refused(f"{found[0].name} needs its plan audits on main first:\n" + "\n".join(bad))


def merged_steps(repo: Path, ref: str = "main") -> set[str]:
    log = git(repo, "log", ref, f"--format=%(trailers:key={TRAILER},valueonly)")
    if log.returncode:
        raise RuntimeError(log.stderr.strip())
    return {line.strip() for line in log.stdout.splitlines() if line.strip()}


def next_step(repo: Path, name: str, base: str) -> str:
    """Refuse unless `<change>/<step>` is in steps.md at the merge-base with `base`, every step before it
    there is merged on `base`, and it isn't; with no steps.md there, only S, which writes it, may be open.
    Return the merge-base."""
    change, _, step = name.partition("/")
    found = git(repo, "merge-base", base, "HEAD")
    if found.returncode:
        raise RuntimeError(f"no merge-base with {base}: {found.stderr.strip()}")
    fork = found.stdout.strip()
    path = f"redline/changes/{change}/steps.md"
    text = shown(repo, path, fork)
    if text is None and step != "S":
        raise Refused(f"{name}: redline/changes/{change} has no steps.md at the merge-base, "
                      "so it can only be at its S step, which writes it")
    names = [s.name for s in parse_steps(text)] if text is not None else ["S"]
    if step not in names:
        raise Refused(f"{name}: {path} at the merge-base has no step {step}")
    merged = merged_steps(repo, base)
    if name in merged:
        raise Refused(f"{name} is already merged on {base}: a step is one PR")
    if behind := [f"{change}/{s}" for s in names[:names.index(step)] if f"{change}/{s}" not in merged]:
        raise Refused(f"{name} isn't next; not merged on {base}: {', '.join(behind)}")
    return fork


def open_step_file(repo: Path) -> Path:
    found = git(repo, "rev-parse", "--git-path", "redline-open-step")
    if found.returncode:
        raise RuntimeError(found.stderr.strip())
    return repo / found.stdout.strip()


def find_step(repo: Path, name: str) -> tuple[str, list[Step], int]:
    """The change, its steps, and the index of the step that `<change>/<step>` names."""
    change, _, step_name = name.partition("/")
    if not change or not step_name:
        raise RuntimeError(f"a step is <change>/<step>, e.g. add-greet/G1, not {name!r}")
    steps = read_steps(repo, change)
    index = next((i for i, s in enumerate(steps) if s.name == step_name), None)
    if index is None:
        raise RuntimeError(f"no step {step_name} in redline/changes/{change}/steps.md")
    return change, steps, index


def start(repo: Path, name: str) -> str:
    change, steps, index = find_step(repo, name)
    merged = merged_steps(repo)
    state = open_step_file(repo)
    current = state.read_text(encoding="utf-8").strip() if state.is_file() else ""
    if current and current != name and current not in merged:
        raise Refused(f"step {current} is still open; finish it with `redline pr` first")
    may_begin(repo, change, merged, "main")  # the tree too: the branch must be fresh from main, below
    if index and (previous := f"{change}/{steps[index - 1].name}") not in merged:
        raise Refused(f"previous step {previous} is not merged on main")
    head = git(repo, "rev-parse", "HEAD", "main").stdout.split()
    branch = git(repo, "branch", "--show-current").stdout.strip()
    if branch == "main" or len(head) != 2 or head[0] != head[1]:
        raise Refused("start each step on a new branch fresh from main (no commits of its own yet)")
    text = brief(repo, change, steps[index], merged)
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(name + "\n", encoding="utf-8")
    return text
