"""Red before green, from git history.

For every scenario, each commit that introduces it as green (marker without `new=True`) must have
a commit where it was red (`new=True`) among its ancestors. With `since`, only the commits of
`since..rev` make a scenario red or turn it green: a change's window (redline.ledger). `failed` gives the failures a gate counts: none for a scenario no test
at `rev` links any more, or a `hold` one (O-SELF5).
Markers are read as each runner reads them (redline.runner), once per blob; a file that doesn't
parse at a commit gives none there, and is noted. History is read in a fixed number of git calls,
each commit's files being its first parent's with its diff applied (O-PERF1). See specs/, §5.
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path

from redline.runner import Mark, Runner, markers, runner_for

READ: dict[tuple[str, str], tuple[Mark, ...] | str] = {}  # (runner, blob) -> its markers, or why it can't be read


@dataclass
class Result:
    scenario: str
    status: str  # "ok", "pending" (red, no green yet) or "fail"
    red: str | None = None
    green: str | None = None
    linked: bool = True  # a test at `rev` links it; if not, only history holds it (O-SELF5)


def failed(results: list[Result], held: set[str]) -> list[Result]:
    """The failures a gate counts: a scenario a test at `rev` still links, not `hold`, which has no red by design."""
    return [r for r in results if r.status == "fail" and r.linked and r.scenario not in held]


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-c", "core.quotePath=false", *args], cwd=repo, capture_output=True,
                          encoding="utf-8", errors="replace")


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


Files = dict[str, tuple[Runner, str]]  # path -> its runner and blob


def read(repo: Path, files: list[tuple[str, Runner, str]]) -> None:
    """Each (path, runner, blob)'s markers into READ, the blobs not read before in one `cat-file`."""
    texts = contents(repo, sorted({blob for _, runner, blob in files if (runner.name, blob) not in READ}))
    for path, runner, blob in files:
        if (runner.name, blob) not in READ:
            try:
                READ[runner.name, blob] = markers(runner, path, texts[blob])
            except RuntimeError as error:
                READ[runner.name, blob] = str(error).removeprefix(f"{path}: ")


def scan(repo: Path, commit: str, skipped: dict[tuple[str, str], str] | None = None) -> dict[str, str]:
    """Scenario ID -> "red" or "green" for the test files at `commit`; (path, why) -> commit for each
    file that can't be read, the first commit only."""
    files: Files = {}
    for record in git(repo, "ls-tree", "-r", "-z", commit).stdout.split("\0"):
        meta, _, path = record.partition("\t")
        if meta.split()[1:2] == ["blob"] and (runner := runner_for(path)):
            files[path] = (runner, meta.split()[2])
    read(repo, [(path, runner, blob) for path, (runner, blob) in files.items()])
    return marked(files, commit, skipped)


def marked(files: Files, commit: str, skipped: dict[tuple[str, str], str] | None) -> dict[str, str]:
    """Scenario ID -> "red" or "green" for `files`, whose markers READ holds."""
    states: dict[str, str] = {}
    for path, (runner, blob) in files.items():
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


def merged_into(repo: Path, commit: str, line: list[str], main: str) -> str:
    """The first commit of `line`, main's first-parent line oldest first, that contains `commit`:
    `commit` itself or one of its descendants, all found in one call."""
    after = {commit, *git(repo, "rev-list", "--ancestry-path", f"{commit}..{main}").stdout.split()}
    merged = next((c for c in line if c in after), None)
    if merged is None:
        raise RuntimeError(f"{commit[:7]} isn't merged on {main}")
    return merged


def history(repo: Path, rev: str) -> dict[str, tuple[list[str], Files]]:
    """Each commit of `rev`, oldest first in topological order, with its parents and its runners'
    files: its first parent's, with its diff against that parent applied. One `git log`, one `cat-file`."""
    log = git(repo, "log", "--reverse", "--topo-order", "--no-color", "--no-renames", "--no-abbrev", "--raw", "-z", "--root",
              "--diff-merges=first-parent", "--format=%x01%H %P", rev)
    if log.returncode:
        raise RuntimeError(log.stderr.strip())
    commits: dict[str, tuple[list[str], Files]] = {}
    new: list[tuple[str, Runner, str]] = []
    for entry in log.stdout.split("\x01")[1:]:
        head, *records = [part for part in entry.split("\0") if part not in ("", "\n")]  # "\n" ends a header
        commit, *parents = head.split()
        files = commits[parents[0]][1] if parents else {}
        changed = {path: meta.split() for meta, path in zip(records[::2], records[1::2])
                   if runner_for(path)}  # ":<old mode> <new mode> <old blob> <new blob> <status>"
        if changed:
            files = dict(files)
            for path, (_, mode, _, blob, _) in changed.items():
                files.pop(path, None)
                if mode not in ("000000", "160000"):  # deleted, or a submodule: no blob
                    files[path] = (runner_for(path), blob)
                    new.append((path, files[path][0], blob))
        commits[commit] = (parents, files)
    read(repo, new)
    return commits


def check_order(repo: Path, rev: str = "HEAD", since: str | None = None, notes: list[str] | None = None) -> list[Result]:
    """Each scenario's result; `notes` gets a line for each test file skipped because it can't be read."""
    commits = history(repo, rev)
    counted = set(git(repo, "rev-list", f"{since}..{rev}").stdout.split()) if since else None
    states: dict[str, dict[str, str]] = {}
    reds: dict[str, list[str]] = {}
    results: dict[str, Result] = {}
    skipped: dict[tuple[str, str], str] = {}
    for commit, (parents, files) in commits.items():
        first = parents and commits[parents[0]][1]
        states[commit] = states[parents[0]] if first is files else marked(files, commit, skipped)
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
    now = states[next(reversed(commits))] if commits else {}  # topological order: `rev` comes last
    for result in results.values():
        result.linked = result.scenario in now
    return sorted(results.values(), key=lambda r: r.scenario)
