"""How far the work has come, from what main holds: the end of every brief, and `merged`'s after C (§6).

The change's steps merged out of its steps.md and the first that isn't; in an initiative, its
phase's changes complete and the plan's phases complete, as `start` reads completeness; then the
open items whose owning step isn't merged. It prints and judges nothing.
"""

from pathlib import Path

from redline.plan import placed
from redline.start import complete, read_steps

WIDTH = 20


def bar(n: int, total: int) -> str:
    filled = n * WIDTH // total if total else 0
    return "[" + "█" * filled + "░" * (WIDTH - filled) + "]"


def progress(repo: Path, change: str, done: set[str]) -> str:
    steps = read_steps(repo, change)
    merged = [s for s in steps if f"{change}/{s.name}" in done]
    left = [s for s in steps if s not in merged]
    after = f"next: {change}/{left[0].name}" if left else "the change is complete"
    lines = ["## Progress", f"{change}: {bar(len(merged), len(steps))} {len(merged)} of {len(steps)} steps merged · {after}"]
    if found := placed(repo, change):
        plan, index = found
        phase = plan.phases[index]
        changes = sum(complete(repo, c, done) for c in phase.changes)
        phases = sum(all(complete(repo, c, done) for c in p.changes) for p in plan.phases)
        lines += [f"Phase {phase.number} of {len(plan.phases)} ({phase.name}): "
                  f"{bar(changes, len(phase.changes))} {changes} of {len(phase.changes)} changes complete",
                  f"{plan.name}: {bar(phases, len(plan.phases))} {phases} of {len(plan.phases)} phases complete"]
    items = [f"{item.partition(':')[0]} [{s.name}]:{item.partition(':')[2]}" for s in left for item in s.items]
    return "\n".join(lines + ["Open items later steps own:"] + (items or ["(none)"])) + "\n"
