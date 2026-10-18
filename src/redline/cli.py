import argparse
from pathlib import Path

from redline.order import check_order


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="redline")
    commands = parser.add_subparsers(dest="command", required=True)
    order = commands.add_parser("check-order", help="prove each scenario was red before green")
    order.add_argument("--repo", type=Path, default=Path.cwd())
    order.add_argument("--rev", default="HEAD")
    args = parser.parse_args(argv)

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
