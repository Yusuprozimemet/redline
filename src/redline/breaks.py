"""`redline check-break <change>`: mutation proves each `hold` scenario's tests can fail.

Its tests (spec marker without `new=True`) must pass unmutated, and fail under at least one mutant
of the files its premises cite, mutated by their runner's tool. Each tool is in `MUTATORS`, keyed
by runner name, which tests replace whole: mutmut for pytest, which doesn't run on Windows, so there
the mutation is skipped (CI runs it), and Stryker for Jest. See specs/, §5.
"""

import configparser
import contextlib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from redline.config import load_config
from redline.lines import is_generated
from redline.links import SPEC_PATHS, declarations, grep
from redline.premises import CITATION, premise_lines
from redline.runner import RUNNERS, Runner, run, runner_for

HOLD = re.compile(r"^#### Scenario (\S+) \[hold\]:")
UNCOPIED = (".git", ".venv", "mutants")
TABLE = re.compile(r"\s*\[\[?[^\[\]=]+\]\]?\s*(#.*)?$")  # a table's header line
MUTMUT_TABLE = re.compile(r"\s*\[\[?\s*tool\s*\.\s*mutmut\s*[\].]")  # [tool.mutmut] or one of its subtables


def without_mutmut(pyproject: Path) -> None:
    """Take `[tool.mutmut]` out of the copy's pyproject.toml, which mutmut would read instead of setup.cfg.
    Python's TOML parser checks that only that table went; when it can't be taken out by its headers, an error."""
    if not pyproject.is_file():
        return
    text = pyproject.read_text(encoding="utf-8")
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise RuntimeError(f"pyproject.toml: {e}") from None
    if not (isinstance(tool := data.get("tool"), dict) and "mutmut" in tool):
        return
    kept, inside = [], False
    for line in text.splitlines(keepends=True):
        if TABLE.match(line):
            inside = bool(MUTMUT_TABLE.match(line))
        if not inside:
            kept.append(line)
    del tool["mutmut"]
    if not tool:
        del data["tool"]
    try:
        left = tomllib.loads("".join(kept))
    except tomllib.TOMLDecodeError:
        left = None
    if left != data:
        raise RuntimeError("can't take [tool.mutmut] out of pyproject.toml by its table headers, "
                           "and mutmut would read its settings instead of Redline's")
    pyproject.write_text("".join(kept), encoding="utf-8", newline="")


def package(copy: Path, path: str) -> PurePosixPath | None:
    """The outermost package holding `path`: the highest of its directories with an __init__.py, all of them up to it."""
    top = None
    for parent in (p for p in PurePosixPath(path).parents if p.name):
        if not (copy / parent / "__init__.py").is_file():
            break
        top = parent
    return top


def copied(copy: Path, tests: list[str], mutated: list[str] = ()) -> list[str]:
    """mutmut's `also_copy`: the directory of each of the scenario's tests, of each conftest.py from the root down
    to them and of each `support:` file, or the file itself at the root, since mutmut makes no directory for a file;
    and the outermost package of each mutated file, whose copy would otherwise be a namespace portion (O-MUT3)."""
    files = set(tests) | {(top / "__init__.py").as_posix() for path in mutated if (top := package(copy, path))}
    for test in tests:
        files |= {(parent / "conftest.py").as_posix() for parent in PurePosixPath(test).parents
                  if (copy / parent / "conftest.py").is_file()}
    if support := load_config(copy).support:
        for root, dirs, names in os.walk(copy):
            dirs[:] = [d for d in dirs if d not in UNCOPIED]
            relative = (Path(root, name).relative_to(copy).as_posix() for name in names)
            files |= {path for path in relative if is_generated(path, support)}
    return sorted({path.rpartition("/")[0] or path for path in files})


class Mutmut:
    """pytest's mutation tool: mutmut, run in a throwaway copy of the repository."""

    def __init__(self, repo: Path):
        self.repo = repo

    def unavailable(self) -> str | None:
        if sys.platform == "win32":
            return "mutmut doesn't run on Windows"
        return None if shutil.which("mutmut") else "mutmut isn't installed"

    def kills(self, files: list[str], sid: str, tests=()) -> tuple[int, int]:
        """(mutants made from `files`, mutants that made the scenario's tests, in the files `tests`, fail),
        with Redline's settings alone, so no other test's kill counts."""
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "repo"
            shutil.copytree(self.repo, copy, ignore=shutil.ignore_patterns(*UNCOPIED))
            without_mutmut(copy / "pyproject.toml")
            config = configparser.ConfigParser()
            config.read(copy / "setup.cfg", encoding="utf-8")
            config["mutmut"] = {"source_paths": "\n".join(files), "pytest_add_cli_args": f"--redline-spec={sid}"}
            if also := copied(copy, list(tests), files):  # never empty: mutmut reads "" as ".", the whole copy
                config["mutmut"]["also_copy"] = "\n".join(also)
            with open(copy / "setup.cfg", "w", encoding="utf-8") as out:
                config.write(out)
            for command in (["mutmut", "run"], ["mutmut", "results", "--all", "true"]):
                done = subprocess.run(command, cwd=copy, capture_output=True, encoding="utf-8", errors="replace")
                if done.returncode:
                    raise RuntimeError(f"{' '.join(command)}: {(done.stderr or done.stdout).strip()[-500:]}")
        statuses = [line.rpartition(": ")[2].strip() for line in done.stdout.splitlines() if "__mutmut_" in line]
        return len(statuses), statuses.count("killed")


class Stryker:
    """Jest's mutation tool: Stryker, which mutates in its own sandbox. Its JSON report is read, then deleted."""

    REPORT = Path("reports/mutation/mutation.json")
    PACKAGES = ("@stryker-mutator/core", "@stryker-mutator/jest-runner")
    MADE = ("Killed", "Survived", "NoCoverage", "Timeout")  # not CompileError, RuntimeError, Ignored, Pending

    def __init__(self, repo: Path):
        self.repo = repo

    def unavailable(self) -> str | None:
        if not shutil.which("npx"):
            return "npx isn't installed"
        missing = (p for p in self.PACKAGES if not (self.repo / "node_modules" / p).is_dir())
        return next((f"{p} isn't installed" for p in missing), None)

    def kills(self, files: list[str], sid: str, tests=()) -> tuple[int, int]:
        """(mutants made from `files`, mutants that made the scenario's tests fail); a timeout isn't a kill.
        Its sandbox holds the whole project, so it needs no `tests`."""
        argv = [shutil.which("npx"), "--no-install", "stryker", "run", "--mutate", ",".join(files),
                "--testRunner", "jest", "--reporters", "json"]
        done = subprocess.run(argv, cwd=self.repo, capture_output=True, encoding="utf-8", errors="replace",
                              env={**os.environ, "REDLINE_SPEC": sid})
        report = self.repo / self.REPORT
        try:
            if done.returncode:
                raise RuntimeError(f"stryker run: {(done.stderr or done.stdout).strip()[-500:]}")
            found = json.loads(report.read_text(encoding="utf-8"))["files"].values()
        finally:
            shutil.rmtree(report.parent, ignore_errors=True)
            with contextlib.suppress(OSError):
                report.parent.parent.rmdir()  # reports/, unless something else is in it
        made = [m["status"] for f in found for m in f["mutants"] if m["status"] in self.MADE]
        return len(made), made.count("Killed")


MUTATORS = {"pytest": Mutmut, "jest": Stryker}  # runner name -> its mutation tool


@dataclass
class BreakReport:
    results: dict[str, str | None] = field(default_factory=dict)  # hold scenario -> why it isn't proved
    skipped: dict[str, str] = field(default_factory=dict)  # hold scenario -> why its mutation was skipped

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
                for mark in marks:
                    if not mark.new and mark.sid in found:
                        found[mark.sid][f"{path}::{name}"] = digest
    return found


def touched(repo: Path, change: str, runner: Runner) -> list[str]:
    """The files the change's premises cite that are `runner`'s: the code its R step's tests protect."""
    cited = {path for _, _, text in premise_lines(repo, change) for path, *_ in CITATION.findall(text)}
    return sorted(p for p in cited if runner_for(p) is runner and (repo / p).is_file())


def passes(repo: Path, runner: Runner, sid: str) -> bool:
    return run(repo, runner, sid).returncode == 0


def unmutated(repo: Path, runner: Runner, sid: str) -> str | None:
    """Why the scenario's tests of this runner don't pass on today's code, or None."""
    if runner.needs and not shutil.which(runner.needs):
        return f"its {runner.name} tests can't run: {runner.needs} isn't installed"
    return None if passes(repo, runner, sid) else f"its {runner.name} tests fail on unmutated code"


def mutate(repo: Path, change: str, sid: str, runners: list[Runner], tests: list[str],
           report: BreakReport) -> str | None:
    """Each runner's tool on its cited files until a mutant is killed: why the scenario isn't proved, or None."""
    made = killed = 0
    files, skipped = [], []
    for runner in runners:
        if not (mine := touched(repo, change, runner)):
            continue
        files += mine
        tool = MUTATORS[runner.name](repo)
        if why := tool.unavailable():
            skipped.append(why)
            continue
        more, kills = tool.kills(mine, sid, sorted({t.partition('::')[0] for t in tests if runner_for(t) is runner}))
        made, killed = made + more, killed + kills
        if killed:
            return None
    if skipped:  # nothing killed, and a tool CI has didn't run here
        report.skipped[sid] = "; ".join(skipped)
        return None
    if not files:
        return "nothing to mutate: the change's premises cite no file its tests' runners mutate"
    return f"its tests survive every mutant ({killed} of {made} killed, in {', '.join(files)})"


def check_break(repo: Path, change: str) -> BreakReport:
    report = BreakReport()
    for sid, tests in hold_tests(repo, change).items():
        runners = [r for r in RUNNERS if any(runner_for(test) is r for test in tests)]
        if not tests:
            report.results[sid] = "no test links it without new=True"
        elif failed := next((why for r in runners if (why := unmutated(repo, r, sid))), None):
            report.results[sid] = failed
        else:
            report.results[sid] = mutate(repo, change, sid, runners, list(tests), report)
    return report
