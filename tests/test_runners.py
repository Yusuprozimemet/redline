"""The real Jest and Stryker on the toy project in tests/toys/jest. Skipped unless REDLINE_REAL_RUNNERS=1,
which the `runners` CI job sets after `npm ci` there; with it, a missing tool fails. See docs/design.md, §5."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from redline.breaks import Stryker
from redline.runner import install

TOY = Path(__file__).parent / "toys" / "jest"
pytestmark = pytest.mark.skipif(os.environ.get("REDLINE_REAL_RUNNERS") != "1",
                                reason="the real Jest and Stryker run in the runners CI job")


@pytest.fixture(scope="module")
def toy():
    install(TOY, "jest")
    yield TOY
    shutil.rmtree(TOY / "redline")


def jest(toy, *paths, sid=None) -> subprocess.CompletedProcess:
    npx = shutil.which("npx")
    assert npx, "npx isn't installed"
    env = {key: value for key, value in os.environ.items() if key != "REDLINE_SPEC"}
    env |= {"REDLINE_SPEC": sid} if sid else {}
    return subprocess.run([npx, "--no-install", "jest", "--ci", *paths], cwd=toy, capture_output=True,
                          encoding="utf-8", errors="replace", env=env)


def test_jest_runs_every_test_and_doesnt_take_the_helper_for_a_test_file(toy):
    done = jest(toy)
    assert done.returncode == 0, done.stderr
    assert "Test Suites: 1 passed, 1 total" in done.stderr
    assert "Tests:       2 passed, 2 total" in done.stderr


def test_redline_spec_runs_one_scenarios_tests_alone(toy):
    done = jest(toy, sid="TOY.H1")
    assert done.returncode == 0, done.stderr
    assert "Tests:       1 skipped, 1 passed, 2 total" in done.stderr


@pytest.mark.parametrize("expected, code", [("2", 0), ("1", 1)])
def test_a_new_test_runs_as_test_failing_so_one_that_passes_fails_the_run(toy, expected, code):
    path = toy / "src" / "new.test.js"
    path.write_text('const { spec } = require("../redline/runners/jest");\n\n'
                    f'spec("TOY.S1", {{ new: true }}).test("not built yet", () => {{\n  expect(1).toBe({expected});\n}});\n')
    try:
        done = jest(toy, "src/new.test.js")
    finally:
        path.unlink()
    assert done.returncode == code, done.stderr


def test_stryker_kills_only_what_the_scenarios_tests_kill(toy):
    stryker = Stryker(toy)
    assert stryker.unavailable() is None
    assert stryker.kills(["src/adult.js"], "TOY.H1") == (6, 4)  # REDLINE_SPEC reaches its Jest workers
    assert stryker.kills(["src/adult.js"], "TOY.H2") == (6, 6)
    assert not (toy / "reports").exists()
