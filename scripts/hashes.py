"""Writes each pin's `--hash` lines in the requirements files CI installs from (specs/, section 7).

For each `name==version` line it asks PyPI for that release's files and keeps the sha256 of every wheel that installs
on one of CI's Pythons: CPython 3.12 on Linux x86_64 (ubuntu-24.04's glibc, 2.39) and on Windows x64. Every other line
is kept. Usage: python scripts/hashes.py requirements-pip.txt requirements.txt
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

from packaging.tags import compatible_tags, cpython_tags
from packaging.utils import parse_wheel_filename

LINUX = [f"manylinux_2_{minor}_x86_64" for minor in range(39, 4, -1)]
LINUX += ["manylinux2014_x86_64", "manylinux2010_x86_64", "manylinux1_x86_64"]
TAGS = {tag for platforms in (LINUX, ["win_amd64"]) for tags in (cpython_tags, compatible_tags)
        for tag in tags((3, 12), platforms=platforms)}
PIN = re.compile(r"[A-Za-z0-9._-]+==[\w.]+(?: ?;.*)?")


def release(name: str, version: str) -> list[dict]:
    """The files PyPI holds for a release, each with its `filename` and `digests`."""
    with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/{version}/json") as response:
        return json.load(response)["urls"]


def fitting(files: list[dict]) -> list[str]:
    """The sha256 of each wheel among a release's files that installs on one of CI's Pythons, sorted; never an sdist."""
    return sorted(f["digests"]["sha256"] for f in files
                  if f["filename"].endswith(".whl") and TAGS & parse_wheel_filename(f["filename"])[3])


def rewrite(text: str, files=release) -> str:
    """The file with every pin followed by its hashes, old ones dropped; a pin no wheel fits, or a line that is neither
    a pin nor a comment, is an error."""
    out = []
    for line in text.splitlines():
        line = line.removesuffix("\\").rstrip()
        if line.lstrip().startswith("--hash="):
            continue
        if not line or line.startswith("#"):
            out.append(line)
            continue
        if not PIN.fullmatch(line):
            raise ValueError(f"not a pin: {line}")
        name, _, rest = line.partition("==")
        hashes = fitting(files(name, re.match(r"[\w.]+", rest).group()))
        if not hashes:
            raise ValueError(f"no wheel for CI's Pythons: {line}")
        out.append(f"{line} \\")
        out += [f"    --hash=sha256:{digest} \\" for digest in hashes]
        out[-1] = out[-1].removesuffix(" \\")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    for path in map(Path, sys.argv[1:]):
        path.write_text(rewrite(path.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
