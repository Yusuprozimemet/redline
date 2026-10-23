"""redline/changes/<change>/ledger.yaml: a cache of the change's evidence, rebuilt from main.

Every scenario the change's deltas declare gets `red`, `green` and `break` entries. Red and green
are check-order's commits on main, each with `merged`, the first commit on main's first-parent
line that contains it (the commit CI ran on), and `result`, which only CI knows: it comes from the
git note CI left on `merged` under refs/notes/redline-ci, and is `unverified` without one, and
`unconfirmed` when the note's `run:` isn't the push run that wrote it, as GitHub has it (§4). Commits
not reachable from main aren't evidence. A `hold` scenario has no red or green; its `break` is the
commit where its test landed, with the result CI noted for it under `break:` (see redline.breaks).
A change's evidence is its own (§4): red and green count only from its window, the PRs from its
S step to its C step, and a break is its R step's. Without its S step on main, all of main counts.
"""

from pathlib import Path

import yaml

from redline.breaks import holds
from redline.order import check_order, git, merged_into, scan
from redline.start import HEADING, TRAILER

NOTES = "redline-ci"
HEADER = (
    "# A cache of evidence, rebuilt from main's history by `redline ledger <change>`.\n"
    "# CI rebuilds it and fails on a mismatch, so never edit it by hand. See docs/design.md, section 4.\n"
)


def ledger_path(change: str) -> str:
    return f"redline/changes/{change}/ledger.yaml"


def declared(repo: Path, change: str) -> list[str]:
    ids: list[str] = []
    for delta in sorted((repo / "redline/changes" / change / "specs").glob("**/delta.md")):
        for line in delta.read_text(encoding="utf-8").splitlines():
            if (heading := HEADING.match(line)) and heading[1] not in ids:
                ids.append(heading[1])
    if not ids:
        raise RuntimeError(f"no scenarios declared in redline/changes/{change}/specs")
    return ids


def ci_result(repo: Path, commit: str, github, counted=(), broken: str | None = None) -> str:
    """The suite's result in the CI note on `commit`, or with `broken`, that scenario's break; `unconfirmed`
    unless the note's run checks out (§4). `counted` are the hold scenarios whose breaks are read from it."""
    shown = git(repo, "notes", f"--ref={NOTES}", "show", commit)
    if shown.returncode:
        return "unverified"
    try:
        data = yaml.safe_load(shown.stdout)
    except yaml.YAMLError:
        data = None
    result = data.get("result") if isinstance(data, dict) else None
    if result not in ("pass", "fail"):
        raise RuntimeError(f"the CI note on {commit[:7]} has no result: pass or fail")
    breaks = data.get("break") if isinstance(data.get("break"), dict) else {}
    failed = result == "fail" or any(breaks.get(sid) == "fail" for sid in counted)
    url = data.get("run")
    run = github.push_run(url) if isinstance(url, str) else None
    want = {"html_url": url, "event": "push", "head_sha": commit, "head_branch": "main",
            "path": ".github/workflows/redline.yml"}
    if (run is None or any(run.get(key) != value for key, value in want.items()) or "redline" not in run["jobs"]
            or (run["jobs"]["redline"] == "success") == failed):
        return "unconfirmed"
    if broken is None or result == "fail":
        return result
    return breaks[broken] if breaks.get(broken) in ("pass", "fail") else "unverified"


def stamped(repo: Path, name: str, main: str) -> list[str]:
    """The commits reachable from main whose Redline-Step trailer names the step `name`, oldest first."""
    log = git(repo, "log", "--reverse", "--topo-order", f"--format=%H|%(trailers:key={TRAILER},valueonly,separator=|)", main)
    return [commit for commit, *steps in (row.split("|") for row in log.stdout.splitlines())
            if name in (step.strip() for step in steps)]


def rebuild(repo: Path, change: str, main: str = "main") -> dict:
    from redline.pr import GitHub  # here, as pr imports close, which imports this

    github = GitHub(repo)  # one per rebuild, so each run is asked about once
    ids = declared(repo, change)
    listing = git(repo, "rev-list", "--first-parent", "--reverse", main)
    if listing.returncode:
        raise RuntimeError(listing.stderr.strip())
    line = listing.stdout.split()

    def merge(commit: str) -> str:
        return merged_into(repo, commit, line, main)

    since = until = None
    reds = []
    if spec := stamped(repo, f"{change}/S", main):  # the window: from the S step's PR to the C step's
        since = git(repo, "rev-parse", "-q", "--verify", f"{merge(spec[0])}^1").stdout.strip() or None
        until = merge(close[0]) if (close := stamped(repo, f"{change}/C", main)) else None
        reds = stamped(repo, f"{change}/R", main)
    found = {r.scenario: r for r in check_order(repo, until or main, since)}

    held = set(holds(repo, change))
    landed = {  # its R step's first commit that links it; without an S step, where it landed
        sid: next((c for c in reds if scan(repo, c).get(sid) == "green"), None) if spec else (r := found.get(sid)) and r.green
        for sid in ids if sid in held}
    counted: dict[str, set[str]] = {}  # each merged commit, the hold scenarios whose breaks are read from its note
    for sid, commit in landed.items():
        if commit:
            counted.setdefault(merge(commit), set()).add(sid)

    def evidence(commit: str | None, broken: str | None = None) -> dict | None:
        if commit is None:
            return None
        merged = merge(commit)
        return {"commit": commit, "merged": merged,
                "result": ci_result(repo, merged, github, counted.get(merged, ()), broken)}

    scenarios = {}
    for sid in ids:
        result = found.get(sid)
        if sid in held:
            scenarios[sid] = {"red": None, "green": None, "break": evidence(landed[sid], sid)}
            continue
        scenarios[sid] = {
            "red": evidence(result and result.red),
            "green": evidence(result and result.green),
            "break": None,
        }
    return {"change": change, "scenarios": scenarios}


def write_ledger(repo: Path, change: str, main: str = "main") -> dict:
    data = rebuild(repo, change, main)
    text = HEADER + yaml.safe_dump(data, sort_keys=False, default_flow_style=False)
    (repo / ledger_path(change)).write_text(text, encoding="utf-8")
    return data


def check_ledger(repo: Path, change: str, main: str = "main") -> list[str]:
    """Each way the committed ledger differs from the one rebuilt from history."""
    want = rebuild(repo, change, main)
    path = ledger_path(change)
    if not (repo / path).is_file():
        return [f"{path}: missing; run `redline ledger {change}`"]
    have = yaml.safe_load((repo / path).read_text(encoding="utf-8"))
    if not isinstance(have, dict) or have.get("change") != change:
        return [f"{path}: not the ledger of {change}; run `redline ledger {change}`"]
    scenarios = have.get("scenarios") if isinstance(have.get("scenarios"), dict) else {}
    return [
        f"{path}: {sid} doesn't match the history of {main}; run `redline ledger {change}`"
        for sid in sorted(set(want["scenarios"]) | set(scenarios))
        if scenarios.get(sid) != want["scenarios"].get(sid)
    ]
