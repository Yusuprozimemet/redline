"""What a frozen test reaches (fixtures, same-file helpers, marks, pytest settings), which the
critical contract lock hashes as its `reach`. Imported names aren't followed. See docs/design.md, §4."""

import ast
import configparser
import hashlib
import tomllib
from pathlib import Path, PurePosixPath

from redline.breaks import source

FUNCS = (ast.FunctionDef, ast.AsyncFunctionDef)
CONFIGS = (("pytest.ini", "pytest"), ("pyproject.toml", None), ("tox.ini", "pytest"), ("setup.cfg", "tool:pytest"))


class Module:
    def __init__(self, repo: Path, path: str):
        self.path = path
        text = (repo / path).read_text(encoding="utf-8")
        self.lines = text.split("\n")
        self.tree = ast.parse(text, path)
        self.defs: dict[str, ast.stmt] = {}  # module-level name -> the statement that defines it
        for node in self.tree.body:
            targets = getattr(node, "targets", None) or [getattr(node, "target", node)]
            for name in filter(None, [getattr(node, "name", None)] + [getattr(t, "id", None) for t in targets]):
                self.defs.setdefault(name, node)


def mark(decorator: ast.expr, name: str) -> ast.expr | None:
    func = decorator.func if isinstance(decorator, ast.Call) else decorator
    return decorator if getattr(func, "id", getattr(func, "attr", None)) == name else None


def autouse(node: ast.stmt) -> bool:
    calls = [d for d in node.decorator_list if isinstance(mark(d, "fixture"), ast.Call)]
    return any(k.arg == "autouse" and getattr(k.value, "value", False) is True for d in calls for k in d.keywords)


def requested(node: ast.stmt) -> list[str]:
    """The fixtures a function asks for: its parameters, then its `usefixtures` names."""
    args = node.args.posonlyargs + node.args.args + node.args.kwonlyargs
    used = [a.value for d in node.decorator_list if isinstance(mark(d, "usefixtures"), ast.Call) for a in d.args]
    return [a.arg for a in args] + [u for u in used if isinstance(u, str)]


def settings(repo: Path) -> str:
    """The root pytest configuration section, from the first file that has one."""
    for name, section in CONFIGS:
        if not (repo / name).is_file():
            continue
        text = (repo / name).read_text(encoding="utf-8")
        if section is None:
            found = tomllib.loads(text).get("tool", {}).get("pytest", {}).get("ini_options")
        else:
            parser = configparser.ConfigParser(interpolation=None)
            parser.read_string(text)
            found = dict(parser[section]) if parser.has_section(section) else None
        if found is not None:
            return f"{name}: {sorted(found.items())!r}"
    return ""


def reach(repo: Path, test: str) -> str:
    """SHA-256 of what `path::name` or `path::Class::name` reaches, the test itself left out."""
    path, *names = test.split("::")
    parent = PurePosixPath(path).parent
    conftests = [str(d / "conftest.py") for d in (parent, *parent.parents) if (repo / d / "conftest.py").is_file()]
    module, *others = [Module(repo, p) for p in [path, *conftests]]
    cls = module.defs[names[0]] if len(names) > 1 else None
    node = next(n for n in (cls.body if cls else module.tree.body) if getattr(n, "name", None) == names[-1])
    fixtures: dict[str, tuple[Module, ast.stmt]] = {}
    for owner, body in ([(module, cls.body)] if cls else []) + [(m, m.tree.body) for m in (module, *others)]:
        for n in body:
            if isinstance(n, FUNCS) and any(mark(d, "fixture") for d in n.decorator_list):
                fixtures.setdefault(n.name, (owner, n))
    reached: dict[tuple[str, int, int], str] = {}

    def visit(owner: Module, n: ast.AST) -> None:
        key = (owner.path, n.lineno, n.col_offset)
        if key in reached:
            return
        reached[key] = source(owner.lines, n)
        for name in requested(n) if isinstance(n, FUNCS) else []:
            if name in fixtures:
                visit(*fixtures[name])
        for sub in ast.walk(n):
            if isinstance(sub, ast.Name) and sub.id in owner.defs:
                visit(owner, owner.defs[sub.id])

    visit(module, node)
    for owner, n in fixtures.values():
        if autouse(n):
            visit(owner, n)
    if "pytestmark" in module.defs:
        visit(module, module.defs["pytestmark"])
    for n in (cls.decorator_list + [s for s in cls.body if not isinstance(s, FUNCS)]) if cls else []:
        visit(module, n)
    del reached[path, node.lineno, node.col_offset]
    text = "".join(f"{p}:{line}\n{src}\n" for (p, line, _), src in sorted(reached.items())) + settings(repo)
    return hashlib.sha256(text.encode()).hexdigest()
