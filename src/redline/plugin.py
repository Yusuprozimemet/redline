"""pytest plugin: `@pytest.mark.spec("ID")` links a test to a scenario.

`spec("ID", new=True)` marks a scenario that has no code yet. The test runs as a strict expected
failure, so a `new` test that already passes fails the run: a check that can't fail can't get in.
`--redline-spec ID` runs only the tests linked to ID without `new=True` (what check-break runs).
"""

import pytest

USAGE = 'use @pytest.mark.spec("ID") or @pytest.mark.spec("ID", new=True)'


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "spec(id, new=False): link a test to a scenario; new=True expects it to fail"
    )


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--redline-spec", metavar="ID", help="run only the tests linked to ID without new=True")


def linked(item: pytest.Item, sid: str) -> bool:
    return any(m.args[0] == sid and not m.kwargs.get("new") for m in item.iter_markers("spec"))


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        own = [m for m in getattr(getattr(item, "function", None), "pytestmark", []) if m.name == "spec"]
        if len(list(item.iter_markers("spec"))) > len(own):  # Redline reads a marker only as the function's decorator
            raise pytest.UsageError(f"{item.nodeid}: a spec marker goes on the test function, as its decorator, "
                                    "not on its class, its module or a parameter")
        for mark in item.iter_markers("spec"):
            args_ok = len(mark.args) == 1 and isinstance(mark.args[0], str) and mark.args[0]
            if not args_ok or set(mark.kwargs) - {"new"}:
                raise pytest.UsageError(f"{item.nodeid}: malformed spec marker; {USAGE}")
            if mark.kwargs.get("new"):
                reason = f"new scenario {mark.args[0]}: must fail until its Green step"
                item.add_marker(pytest.mark.xfail(strict=True, reason=reason))
    if sid := config.getoption("redline_spec"):
        config.hook.pytest_deselected(items=[item for item in items if not linked(item, sid)])
        items[:] = [item for item in items if linked(item, sid)]
