"""End to end on a toy project: Red then Green, proved by pytest and by git history."""

import subprocess
import sys

from redline.cli import main

RED_TEST = '''import pytest
from greet import greet

@pytest.mark.spec("GREET.S1", new=True)
def test_greets_by_name():
    assert greet("Ada") == "Hello, Ada!"
'''
STUB = "def greet(name):\n    raise NotImplementedError\n"
IMPL = 'def greet(name):\n    return f"Hello, {name}!"\n'


def pytest_in(repo):
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-rxX"],
        cwd=repo.path, capture_output=True, text=True,
    )


def test_toy_red_then_green(repo):
    repo.commit("R: GREET.S1 red", {"greet.py": STUB, "test_greet.py": RED_TEST})
    red = pytest_in(repo)
    assert red.returncode == 0, red.stdout
    assert "1 xfailed" in red.stdout

    # Green: the code lands and the `new` flag is removed in the same commit.
    repo.commit("G1: GREET.S1 green", {"greet.py": IMPL, "test_greet.py": RED_TEST.replace(", new=True", "")})
    green = pytest_in(repo)
    assert green.returncode == 0, green.stdout
    assert "1 passed" in green.stdout
    assert main(["check-order", "--repo", str(repo.path)]) == 0


def test_toy_test_that_cannot_fail_is_caught_at_red(repo):
    repo.commit("R: GREET.S1 red, but code already there", {"greet.py": IMPL, "test_greet.py": RED_TEST})
    result = pytest_in(repo)
    assert result.returncode == 1
    assert "XPASS(strict)" in result.stdout


def test_toy_green_squashed_with_red_is_caught_by_history(repo):
    repo.commit("G1 only", {"greet.py": IMPL, "test_greet.py": RED_TEST.replace(", new=True", "")})
    assert pytest_in(repo).returncode == 0
    assert main(["check-order", "--repo", str(repo.path)]) == 1
