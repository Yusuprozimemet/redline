"""Runners: the test framework a test file belongs to, chosen by its extension. See docs/design.md, §5.

Each knows its test files, its spec marker (the scenario ID, and whether it is `new`) and where each
of its tests starts and ends: pytest's from Python's own parser, Jest's from a scanner that skips
strings, template literals and comments; and the command that runs them. `redline install jest`
writes the Jest helper tests import; `check_helpers`, run by every gate, fails on one that differs
from the copy Redline ships.
"""

import ast
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from fnmatch import fnmatch
from importlib.resources import files
from pathlib import Path

HELPERS = {"jest": "redline/runners/jest.js"}  # runner -> where `redline install` writes its helper
CLOSE = {"(": ")", "[": "]", "{": "}"}


@dataclass(frozen=True)
class Runner:
    name: str
    paths: tuple[str, ...]  # git pathspecs of its test files
    grep: str  # a `git grep -E` pattern for a line with a marker
    call: str  # a Python pattern for the marker's opening, up to its `(`
    new: str  # a Python pattern for the `new` argument after the ID
    tests: Callable[[str, str], Iterator[tuple[str, str, str]]]  # (path, text) -> (name, source, marker text)
    test_files: tuple[str, ...]  # globs of its test files, which check-track doesn't count as code
    needs: str  # the program its command needs on PATH, or ""
    command: Callable[[str | None], tuple[list[str], dict[str, str]]]  # scenario or all -> (argv, env it adds)

    @property
    def ids(self) -> re.Pattern:
        return re.compile(self.call + r"""\s*["']([^"']+)["']""")

    @property
    def marker(self) -> re.Pattern:
        """(scenario ID, the `new` argument or "")."""
        return re.compile(self.call + r"""\s*["']([^"']+)["']\s*(""" + self.new + r""")?\)""")


def functions(tree: ast.AST, prefix: str = ""):
    """(test id within its file, node) for each function, methods as `Class::name`."""
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            yield from functions(node, f"{prefix}{node.name}::")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield prefix + node.name, node


def source(lines: list[str], node: ast.AST) -> str:
    """A node's lines, from its first decorator (if it has any) to its last line."""
    decorators = getattr(node, "decorator_list", None)
    return "\n".join(lines[(decorators[0] if decorators else node).lineno - 1:node.end_lineno])


def python_tests(path: str, text: str) -> Iterator[tuple[str, str, str]]:
    try:
        tree = ast.parse(text, path)
    except SyntaxError as error:
        raise RuntimeError(f"{path}: {error}") from None
    lines = text.split("\n")
    for name, node in functions(tree):
        yield name, source(lines, node), " ".join(ast.get_source_segment(text, d) or "" for d in node.decorator_list)


def closing(text: str, start: int, path: str) -> int:
    """The index of the bracket that closes the one at `start`, skipping strings, templates and comments."""
    stack, i = [], start  # closers expected; "`" while inside a template literal
    while i < len(text):
        c = text[i]
        if stack and stack[-1] == "`":
            if c == "\\":
                i += 1
            elif c == "`":
                stack.pop()
            elif text.startswith("${", i):
                stack.append("}")
                i += 1
        elif c in "\"'":
            i += 1
            while i < len(text) and text[i] not in (c, "\n"):
                i += 2 if text[i] == "\\" else 1
        elif c == "`":
            stack.append("`")
        elif text.startswith("//", i):
            i = text.find("\n", i) % (len(text) + 1)
        elif text.startswith("/*", i):
            i = text.find("*/", i + 2) % (len(text) + 1) + 1
        elif c in CLOSE:
            stack.append(CLOSE[c])
        elif c in ")]}":
            if stack.pop() != c:
                raise RuntimeError(f"{path}:{text.count(chr(10), 0, i) + 1}: `{c}` closes nothing opened")
            if not stack:
                return i
        i += 1
    raise RuntimeError(f"{path}:{text.count(chr(10), 0, start) + 1}: the brackets opened here never close")


TEST_CALL = re.compile(r"""\s*\.test\(\s*(["'])((?:\\.|(?!\1).)*)\1""")


def jest_tests(path: str, text: str) -> Iterator[tuple[str, str, str]]:
    """Each `spec(...).test("name", ...)`, its source from `spec(` to the `)` closing its `test(` call."""
    names = set()
    for found in JEST.marker.finditer(text):
        line = text.count("\n", 0, found.start()) + 1
        if not (call := TEST_CALL.match(text, found.end())):
            raise RuntimeError(f"{path}:{line}: a spec marker must be followed by .test(\"name\", ...)")
        if call[2] in names:
            raise RuntimeError(f"{path}:{line}: two tests named {call[2]!r}")
        names.add(call[2])
        yield call[2], text[found.start():closing(text, text.index("(", found.end()), path) + 1], found[0]


def pytest_command(sid: str | None) -> tuple[list[str], dict[str, str]]:
    spec = [f"--redline-spec={sid}"] if sid else []
    return [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *spec], {"PYTHONDONTWRITEBYTECODE": "1"}


def jest_command(sid: str | None) -> tuple[list[str], dict[str, str]]:
    return [shutil.which("npx") or "npx", "--no-install", "jest", "--ci"], {"REDLINE_SPEC": sid} if sid else {}


JS = ("js", "jsx", "mjs", "cjs", "ts", "tsx")
PYTEST = Runner("pytest", ("*.py",), r"mark\.spec\(", r"mark\.spec\(", r",\s*new\s*=\s*True\s*", python_tests,
                ("test_*.py", "*_test.py", "conftest.py"), "", pytest_command)
JEST = Runner("jest", tuple(f"*.{ext}" for ext in JS),
              r"(^|[^[:alnum:]_.$])spec\(", r"(?<![\w.$])spec\(", r",\s*\{\s*new\s*:\s*true\s*\}\s*", jest_tests,
              tuple(f"*.{kind}.{ext}" for kind in ("test", "spec") for ext in JS) + tuple(f"*__tests__/*.{ext}" for ext in JS),
              "npx", jest_command)
RUNNERS = (PYTEST, JEST)


def run(repo: Path, runner: Runner, sid: str | None = None) -> subprocess.CompletedProcess:
    """Run the runner's tests, or one scenario's alone; its output is decoded as UTF-8 (O-ENC1)."""
    argv, env = runner.command(sid)
    return subprocess.run(argv, cwd=repo, capture_output=True, encoding="utf-8", errors="replace", env={**os.environ, **env})


def runner_for(test: str) -> Runner | None:
    """The runner of a test (`path::name`) or a file, by its extension."""
    path = test.split("::")[0]
    return next((r for r in RUNNERS if any(fnmatch(path, glob) for glob in r.paths)), None)


def shipped(name: str) -> str:
    return files("redline").joinpath("helpers", Path(HELPERS[name]).name).read_text(encoding="utf-8")


def install(repo: Path, name: str) -> str:
    (repo / HELPERS[name]).parent.mkdir(parents=True, exist_ok=True)
    (repo / HELPERS[name]).write_bytes(shipped(name).encode())
    return HELPERS[name]


def check_helpers(repo: Path) -> list[str]:
    """Each helper in the repository that differs from the one Redline ships (line endings aside)."""
    return [f"{path} differs from the helper Redline ships; run `redline install {name}`"
            for name, path in HELPERS.items()
            if (repo / path).is_file() and (repo / path).read_text(encoding="utf-8").replace("\r\n", "\n") != shipped(name)]
