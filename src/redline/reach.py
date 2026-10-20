"""What a frozen test reaches (fixtures, same-file helpers, marks, pytest settings, and names
imported from the support files `support:` in redline/config.yaml names), which the critical
contract lock hashes as its `reach`. Other imports aren't followed. See docs/design.md, §4."""

import ast
import configparser
import hashlib
import tomllib
from pathlib import Path, PurePosixPath

from redline.config import load_config
from redline.lines import is_generated
from redline.runner import source

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
        self.imports: dict[str, tuple[int, str, str | None]] = {}  # name -> (level, module, its name or None)
        for node in self.tree.body:
            for a in getattr(node, "names", []) if isinstance(node, (ast.Import, ast.ImportFrom)) else []:
                if isinstance(node, ast.ImportFrom):
                    self.imports.setdefault(a.asname or a.name, (node.level, node.module or "", a.name))
                elif a.asname or "." not in a.name:  # `import a.b` binds `a`; `a.b.name` isn't followed
                    self.imports.setdefault(a.asname or a.name, (0, a.name, None))


def find(repo: Path, importer: str, level: int, module: str, globs: list[str]) -> str | None:
    """The support file `module` names from `importer`, or None if the first file found isn't one."""
    here = PurePosixPath(importer).parent
    for _ in range(max(level - 1, 0)):
        here = here.parent
    rel = module.replace(".", "/")
    for root in [here] if level else [here, *here.parents]:
        for path in (root / f"{rel}.py", root / rel / "__init__.py"):
            if (repo / path).is_file():
                return str(path) if is_generated(str(path), globs) else None
    return None


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
    support = load_config(repo).support
    loaded = {m.path: m for m in (module, *others)}

    def load(owner: Module, level: int, name: str) -> Module | None:
        found = find(repo, owner.path, level, name, support) if support else None
        if found and found not in loaded:
            loaded[found] = Module(repo, found)
        return loaded.get(found) if found else None

    def resolve(owner: Module, name: str, attr: str | None = None, seen: frozenset = frozenset()) -> tuple | None:
        """Where `name` (or `name.attr`, for a module) is defined: here, or in a support file."""
        if attr is None and name in owner.defs:
            return owner, owner.defs[name]
        if name not in owner.imports or (owner.path, name) in seen:
            return None
        level, mod, imported = owner.imports[name]
        target = load(owner, level, mod)
        wanted = imported if attr is None else attr if imported is None else None
        return resolve(target, wanted, None, seen | {(owner.path, name)}) if target and wanted else None

    cls = module.defs[names[0]] if len(names) > 1 else None
    node = next(n for n in (cls.body if cls else module.tree.body) if getattr(n, "name", None) == names[-1])
    fixtures: dict[str, tuple[Module, ast.stmt]] = {}
    for owner, body in ([(module, cls.body)] if cls else []) + [(m, m.tree.body) for m in (module, *others)]:
        named = [(n.name, (owner, n)) for n in body if isinstance(n, FUNCS)]
        if body is owner.tree.body:  # a fixture imported into the module is one there, as in pytest
            named += [(name, found) for name in owner.imports if (found := resolve(owner, name))]
        for name, (o, n) in named:
            if isinstance(n, FUNCS) and any(mark(d, "fixture") for d in n.decorator_list):
                fixtures.setdefault(name, (o, n))
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
            if isinstance(sub, ast.Name) and (found := resolve(owner, sub.id)):
                visit(*found)
            elif isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name) and (
                    found := resolve(owner, sub.value.id, sub.attr)):
                visit(*found)

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
