import argparse
from pathlib import Path

from redline.lines import LIMIT, check_lines
from redline.order import check_order


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="redline")
    commands = parser.add_subparsers(dest="command", required=True)
    order = commands.add_parser("check-order", help="prove each scenario was red before green")
    order.add_argument("--repo", type=Path, default=Path.cwd())
    order.add_argument("--rev", default="HEAD")
    lines = commands.add_parser("check-lines", help=f"fail if the change is over {LIMIT} lines")
    lines.add_argument("--repo", type=Path, default=Path.cwd())
    lines.add_argument("--base", help="base ref (default: merge-base with main)")
    args = parser.parse_args(argv)
    if args.command == "check-lines":
        return run_check_lines(args.repo, args.base)

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
