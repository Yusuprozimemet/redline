"""Red before green, from git history.

For every scenario, each commit that introduces it as green (marker without `new=True`) must have
a commit where it was red (`new=True`) among its ancestors. With `since`, only the commits of
`since..rev` make a scenario red or turn it green: a change's window (redline.ledger).
"""

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

MARKER = re.compile(r"""mark\.spec\(\s*["']([^"']+)["']\s*(,\s*new\s*=\s*True\s*)?\)""")


@dataclass
class Result:
    scenario: str
    status: str  # "ok", "pending" (red, no green yet) or "fail"
    red: str | None = None
    green: str | None = None


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)


def scan(repo: Path, commit: str) -> dict[str, str]:
    """Scenario ID -> "red" or "green" for the test files at `commit`."""
    found = git(repo, "grep", "-h", "-E", r"mark\.spec\(", commit, "--", "*.py").stdout
    states: dict[str, str] = {}
    for sid, new in MARKER.findall(found):
        if not new or states.get(sid) != "green":
            states[sid] = "red" if new else "green"
    return states


def is_ancestor(repo: Path, older: str, newer: str) -> bool:
    return git(repo, "merge-base", "--is-ancestor", older, newer).returncode == 0


def check_order(repo: Path, rev: str = "HEAD", since: str | None = None) -> list[Result]:
    listing = git(repo, "rev-list", "--reverse", "--topo-order", "--parents", rev)
    if listing.returncode:
        raise RuntimeError(listing.stderr.strip())
    counted = set(git(repo, "rev-list", f"{since}..{rev}").stdout.split()) if since else None
    states: dict[str, dict[str, str]] = {}
    reds: dict[str, list[str]] = {}
    results: dict[str, Result] = {}
    for line in listing.stdout.splitlines():
        commit, *parents = line.split()
        states[commit] = scan(repo, commit)
        if counted is not None and commit not in counted:
            continue  # still read: a parent of the window's first commits
        for sid, state in states[commit].items():
            result = results.setdefault(sid, Result(sid, "pending"))
            if state == "red":
                reds.setdefault(sid, []).append(commit)
                result.red = result.red or commit
            elif not any(states[p].get(sid) == "green" for p in parents):
                red = next((r for r in reds.get(sid, []) if is_ancestor(repo, r, commit)), None)
                if result.status != "fail":
                    result.status, result.red, result.green = ("ok", red, commit) if red else ("fail", None, commit)
    return sorted(results.values(), key=lambda r: r.scenario)
