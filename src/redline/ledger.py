"""redline/changes/<change>/ledger.yaml: a cache of the change's evidence, rebuilt from main.

Every scenario the change's deltas declare gets `red`, `green` and `break` entries. Red and green
are check-order's commits on main, each with `merged`, the first commit on main's first-parent
line that contains it (the commit CI ran on), and `result`, which only CI knows: it comes from the
git note CI left on `merged` under refs/notes/redline-ci, and is `unverified` without one. Commits
not reachable from main aren't evidence. A `hold` scenario has no red or green; its `break` is the
commit where its test landed, with the result CI noted for it under `break:` (see redline.breaks).
"""

from pathlib import Path

import yaml

from redline.breaks import holds
from redline.order import check_order, git, is_ancestor
from redline.start import HEADING

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


def ci_result(repo: Path, commit: str, broken: str | None = None) -> str:
    """The suite's result in the CI note on `commit`, or with `broken`, that scenario's break."""
    shown = git(repo, "notes", f"--ref={NOTES}", "show", commit)
    if shown.returncode:
        return "unverified"
    data = yaml.safe_load(shown.stdout)
    result = data.get("result") if isinstance(data, dict) else None
    if result not in ("pass", "fail"):
        raise RuntimeError(f"the CI note on {commit[:7]} has no result: pass or fail")
    if broken is None:
        return result
    breaks = data.get("break")
    result = breaks.get(broken) if isinstance(breaks, dict) else None
    return result if result in ("pass", "fail") else "unverified"


def rebuild(repo: Path, change: str, main: str = "main") -> dict:
    ids = declared(repo, change)
    listing = git(repo, "rev-list", "--first-parent", "--reverse", main)
    if listing.returncode:
        raise RuntimeError(listing.stderr.strip())
    line = listing.stdout.split()
    found = {r.scenario: r for r in check_order(repo, main)}

    def evidence(commit: str | None, broken: str | None = None) -> dict | None:
        if commit is None:
            return None
        merged = next(c for c in line if is_ancestor(repo, commit, c))
        return {"commit": commit, "merged": merged, "result": ci_result(repo, merged, broken)}

    held = set(holds(repo, change))
    scenarios = {}
    for sid in ids:
        result = found.get(sid)
        if sid in held:  # check-order calls the commit where a hold test landed its green
            scenarios[sid] = {"red": None, "green": None, "break": evidence(result and result.green, sid)}
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
