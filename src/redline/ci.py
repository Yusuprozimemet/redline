"""`redline ci`: what the GitHub Action runs (.github/workflows/redline.yml).

On a pull request, the step comes from the `Redline-Step` trailers of the PR's commits (base..HEAD),
which must name at most one step, and that step must be the change's next, as `start` checks: in its
steps.md at the merge-base (only S when there is none), every step before it merged on the base, and
itself not merged; and its phase ready, as `start` refuses, with the plans, the changes' steps.md, their
levels and the plan audits read at the merge-base. Then the step's gates, the test suite (each runner's the
repository uses, which fails when none is or when Jest is listed but can't run) and check-ledger against
the base run, and every failure is reported. A PR with no trailer is outside any step: it may not
touch a change, the lock or the specs, and gets check-lines, the rigor claim, check-plan, check-lock
on every locked change and the suite; a `Redline-Manual` trailer fails there, as it is a C step's.
A departure, an Oversized trailer or a manual check needs its label
on the PR (`--pr <number>`), read through `GitHub`. On a push to main, the suite runs and its result is
recorded as a git note on the merged commit under refs/notes/redline-ci, which is then pushed.
When the push merged an R step, check-break runs too, and the note gets each `hold` scenario's
result under `break:`; a failed break fails the run. When the merged commits carry claim trailers,
the note also gets `claims:`, each claim with its label on the merged PR, who applied it last and their
role, read through `GitHub` (claims.record); a re-run keeps an earlier record, and a failed read
writes none and fails the run. With `--note <file>` the note goes to the file, and nothing is added or
pushed: the workflow's read-only job runs it so, and a job that runs no repository code writes the note.
Pushing sits behind `Remote`, which tests replace.
"""

import json
import shutil
from pathlib import Path

import yaml

from redline.breaks import check_break
from redline.claims import note, record
from redline.close import misplaced
from redline.ledger import NOTES, check_ledger
from redline.lines import is_generated
from redline.lock import check_lock, read_lock
from redline.order import git
from redline.approval import Approvals
from redline.plan import check_plan
from redline.planaudit import check_plan_audits
from redline.pr import GitHub, gates, rigor_claim, size, touched
from redline.runner import JEST, RUNNERS, Runner, check_helpers, run
from redline.start import TRAILER, Refused, may_begin, merged_steps, next_step

STEPS_ONLY = ("redline/changes/", "redline/contracts/", "redline/specs/")  # written only by a step's gates


class Remote:
    """Everything that goes over the network."""

    def __init__(self, repo: Path):
        self.repo = repo

    def push_notes(self) -> None:
        done = git(self.repo, "push", "origin", f"refs/notes/{NOTES}")
        if done.returncode:
            raise RuntimeError(f"git push refs/notes/{NOTES}: {done.stderr.strip()}")


def uses(repo: Path, runner: Runner) -> bool:
    """Jest when the root package.json lists it; pytest when git tracks one of its test files."""
    if runner is JEST:
        package = repo / "package.json"
        listed = json.loads(package.read_text(encoding="utf-8")) if package.is_file() else {}
        return any("jest" in (listed.get(key) or {}) for key in ("dependencies", "devDependencies"))
    return any(is_generated(path, list(runner.test_files)) for path in git(repo, "ls-files").stdout.splitlines())


def suite(repo: Path) -> list[str]:
    """Run every test of each runner the repository uses; a failure is the one line that says so."""
    used = [r for r in RUNNERS if uses(repo, r)]
    if not used:
        return ["suite: no tests ran: git tracks no pytest test file, and package.json doesn't list jest"]
    failures = []
    for runner in used:
        if runner.needs and not shutil.which(runner.needs):
            failures.append(f"suite: {runner.name} is listed in package.json, but {runner.needs} isn't installed")
        elif runner is JEST and not (repo / "node_modules" / "jest").is_dir():
            failures.append("suite: jest is listed in package.json, but node_modules/jest isn't installed")
        elif (done := run(repo, runner)).returncode:
            last = next((line for line in reversed(f"{done.stdout}\n{done.stderr}".splitlines()) if line.strip()), "")
            failures.append(f"suite: the test suite failed ({runner.name} exit {done.returncode}): {last.strip('= ')}")
    return failures


def pr_step(repo: Path, base: str) -> str:
    """The one step base..HEAD's trailers name, or "" when no commit carries one."""
    log = git(repo, "log", f"{base}..HEAD", f"--format=%(trailers:key={TRAILER},valueonly,separator=|)")
    if log.returncode:
        raise RuntimeError(log.stderr.strip())
    steps = sorted({s.strip() for line in log.stdout.splitlines() for s in line.split("|") if s.strip()})
    if not steps:
        return ""
    if len(steps) > 1:
        raise Refused(f"more than one step in {base}..HEAD: {', '.join(steps)}")
    if "/" not in steps[0]:
        raise Refused(f"{TRAILER}: {steps[0]} is not <change>/<step>")
    return steps[0]


def outside(repo: Path, base: str, approvals: Approvals) -> list[str]:
    """A PR outside any step: refused if it touches a step's files, else the gates for any PR."""
    if files := touched(repo, base, STEPS_ONLY):
        raise Refused(f"outside any step a PR can't touch a change, the lock or the specs: {', '.join(files)}")
    failures = size(repo, approvals) + rigor_claim(repo, approvals) + misplaced(repo, base)
    failures += [f"check-plan: {bad}" for bad in check_plan(repo).bad + check_plan_audits(repo)]
    failures += [f"check-helpers: {bad}" for bad in check_helpers(repo)]
    for change in sorted(read_lock(repo)):  # no Redline-Step, so no departure: the lock can't change here
        failures += [f"check-lock: {change}: {bad}" for bad in check_lock(repo, change).bad]
    return failures + suite(repo)


def ci_pr(repo: Path, base: str, number: int | None = None) -> tuple[str, list[str]]:
    name = pr_step(repo, base)
    approvals = Approvals(GitHub(repo), number)
    if not name:
        return "", outside(repo, base, approvals)
    fork = next_step(repo, name, base)  # before any gate: a step's name decides which gates run
    change, _, step = name.partition("/")
    may_begin(repo, change, merged_steps(repo, base), fork)  # start's phase refusals, read where the PR can't edit
    failures = gates(repo, change, step, approvals) + suite(repo)
    failures += [f"check-ledger: {p}" for p in check_ledger(repo, change, base)]
    return name, failures


def ci_push(repo: Path, run_url: str, rev: str = "HEAD", to: Path | None = None) -> list[str]:
    """`to`: write the note there instead, for a job that runs no repository code to add and push."""
    failures = suite(repo)
    message = f"result: {'fail' if failures else 'pass'}\nrun: {run_url}\n"
    change, _, step = pr_step(repo, f"{rev}^").partition("/")  # "" when no step merged here
    if step == "R":
        report = check_break(repo, change)
        failures += [f"check-break: {sid}: {why}" for sid, why in report.bad.items()]
        failures += [f"check-break: {sid}: not mutated: {why}" for sid, why in report.skipped.items()]
        broken = {sid: "fail" if why or sid in report.skipped else "pass" for sid, why in report.results.items()}
        message += yaml.safe_dump({"break": broken}, sort_keys=False) if broken else ""
    if not (made := (note(repo, rev) or {}).get("claims")):  # a re-run keeps the labels read at the merge
        try:
            made = record(repo, rev, GitHub(repo))
        except RuntimeError as error:
            failures.append(f"claims: could not read the merged PR's labels: {error}")
    message += yaml.safe_dump({"claims": made}, sort_keys=False, width=1000) if made else ""
    if to:
        to.write_text(message, encoding="utf-8", newline="\n")
        return failures
    noted = git(repo, "-c", "user.name=redline-ci", "-c", "user.email=redline-ci@users.noreply.github.com",
                "notes", f"--ref={NOTES}", "add", "-f", "-m", message, rev)
    if noted.returncode:
        raise RuntimeError(f"could not write the CI note: {noted.stderr.strip()}")
    Remote(repo).push_notes()
    return failures
