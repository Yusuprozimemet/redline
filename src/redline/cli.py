import argparse
import io
import sys
from pathlib import Path

from redline.audit import check_audit
from redline.breaks import check_break, holds
from redline.ci import ci_pr, ci_push
from redline.claims import claims
from redline.close import check_close, tags
from redline.defects import check_defects, retro
from redline.ledger import check_ledger, declared, write_ledger
from redline.lines import LIMIT, check_lines
from redline.merged import merged
from redline.links import check_links
from redline.approval import Approvals
from redline.lock import check_lock, write_lock
from redline.order import check_order, failed
from redline.plan import check_plan
from redline.planaudit import check_plan_audits
from redline.pr import pr
from redline.premises import check_premises
from redline.relabel import blind, check_relabel
from redline.runner import HELPERS, install
from redline.specs import check_specs
from redline.start import Refused, read_steps, start
from redline.steps import check_steps, since


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):  # a brief printed into a pipe is UTF-8, as on Linux (§7)
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(prog="redline")
    commands = parser.add_subparsers(dest="command", required=True)
    order = commands.add_parser("check-order", help="prove each scenario was red before green")
    order.add_argument("--repo", type=Path, default=Path.cwd())
    order.add_argument("--rev", default="HEAD")
    lines = commands.add_parser("check-lines", help=f"fail if the change is over {LIMIT} lines")
    lines.add_argument("--repo", type=Path, default=Path.cwd())
    lines.add_argument("--base", help="base ref (default: merge-base with main)")
    links = commands.add_parser("check-links", help="link every scenario to a test, both ways")
    links.add_argument("--repo", type=Path, default=Path.cwd())
    cited = commands.add_parser("check-premises", help="check every premise citation in the deltas")
    cited.add_argument("--change", help="check this change only (default: every change)")
    cited.add_argument("--repo", type=Path, default=Path.cwd())
    planned = commands.add_parser("check-plan", help="check the structure of every initiative's plan, or one")
    planned.add_argument("initiative", nargs="?", help="check this initiative only (default: every one)")
    planned.add_argument("--repo", type=Path, default=Path.cwd())
    audit = commands.add_parser("check-audit", help="fail on a missing audit or an unresolved finding")
    audit.add_argument("change", help="the change, e.g. add-greet")
    audit.add_argument("--repo", type=Path, default=Path.cwd())
    for name, help in (("check-steps", "check the form of a change's steps.md against its deltas"),
                       ("check-defects", "check the form of a change's defect log, as at the C step"),
                       ("retro", "group a change's defects by cause and propose rules; writes nothing"),
                       ("blind", "print a change's defect log without its causes, for the relabeller"),
                       ("check-relabel", "compare the blind relabel with the defect log, as at the C step")):
        logged = commands.add_parser(name, help=help)
        logged.add_argument("change", help="the change, e.g. add-greet")
        logged.add_argument("--repo", type=Path, default=Path.cwd())
        if name == "check-steps":
            logged.add_argument("--base", default="main", help="also fail on what left steps.md since the merge-base with this ref")
    closed = commands.add_parser("check-close", help="fail unless main's evidence closes the change, as at the C step")
    closed.add_argument("change", help="the change, e.g. add-greet")
    closed.add_argument("--repo", type=Path, default=Path.cwd())
    closed.add_argument("--base", default="main", help="read the C PR's manual checks from base..HEAD")
    merging = commands.add_parser("check-specs", help="fail unless the deltas, and only they, reached redline/specs")
    merging.add_argument("change", help="the change, e.g. add-greet")
    merging.add_argument("--repo", type=Path, default=Path.cwd())
    merging.add_argument("--base", default="main", help="compare with the merge-base with this ref")
    claimed = commands.add_parser("claims", help="print the claims main's history holds for an initiative")
    claimed.add_argument("initiative", help="the initiative, e.g. 2fa-rollout")
    claimed.add_argument("--repo", type=Path, default=Path.cwd())
    broken = commands.add_parser("check-break", help="prove by mutation that each hold scenario's tests can fail")
    broken.add_argument("change", help="the change, e.g. add-greet")
    broken.add_argument("--repo", type=Path, default=Path.cwd())
    locks = commands.add_parser("lock", help="write a change's hold tests into the contract lock")
    locks.add_argument("change", help="the change, e.g. add-greet")
    locks.add_argument("--repo", type=Path, default=Path.cwd())
    locked = commands.add_parser("check-lock", help="print each difference between the contract lock and the code")
    locked.add_argument("change", help="the change, e.g. add-greet")
    locked.add_argument("--base", help="also fail on lock entries changed since this ref, as G steps do")
    locked.add_argument("--repo", type=Path, default=Path.cwd())
    for name, help in (("ledger", "rebuild a change's ledger.yaml from main's history"),
                       ("check-ledger", "fail if a change's ledger.yaml doesn't match main's history")):
        led = commands.add_parser(name, help=help)
        led.add_argument("change", help="the change, e.g. add-greet")
        led.add_argument("--main", default="main", help="the ref whose history is evidence")
        led.add_argument("--repo", type=Path, default=Path.cwd())
    setup = commands.add_parser("install", help="write a runner's spec helper into the repository")
    setup.add_argument("runner", choices=sorted(HELPERS))
    setup.add_argument("--repo", type=Path, default=Path.cwd())
    begin = commands.add_parser("start", help="start a step on a fresh branch and print its brief")
    begin.add_argument("step", help="<change>/<step>, e.g. add-greet/G1")
    begin.add_argument("--repo", type=Path, default=Path.cwd())
    finish = commands.add_parser("pr", help="run the local gates, then open the open step's PR")
    finish.add_argument("--body", default="", help="text for the PR description")
    finish.add_argument("--repo", type=Path, default=Path.cwd())
    done = commands.add_parser("merged", help="confirm a step merged, sync main, hand off the next")
    done.add_argument("step", help="<change>/<step>, e.g. add-greet/G1")
    done.add_argument("--repo", type=Path, default=Path.cwd())
    ci = commands.add_parser("ci", help="what the GitHub Action runs, on a PR or a push to main")
    ci.add_argument("event", choices=["pr", "push"])
    ci.add_argument("--base", default="main", help="pr: the PR's base ref")
    ci.add_argument("--run-url", default="", help="push: the CI run to record in the note")
    ci.add_argument("--pr", type=int, help="pr: the PR's number, to read its approval labels")
    ci.add_argument("--note", type=Path, help="push: write the note to this file instead of adding and pushing it")
    ci.add_argument("--python", type=Path, help="pr: run the suite with this interpreter, not Redline's own")
    ci.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    if args.command == "ci":
        return run_ci(args.repo, args.event, args.base, args.run_url, args.pr, args.note, args.python)
    if args.command == "install":
        print(f"ok: wrote {install(args.repo, args.runner)}")
        return 0
    if args.command == "merged":
        return run_merged(args.repo, args.step)
    if args.command == "pr":
        return run_pr(args.repo, args.body)
    if args.command == "start":
        return run_start(args.repo, args.step)
    if args.command == "check-lines":
        return run_check_lines(args.repo, args.base)
    if args.command == "check-links":
        return run_check_links(args.repo)
    if args.command == "check-premises":
        return run_check_premises(args.repo, args.change)
    if args.command == "check-plan":
        return run_check_plan(args.repo, args.initiative)
    if args.command == "check-break":
        return run_check_break(args.repo, args.change)
    if args.command == "check-defects":
        return run_check_defects(args.repo, args.change)
    if args.command == "check-steps":
        return run_check_steps(args.repo, args.change, args.base)
    if args.command in ("retro", "blind"):
        return run_retro(args.repo, args.change, retro if args.command == "retro" else blind)
    if args.command == "claims":
        return run_retro(args.repo, args.initiative, claims)
    if args.command == "check-close":
        return run_check_close(args.repo, args.change, args.base)
    if args.command == "check-specs":
        return run_check_specs(args.repo, args.change, args.base)
    if args.command == "check-relabel":
        return run_check_relabel(args.repo, args.change)
    if args.command in ("lock", "check-lock"):
        return run_lock(args.repo, args.change, getattr(args, "base", None), args.command == "check-lock")
    if args.command == "check-audit":
        return run_check_audit(args.repo, args.change)
    if args.command in ("ledger", "check-ledger"):
        return run_ledger(args.repo, args.change, args.main, args.command == "check-ledger")

    notes: list[str] = []
    try:
        results = check_order(args.repo, args.rev, notes=notes)
        bad = failed(results, set(holds(args.repo)))  # the gate's own count (O-SELF5)
    except RuntimeError as error:
        print(f"redline: {error}")
        return 2
    for note in notes:
        print(note)
    for r in results:
        if r.status == "ok":
            print(f"ok {r.scenario}: red {r.red[:7]} is an ancestor of green {r.green[:7]}")
        elif r.status == "pending":
            print(f"pending {r.scenario}: red {r.red[:7]}, no green yet")
        elif r in bad:
            print(f"FAIL {r.scenario}: green {r.green[:7]} has no red commit among its ancestors")
        elif not r.linked:
            print(f"skipped {r.scenario}: no test at {args.rev} links it; its green {r.green[:7]} had no red")
        else:
            print(f"hold {r.scenario}: no red by design")
    return 1 if bad else 0


def run_check_lines(repo: Path, base: str | None) -> int:
    try:
        count = check_lines(repo, base)
    except RuntimeError as error:
        print(f"redline: {error}")
        return 2
    for path in count.excluded:
        print(f"excluded {path} (generated)")
    if count.total > LIMIT:
        print(f"FAIL: {count.total} changed lines since {count.base[:7]}, over the limit of {LIMIT}")
        return 1
    print(f"ok: {count.total} changed lines since {count.base[:7]} (limit {LIMIT})")
    return 0


def run_start(repo: Path, step: str) -> int:
    try:
        print(start(repo, step), end="")
    except Refused as reason:
        print(f"refused: {reason}")
        return 1
    except RuntimeError as error:
        print(f"redline: {error}")
        return 2
    return 0


def run_merged(repo: Path, step: str) -> int:
    try:
        print(merged(repo, step), end="")
    except Refused as reason:
        print(f"refused: {reason}")
        return 1
    except RuntimeError as error:
        print(f"redline: {error}")
        return 2
    return 0


def run_pr(repo: Path, body: str) -> int:
    try:
        url, pending = pr(repo, body)
        for note in pending:
            print(f"note: {note}")
        print(f"ok: opened {url}")
    except Refused as reason:
        print(f"refused: {reason}")
        return 1
    except RuntimeError as error:
        print(f"redline: {error}")
        return 2
    return 0


def run_check_links(repo: Path) -> int:
    try:
        report = check_links(repo)
    except RuntimeError as error:
        print(f"redline: {error}")
        return 2
    for gap in report.gaps:
        print(gap)
    if report.gaps:
        return 1
    print(f"ok: {report.scenarios} scenarios, each linked to a test" + (f", except {report.manual} manual" if report.manual else ""))
    return 0


def run_check_premises(repo: Path, change: str | None) -> int:
    try:
        report = check_premises(repo, change)
    except RuntimeError as error:
        print(f"redline: {error}")
        return 2
    for bad in report.bad:
        print(bad)
    if report.bad:
        return 1
    n = report.citations
    print(f"ok: {n} premise citation{' resolves' if n == 1 else 's resolve'}")
    return 0


def run_check_plan(repo: Path, initiative: str | None) -> int:
    try:
        report = check_plan(repo, initiative)
        report.bad += check_plan_audits(repo, initiative)
    except RuntimeError as error:
        print(f"redline: {error}")
        return 2
    for bad in report.bad:
        print(bad)
    if report.bad:
        return 1
    print(f"ok: {report.plans} initiative{'' if report.plans == 1 else 's'}, "
          f"{report.phases} phase{'' if report.phases == 1 else 's'}")
    return 0


def run_check_audit(repo: Path, change: str) -> int:
    try:
        report = check_audit(repo, change)
    except RuntimeError as error:
        print(f"redline: {error}")
        return 2
    for bad in report.bad:
        print(bad)
    if report.bad:
        return 1
    print(f"ok: {report.findings} finding{'' if report.findings == 1 else 's'}, none open")
    return 0


def run_check_defects(repo: Path, change: str) -> int:
    try:
        report = check_defects(repo, change)
    except RuntimeError as error:
        print(f"redline: {error}")
        return 2
    for bad in report.bad:
        print(bad)
    if report.bad:
        return 1
    n = len(report.defects)
    print(f"ok: {n} defect{'' if n == 1 else 's'}, each with a cause and what found it")
    return 0


def run_check_steps(repo: Path, change: str, base: str = "main") -> int:
    if bad := check_steps(repo, change) + since(repo, change, base):
        for line in bad:
            print(line)
        return 1
    steps = read_steps(repo, change)
    n, items = len(steps), sum(len(s.items) for s in steps)
    print(f"ok: {n} step{'' if n == 1 else 's'}, {items} open item{'' if items == 1 else 's'}")
    return 0


def run_check_close(repo: Path, change: str, base: str) -> int:
    approvals = Approvals()
    try:
        bad = check_close(repo, change, approvals=approvals, base=base)
        count = len(declared(repo, change))
    except RuntimeError as error:
        print(f"redline: {error}")
        return 2
    for line in bad:
        print(line)
    for note in approvals.pending:
        print(f"note: {note}")
    if bad:
        return 1
    manual = list(tags(repo, change).values()).count("manual")
    evidence = f": {count - manual} on main, {manual} checked by a person" if manual else " on main"
    print(f"ok: {count} scenario{'' if count == 1 else 's'}, each with its evidence{evidence}")
    return 0


def run_check_specs(repo: Path, change: str, base: str) -> int:
    try:
        bad, counts = check_specs(repo, change, base)
    except RuntimeError as error:
        print(f"redline: {error}")
        return 2
    for line in bad:
        print(line)
    if bad:
        return 1
    print(f"ok: {counts['ADDED']} added, {counts['MODIFIED']} modified, {counts['REMOVED']} removed, "
          "as the deltas say; nothing else in redline/specs changed")
    return 0


def run_check_relabel(repo: Path, change: str) -> int:
    try:
        report = check_relabel(repo, change)
    except RuntimeError as error:
        print(f"redline: {error}")
        return 2
    for line in report.disagreements + report.bad:
        print(line)
    if report.bad:
        return 1
    n = len(report.disagreements)
    print(f"ok: {report.labelled} defects relabelled blind, {n} disagreement{'' if n == 1 else 's'}")
    return 0


def run_retro(repo: Path, change: str, make=retro) -> int:
    try:
        print(make(repo, change), end="")
    except Refused as reason:
        print(f"refused: {reason}")
        return 1
    except RuntimeError as error:
        print(f"redline: {error}")
        return 2
    return 0


def run_check_break(repo: Path, change: str) -> int:
    try:
        report = check_break(repo, change)
    except RuntimeError as error:
        print(f"redline: {error}")
        return 2
    for sid, why in report.bad.items():
        print(f"{sid}: {why}")
    if report.bad:
        return 1
    for sid, why in report.skipped.items():
        print(f"skipped {sid}: {why}; CI runs the mutation")
    proved = "" if report.skipped else " and fail under a mutant"
    print(f"ok: {len(report.results)} hold scenario(s): tests pass unmutated{proved}")
    return 0


def run_lock(repo: Path, change: str, base: str | None, check: bool) -> int:
    try:
        if not check:
            print(f"ok: locked {write_lock(repo, change)} hold test(s) of {change}")
            return 0
        approvals = Approvals()
        report = check_lock(repo, change, base, approvals)
    except RuntimeError as error:
        print(f"redline: {error}")
        return 2
    for bad in report.bad:
        print(bad)
    for note in approvals.pending:
        print(f"note: {note}")
    if report.bad:
        return 1
    print(f"ok: {report.locked} locked test(s) match the code")
    return 0


def run_ledger(repo: Path, change: str, main: str, check: bool) -> int:
    try:
        if not check:
            data = write_ledger(repo, change, main)
            print(f"ok: wrote the ledger of {change}, {len(data['scenarios'])} scenarios")
            return 0
        problems = check_ledger(repo, change, main)
        count = len(declared(repo, change))
    except RuntimeError as error:
        print(f"redline: {error}")
        return 2
    for problem in problems:
        print(problem)
    if problems:
        return 1
    print(f"ok: {count} scenario{' matches' if count == 1 else 's match'} the history of {main}")
    return 0


def run_ci(repo: Path, event: str, base: str, run_url: str, number: int | None, to: Path | None = None,
           python: Path | None = None) -> int:
    if python and event != "pr":
        print("redline: --python is for ci pr only: a push run's suite is the merged code's own")
        return 2
    if python and not python.is_file():
        print(f"redline: --python {python} isn't a file")
        return 2
    try:
        if event == "pr":
            name, failures = ci_pr(repo, base, number, str(python) if python else None)
            done = (f"ok: {name} passes the gates, the test suite and check-ledger" if name else
                    "ok: a PR outside any step passes check-lines, check-plan, check-lock and the test suite")
        else:
            failures = ci_push(repo, run_url, to=to)
            done = f"ok: the test suite passed; {f'the note is in {to}' if to else 'noted on refs/notes/redline-ci'}"
    except Refused as reason:
        print(f"refused: {reason}")
        return 1
    except RuntimeError as error:
        print(f"redline: {error}")
        return 2
    for failure in failures:
        print(failure)
    if failures:
        return 1
    print(done)
    return 0
