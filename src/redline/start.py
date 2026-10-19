"""`redline start <change>/<step>`: refuse unless the step may begin, then print its brief.

A change's steps come from redline/changes/<change>/steps.md, in order: a `## <step>: <goal>`
heading for each, with an `Owns: ID, ID` line for the scenarios it owns. Under `## Open items`,
each `- <ID> [<step>]: <text>` line is a deferred item owned by that step.

A step is merged on main when a commit reachable from main carries the trailer
`Redline-Step: <change>/<step>`. The open step is kept in the git directory, and stops being open
once it is merged. A change is complete once its last step is merged. A change in an
initiative's phase waits until every change of the earlier phases is complete (plan.py).
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from redline.order import git
from redline.plan import placed
from redline.premises import premise_lines

STEP = re.compile(r"^## (S|R|G\d+|C): (.+)$")
OWNS = re.compile(r"^Owns: (.+)$")
ITEM = re.compile(r"^- (\S+) \[(\S+)\]: (.+)$")
HEADING = re.compile(r"^#### Scenario (\S+) \[(?:new|hold)\]:")
TRAILER = "Redline-Step"


class Refused(Exception):
    """The step may not start yet."""


@dataclass
class Step:
    name: str
    goal: str
    owns: list[str] = field(default_factory=list)
    items: list[str] = field(default_factory=list)


def read_steps(repo: Path, change: str) -> list[Step]:
    path = f"redline/changes/{change}/steps.md"
    if not (repo / path).is_file():
        raise RuntimeError(f"no steps file {path}")
    steps: list[Step] = []
    in_items = False
    for line in (repo / path).read_text(encoding="utf-8").splitlines():
        if heading := STEP.match(line):
            steps.append(Step(heading[1], heading[2]))
            in_items = False
        elif line.startswith("## "):
            in_items = line == "## Open items"
        elif in_items and (item := ITEM.match(line)):
            owner = next((s for s in steps if s.name == item[2]), None)
            if owner is None:
                raise RuntimeError(f"open item {item[1]} names no step: {line}")
            owner.items.append(f"- {item[1]}: {item[3]}")
        elif steps and not in_items and (owns := OWNS.match(line)):
            steps[-1].owns += [sid.strip() for sid in owns[1].split(",") if sid.strip()]
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


def brief(repo: Path, change: str, step: Step) -> str:
    parts = [f"# Brief: {change}/{step.name}", f"Goal: {step.goal}", "", "## Owned scenarios"]
    parts += [scenario(repo, change, sid) + "\n" for sid in step.owns] or ["(none)", ""]
    parts += ["## Cited files (premises)"] + (premises(repo, change) or ["(none)"])
    parts += ["", "## Open items"] + (step.items or ["(none)"])
    if found := placed(repo, change):
        plan, index = found
        phase = plan.phases[index]
        parts += ["", f"## Initiative: {plan.name}", f"Goal: {plan.goal}",
                  f"Phase {phase.number} of {len(plan.phases)}: {phase.name}", f"Stop: {phase.stop}"]
    return "\n".join(parts) + "\n"


def complete(repo: Path, change: str, done: set[str]) -> bool:
    """Whether the last step of the change is merged; a change with no steps yet isn't."""
    try:
        steps = read_steps(repo, change)
    except RuntimeError:
        return False
    return bool(steps) and f"{change}/{steps[-1].name}" in done


def waiting(repo: Path, change: str, done: set[str]) -> str:
    """Why the change's phase can't begin yet, or nothing."""
    if not (found := placed(repo, change)):
        return ""
    plan, index = found
    for phase in plan.phases[:index]:
        if behind := [c for c in phase.changes if not complete(repo, c, done)]:
            return (f"phase {plan.phases[index].number} of {plan.name} waits for phase {phase.number}: "
                    f"{', '.join(behind)} not complete")
    return ""


def merged_steps(repo: Path) -> set[str]:
    log = git(repo, "log", "main", f"--format=%(trailers:key={TRAILER},valueonly)")
    if log.returncode:
        raise RuntimeError(log.stderr.strip())
    return {line.strip() for line in log.stdout.splitlines() if line.strip()}


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
    current = state.read_text().strip() if state.is_file() else ""
    if current and current != name and current not in merged:
        raise Refused(f"step {current} is still open; finish it with `redline pr` first")
    if why := waiting(repo, change, merged):
        raise Refused(why)
    if index and (previous := f"{change}/{steps[index - 1].name}") not in merged:
        raise Refused(f"previous step {previous} is not merged on main")
    head = git(repo, "rev-parse", "HEAD", "main").stdout.split()
    branch = git(repo, "branch", "--show-current").stdout.strip()
    if branch == "main" or len(head) != 2 or head[0] != head[1]:
        raise Refused("start each step on a new branch fresh from main (no commits of its own yet)")
    text = brief(repo, change, steps[index])
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(name + "\n")
    return text
