"""Runners: the test framework a test file belongs to, chosen by its extension. See specs/, §5.

Each knows its test files, where each of its tests starts and ends, and the spec markers on each (the
scenario ID, and whether it is `new`): pytest's from Python's own parser, a marker counting only as a
test function's decorator; Jest's from `spec(` calls in code, found by a scanner that blanks comments, strings and templates;
and the command that runs them, pytest's with Redline's own Python unless `interpreter` gives another. check-links, check-order and the lock all read markers through it. `redline install jest`
writes the Jest helper tests import; `check_helpers`, run by every gate, fails on one that differs
from the copy Redline ships. `redline install workflow` writes the adopting repository's CI from the
template beside the helpers (§7).
"""

import ast
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from fnmatch import fnmatch
from importlib.metadata import distribution
from importlib.resources import files
from pathlib import Path
from typing import NamedTuple

HELPERS = {"jest": "redline/runners/jest.js", "jest-reporter": "redline/runners/jest-reporter.js"}
WORKFLOW = ".github/workflows/redline.yml"  # `redline install workflow`'s, the one path a note checks out from
CLOSE = {"(": ")", "[": "]", "{": "}"}


class Mark(NamedTuple):
    sid: str
    new: bool
    line: int


@dataclass(frozen=True)
class Runner:
    name: str
    paths: tuple[str, ...]  # git pathspecs of its test files
    grep: str  # a pattern, for `git grep -E` and Python alike, for a line that may hold a marker
    tests: Callable[[str, str], Iterator[tuple[str, str, tuple[Mark, ...]]]]  # (path, text) -> (name, source, its markers)
    test_files: tuple[str, ...]  # globs of its test files, which check-track doesn't count as code
    needs: str  # the program its command needs on PATH, or ""
    command: Callable[[str | None], tuple[list[str], dict[str, str]]]  # scenario or all -> (argv, env it adds)


def markers(runner: Runner, path: str, text: str) -> tuple[Mark, ...]:
    """Every spec marker in a file, as its runner reads them; RuntimeError when it can't read the file."""
    if not re.search(runner.grep, text, re.M):
        return ()
    return tuple(mark for _, _, marks in runner.tests(path, text) for mark in marks)


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


def spec_mark(node: ast.expr) -> Mark | None:
    """The decorator as a marker when it is `….mark.spec("ID")`, or with `new=True`, as pytest reads it."""
    func = node.func if isinstance(node, ast.Call) else None
    owner = getattr(func, "value", None)
    if not (isinstance(func, ast.Attribute) and func.attr == "spec"
            and (getattr(owner, "attr", None) == "mark" or getattr(owner, "id", None) == "mark")):
        return None
    if not (node.args and isinstance(node.args[0], ast.Constant) and isinstance(sid := node.args[0].value, str)):
        return None
    new = any(k.arg == "new" and isinstance(k.value, ast.Constant) and k.value.value is True for k in node.keywords)
    return Mark(sid, new, node.lineno)


def python_tests(path: str, text: str) -> Iterator[tuple[str, str, tuple[Mark, ...]]]:
    try:
        tree = ast.parse(text, path)
    except SyntaxError as error:
        raise RuntimeError(f"{path}: {error}") from None
    lines = text.split("\n")
    for name, node in functions(tree):
        yield name, source(lines, node), tuple(mark for d in node.decorator_list if (mark := spec_mark(d)))


def line(text: str, at: int) -> int:
    return text.count("\n", 0, at) + 1


def blank(text: str, path: str) -> str:
    """The text with its comments and the contents of its strings and templates as spaces, each offset and
    newline kept; a template's `${…}` stays code. A template or block comment that never closes is an error."""
    out, stack, i = list(text), [], 0  # (opener, offset): "`" a template, "${" its code, "{" a brace

    def space(a: int, b: int) -> None:
        for k in range(a, min(b, len(text))):
            if out[k] != "\n":
                out[k] = " "

    while i < len(text):
        c = text[i]
        if stack and stack[-1][0] == "`":
            if c == "`":
                stack.pop()
            elif text.startswith("${", i):
                stack.append(("${", i))
                i += 1
            else:
                space(i, i + (2 if c == "\\" else 1))
                i += 1 if c == "\\" else 0
        elif c in "\"'":
            j = i + 1
            while j < len(text) and text[j] not in (c, "\n"):
                j += 2 if text[j] == "\\" else 1
            space(i + 1, j)
            i = j
        elif c == "`":
            stack.append(("`", i))
        elif text.startswith("//", i):
            j = text.find("\n", i) % (len(text) + 1)
            space(i, j)
            i = j
            continue
        elif text.startswith("/*", i):
            if (j := text.find("*/", i + 2)) < 0:
                raise RuntimeError(f"{path}:{line(text, i)}: the comment opened here never closes")
            space(i, j + 2)
            i = j + 1
        elif c == "{":
            stack.append(("{", i))
        elif c == "}" and stack:
            stack.pop()
        i += 1
    if templates := [at for opener, at in stack if opener == "`"]:
        raise RuntimeError(f"{path}:{line(text, templates[0])}: the template opened here never closes")
    return "".join(out)


def closing(code: str, start: int, path: str) -> int:
    """The index of the bracket that closes the one at `start`, in text `blank` has read."""
    stack = []  # closers expected
    for i in range(start, len(code)):
        if (c := code[i]) in CLOSE:
            stack.append(CLOSE[c])
        elif c in ")]}":
            if stack.pop() != c:
                raise RuntimeError(f"{path}:{line(code, i)}: `{c}` closes nothing opened")
            if not stack:
                return i
    raise RuntimeError(f"{path}:{line(code, start)}: the brackets opened here never close")


SPEC_CALL = re.compile(r"(?<![\w.$])spec\(")
TEST_CALL = re.compile(r"""\s*\.test(?:\.each\([^;\n]*?\))?\(\s*(["'])((?:\\.|(?!\1).)*)\1""")
JEST_MARK = re.compile(r"""(?<![\w.$])spec\(\s*["']([^"']+)["']\s*(,\s*\{\s*new\s*:\s*(true|false)\s*\}\s*)?\)""")


def jest_tests(path: str, text: str) -> Iterator[tuple[str, str, tuple[Mark, ...]]]:
    """Each `spec(...).test("name", ...)` in code, its source from `spec(` to the `)` closing its `test(` call."""
    names, code = set(), blank(text, path)
    for call in SPEC_CALL.finditer(code):
        if not (found := JEST_MARK.match(text, call.start())):
            continue
        at = line(text, found.start())
        if not (test := TEST_CALL.match(text, found.end())):
            raise RuntimeError(f"{path}:{at}: a spec marker must be followed by .test(\"name\", ...)")
        if test[2] in names:
            raise RuntimeError(f"{path}:{at}: two tests named {test[2]!r}")
        names.add(test[2])
        yield test[2], text[found.start():closing(code, code.rfind("(", found.end(), test.end()), path) + 1], (Mark(found[1], found[3] == "true", at),)


PYTHON = [sys.executable]  # pytest's interpreter, the last pushed: another than the gate's own (§7, O-SELF2)


@contextmanager
def interpreter(python: str) -> Iterator[None]:
    """Run pytest with `python` instead of Redline's own Python while the block lasts."""
    PYTHON.append(python)
    try:
        yield
    finally:
        PYTHON.pop()


def pytest_command(sid: str | None) -> tuple[list[str], dict[str, str]]:
    spec = [f"--redline-spec={sid}"] if sid else []
    return [PYTHON[-1], "-m", "pytest", "-q", "-p", "no:cacheprovider", *spec], {"PYTHONDONTWRITEBYTECODE": "1"}


def jest_command(sid: str | None) -> tuple[list[str], dict[str, str]]:
    return [shutil.which("npx") or "npx", "--no-install", "jest", "--ci"], {"REDLINE_SPEC": sid} if sid else {}


JS = ("js", "jsx", "mjs", "cjs", "ts", "tsx")
PYTEST = Runner("pytest", ("*.py",), r"mark\.spec\(", python_tests, ("test_*.py", "*_test.py", "conftest.py"), "", pytest_command)
JEST = Runner("jest", tuple(f"*.{ext}" for ext in JS), r"(^|[^A-Za-z0-9_.$])spec\(", jest_tests,
              tuple(f"*.{kind}.{ext}" for kind in ("test", "spec") for ext in JS) + tuple(f"*__tests__/*.{ext}" for ext in JS),
              "npx", jest_command)
RUNNERS = (PYTEST, JEST)


def run(repo: Path, runner: Runner, sid: str | None = None) -> subprocess.CompletedProcess:
    """Run the runner's tests, or one scenario's alone; its output is decoded as UTF-8 (O-ENC1)."""
    argv, env = runner.command(sid)
    from redline.reports import finish, snapshot
    expected = snapshot(repo, runner)
    with tempfile.TemporaryDirectory(prefix="redline-report-") as directory:
        sink = Path(directory) / "report.json"
        adapter = Path(directory) / "adapter.cjs"
        adapter.write_text("module.exports = require(" + json.dumps(str(repo / HELPERS["jest-reporter"])) + ")(" +
                           json.dumps({"root": str(repo), "sink": directory}) + ");\n", encoding="utf-8")
        options = [f"--redline-report={sink}"] if runner.name == "pytest" else ["--testRunner", str(adapter)]
        done = subprocess.run([*argv, *options], cwd=repo, capture_output=True,
                              encoding="utf-8", errors="replace", env={**os.environ, **env})
        try:
            parts = [json.loads(p.read_text(encoding="utf-8")) for p in Path(directory).glob("*.part")] if runner.name == "jest" else [json.loads(sink.read_text(encoding="utf-8"))]
            if not parts:
                raise ValueError("no report parts")
            payload = {key: [row for part in parts for row in part[key]] for key in ("expected", "observed", "diagnostics")}
        except (OSError, ValueError):
            payload = {"expected": [], "observed": [], "diagnostics": [
                {"code": "missing", "identity": runner.name, "reason": "invocation report unavailable"}]}
        done.outcomes = finish(expected, payload)
        return done


def runner_for(test: str) -> Runner | None:
    """The runner of a test (`path::name`) or a file, by its extension."""
    path = test.split("::")[0]
    return next((r for r in RUNNERS if any(fnmatch(path, glob) for glob in r.paths)), None)


def shipped(name: str) -> str:
    return files("redline").joinpath("helpers", Path(HELPERS[name]).name).read_text(encoding="utf-8")


def install(repo: Path, name: str) -> str:
    if name == "jest":
        install(repo, "jest-reporter")
    (repo / HELPERS[name]).parent.mkdir(parents=True, exist_ok=True)
    (repo / HELPERS[name]).write_bytes(shipped(name).encode())
    return HELPERS[name]


def write_workflow(repo: Path) -> str:
    """Write the adopting repository's workflow, installing the git commit this Redline was installed
    from (`direct_url.json`, PEP 610); refuse with no such commit or an existing file. Never a helper:
    a written workflow may hold the project's own steps, so check-helpers doesn't read it."""
    text = distribution("redline").read_text("direct_url.json")
    direct = json.loads(text) if text else {}
    vcs = direct.get("vcs_info", {})
    commit = vcs.get("commit_id", "")
    if vcs.get("vcs") != "git" or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise RuntimeError("Redline wasn't installed from a git commit, so the workflow has none to install; "
                           'install it with `pip install "redline @ git+<url>@<commit>"` and run this again')
    url = direct.get("url")
    # YAML and Actions read this before the shell; quoting alone cannot contain them (O-SELF6).
    if (not isinstance(url, str) or not re.fullmatch(r"[A-Za-z0-9._~:/?#\[\]@!&'()*+,;=%-]+", url)
            or url.startswith("-")):
        raise RuntimeError("unsupported git URL in direct_url.json; use ASCII URL characters, "
                           "percent-encode spaces and non-ASCII characters, and do not start with '-'")
    if (repo / WORKFLOW).exists():
        raise RuntimeError(f"{WORKFLOW} exists and is the repository's own; to write Redline's, remove it first")
    template = files("redline").joinpath("helpers", "redline.yml").read_text(encoding="utf-8")
    (repo / WORKFLOW).parent.mkdir(parents=True, exist_ok=True)
    (repo / WORKFLOW).write_bytes(template.replace("{url}", shlex.quote(url)).replace("{commit}", commit).encode())
    action = repo / ".github/actions/redline-project/action.yml"
    if not action.exists():
        action.parent.mkdir(parents=True, exist_ok=True)
        action.write_bytes(files("redline").joinpath("helpers", "project.yml").read_bytes())
    return WORKFLOW


def check_helpers(repo: Path) -> list[str]:
    """Each helper in the repository that differs from the one Redline ships (line endings aside)."""
    return [f"{path} differs from the helper Redline ships; run `redline install {name}`"
            for name, path in HELPERS.items()
            if ((repo / path).is_file() or name == "jest-reporter" and (repo / HELPERS["jest"]).is_file())
            and (not (repo / path).is_file() or (repo / path).read_text(encoding="utf-8").replace("\r\n", "\n") != shipped(name))]
