"""Red before green, from git history.

For every scenario, each commit that introduces it as green (marker without `new=True`) must have
a commit where it was red (`new=True`) among its ancestors. With `since`, only the commits of
`since..rev` make a scenario red or turn it green: a change's window (redline.ledger).
Markers are read as each runner reads them (redline.runner), once per blob; a file that doesn't
parse at a commit gives none there, and is noted. See docs/design.md, §5.
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path

from redline.runner import Mark, markers, runner_for

READ: dict[tuple[str, str], tuple[Mark, ...] | str] = {}  # (runner, blob) -> its markers, or why it can't be read


@dataclass
class Result:
    scenario: str
    status: str  # "ok", "pending" (red, no green yet) or "fail"
    red: str | None = None
    green: str | None = None


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)


def shown(repo: Path, path: str, rev: str | None = None) -> str | None:
    """The file's text at `rev`, else in the working tree; None when it isn't there."""
    if rev is None:
        return (repo / path).read_text(encoding="utf-8") if (repo / path).is_file() else None
    done = git(repo, "show", f"{rev}:{path}")
    return done.stdout if done.returncode == 0 else None


def contents(repo: Path, blobs: list[str]) -> dict[str, str]:
    """Each blob's text, read in one `git cat-file --batch`."""
    out = subprocess.run(["git", "cat-file", "--batch"], cwd=repo, capture_output=True,
                         input="".join(f"{blob}\n" for blob in blobs).encode()).stdout
    texts, at = {}, 0
    for blob in blobs:
        end = out.index(b"\n", at)  # "<blob> blob <size>", then the content and a newline
        size = int(out[at:end].split()[2])
        texts[blob] = out[end + 1:end + 1 + size].decode("utf-8", errors="replace")
        at = end + 2 + size
    return texts


def scan(repo: Path, commit: str, skipped: dict[tuple[str, str], str] | None = None) -> dict[str, str]:
    """Scenario ID -> "red" or "green" for the test files at `commit`; (path, why) -> commit for each
    file that can't be read, the first commit only."""
    files = []
    for record in git(repo, "ls-tree", "-r", "-z", commit).stdout.split("\0"):
        meta, _, path = record.partition("\t")
        if meta.split()[1:2] == ["blob"] and (runner := runner_for(path)):
            files.append((runner, path, meta.split()[2]))
    texts = contents(repo, sorted({b for r, _, b in files if (r.name, b) not in READ}))
    states: dict[str, str] = {}
    for runner, path, blob in files:
        if (runner.name, blob) not in READ:
            try:
                READ[runner.name, blob] = markers(runner, path, texts[blob])
            except RuntimeError as error:
                READ[runner.name, blob] = str(error).removeprefix(f"{path}: ")
        if isinstance(found := READ[runner.name, blob], str):
            if skipped is not None:
                skipped.setdefault((path, found), commit)
            continue
        for mark in found:
            if not mark.new or states.get(mark.sid) != "green":
                states[mark.sid] = "red" if mark.new else "green"
    return states


def is_ancestor(repo: Path, older: str, newer: str) -> bool:
    return git(repo, "merge-base", "--is-ancestor", older, newer).returncode == 0


def check_order(repo: Path, rev: str = "HEAD", since: str | None = None, notes: list[str] | None = None) -> list[Result]:
    """Each scenario's result; `notes` gets a line for each test file skipped because it can't be read."""
    listing = git(repo, "rev-list", "--reverse", "--topo-order", "--parents", rev)
    if listing.returncode:
        raise RuntimeError(listing.stderr.strip())
    counted = set(git(repo, "rev-list", f"{since}..{rev}").stdout.split()) if since else None
    states: dict[str, dict[str, str]] = {}
    reds: dict[str, list[str]] = {}
    results: dict[str, Result] = {}
    skipped: dict[tuple[str, str], str] = {}
    for line in listing.stdout.splitlines():
        commit, *parents = line.split()
        states[commit] = scan(repo, commit, skipped)
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
    if notes is not None:
        notes += [f"skipped {path} at {commit[:7]}: {why}" for (path, why), commit in skipped.items()]
    return sorted(results.values(), key=lambda r: r.scenario)
