"""`redline check-break <change>`: mutation proves each `hold` scenario's tests can fail.

Its tests (spec marker without `new=True`) must pass unmutated, and fail under at least one mutant
of the Python files the change's premises cite. mutmut sits behind `Mutator`, which tests replace;
it doesn't run on Windows, so there the mutation is skipped (CI runs it). See docs/design.md, §5.
"""

import configparser
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from redline.links import SPEC_PATHS, declarations, grep
from redline.premises import CITATION, premise_lines
from redline.runner import PYTEST, RUNNERS, runner_for

HOLD = re.compile(r"^#### Scenario (\S+) \[hold\]:")


class Mutator:
    """The mutation tool: mutmut, run in a throwaway copy of the repository."""

    def __init__(self, repo: Path):
        self.repo = repo

    def unavailable(self) -> str | None:
        if sys.platform == "win32":
            return "mutmut doesn't run on Windows"
        return None if shutil.which("mutmut") else "mutmut isn't installed"

    def kills(self, files: list[str], sid: str) -> tuple[int, int]:
        """(mutants made from `files`, mutants that made the scenario's tests fail)."""
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "repo"
            shutil.copytree(self.repo, copy, ignore=shutil.ignore_patterns(".git", ".venv", "mutants"))
            config = configparser.ConfigParser()
            config.read(copy / "setup.cfg")
            config["mutmut"] = {"paths_to_mutate": "\n".join(files), "pytest_add_cli_args": f"--redline-spec={sid}"}
            with open(copy / "setup.cfg", "w") as out:
                config.write(out)
            for command in (["mutmut", "run"], ["mutmut", "results", "--all", "true"]):
                done = subprocess.run(command, cwd=copy, capture_output=True, text=True)
                if done.returncode:
                    raise RuntimeError(f"{' '.join(command)}: {(done.stderr or done.stdout).strip()[-500:]}")
        statuses = [line.rpartition(": ")[2].strip() for line in done.stdout.splitlines() if "__mutmut_" in line]
        return len(statuses), statuses.count("killed")


@dataclass
class BreakReport:
    results: dict[str, str | None] = field(default_factory=dict)  # hold scenario -> why it isn't proved
    skipped: str | None = None  # why nothing was mutated here

    @property
    def bad(self) -> dict[str, str]:
        return {sid: why for sid, why in self.results.items() if why}


def holds(repo: Path, change: str | None = None) -> list[str]:
    """The `hold` scenarios of one change's deltas, or of every spec and delta of a change not closed."""
    ids = []
    found = grep(repo, r"^#### Scenario ", *SPEC_PATHS) if change else declarations(repo)
    for path, _, text in found:
        if (hold := HOLD.match(text)) and hold[1] not in ids:
            if change is None or path.startswith(f"redline/changes/{change}/"):
                ids.append(hold[1])
    return ids


def hold_tests(repo: Path, change: str) -> dict[str, dict[str, str]]:
    """Each `hold` scenario of the change -> {`path::name`: SHA-256 of the test's source} for the
    tests whose marker names it without `new=True`. check-break proves them; the lock freezes them."""
    found: dict[str, dict[str, str]] = {sid: {} for sid in holds(repo, change)}
    for runner in RUNNERS if found else ():
        for path in sorted({path for path, _, _ in grep(repo, runner.grep, *runner.paths)}):
            for name, text, marks in runner.tests(path, (repo / path).read_text(encoding="utf-8")):
                digest = hashlib.sha256((text + "\n").encode()).hexdigest()
                for sid, new in runner.marker.findall(marks):
                    if not new and sid in found:
                        found[sid][f"{path}::{name}"] = digest
    return found


def touched(repo: Path, change: str) -> list[str]:
    """The Python files the change's premises cite: the code its R step's tests protect."""
    cited = {path for _, _, text in premise_lines(repo, change) for path, *_ in CITATION.findall(text)}
    return sorted(p for p in cited if p.endswith(".py") and (repo / p).is_file())


def passes(repo: Path, sid: str) -> bool:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    done = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--redline-spec={sid}"],
        cwd=repo, capture_output=True, text=True, env=env,
    )
    return done.returncode == 0


def check_break(repo: Path, change: str) -> BreakReport:
    report = BreakReport()
    tests = hold_tests(repo, change)
    if not tests:
        return report
    files = touched(repo, change)
    mutator = Mutator(repo)
    report.skipped = mutator.unavailable()
    for sid in tests:
        if not tests[sid]:
            report.results[sid] = "no test links it without new=True"
        elif any(runner_for(test) is not PYTEST for test in tests[sid]):
            report.results[sid] = "its tests include Jest tests, which check-break can't run yet (O-RUN1)"
        elif not passes(repo, sid):
            report.results[sid] = "its tests fail on unmutated code"
        elif report.skipped:
            report.results[sid] = None
        elif not files:
            report.results[sid] = "nothing to mutate: the change's premises cite no Python file"
        else:
            made, killed = mutator.kills(files, sid)
            survived = f"its tests survive every mutant ({killed} of {made} killed, in {', '.join(files)})"
            report.results[sid] = None if killed else survived
    return report
