"""pytest plugin: `@pytest.mark.spec("ID")` links a test to a scenario.

`spec("ID", new=True)` marks a scenario that has no code yet. The test runs as a strict expected
failure, so a `new` test that already passes fails the run: a check that can't fail can't get in.
"""

import pytest

USAGE = 'use @pytest.mark.spec("ID") or @pytest.mark.spec("ID", new=True)'


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "spec(id, new=False): link a test to a scenario; new=True expects it to fail"
    )


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        for mark in item.iter_markers("spec"):
            args_ok = len(mark.args) == 1 and isinstance(mark.args[0], str) and mark.args[0]
            if not args_ok or set(mark.kwargs) - {"new"}:
                raise pytest.UsageError(f"{item.nodeid}: malformed spec marker; {USAGE}")
            if mark.kwargs.get("new"):
                reason = f"new scenario {mark.args[0]}: must fail until its Green step"
                item.add_marker(pytest.mark.xfail(strict=True, reason=reason))
