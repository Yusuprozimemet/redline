import argparse
from pathlib import Path

from redline.lines import LIMIT, check_lines
from redline.merged import merged
from redline.links import check_links
from redline.order import check_order
from redline.pr import pr
from redline.start import Refused, start


def main(argv: list[str] | None = None) -> int:
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
    begin = commands.add_parser("start", help="start a step on a fresh branch and print its brief")
    begin.add_argument("step", help="<change>/<step>, e.g. add-greet/G1")
    begin.add_argument("--repo", type=Path, default=Path.cwd())
    finish = commands.add_parser("pr", help="run the local gates, then open the open step's PR")
    finish.add_argument("--body", default="", help="text for the PR description")
    finish.add_argument("--repo", type=Path, default=Path.cwd())
    done = commands.add_parser("merged", help="confirm a step merged, sync main, hand off the next")
    done.add_argument("step", help="<change>/<step>, e.g. add-greet/G1")
    done.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
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

    try:
        results = check_order(args.repo, args.rev)
    except RuntimeError as error:
        print(f"redline: {error}")
        return 2
    for r in results:
        if r.status == "ok":
            print(f"ok {r.scenario}: red {r.red[:7]} is an ancestor of green {r.green[:7]}")
        elif r.status == "pending":
            print(f"pending {r.scenario}: red {r.red[:7]}, no green yet")
        else:
            print(f"FAIL {r.scenario}: green {r.green[:7]} has no red commit among its ancestors")
    return 1 if any(r.status == "fail" for r in results) else 0


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
        print(f"ok: opened {pr(repo, body)}")
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
    print(f"ok: {report.scenarios} scenarios, each linked to a test")
    return 0
