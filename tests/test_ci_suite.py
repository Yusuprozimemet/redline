"""`redline ci suite` runs a PR's code, and `redline ci pr --suite-result` runs every gate and none of it (the change
suite-job). A `conftest.py` that writes a file outside the repository when pytest loads it shows whether any test ran."""

import os
from pathlib import Path

import pytest

from redline.cli import main
from test_check_break import HOLDS, delta
from test_check_lines import lines
from test_lock import lock
from test_ci import BROKEN, fake_python, red_pr, remote  # noqa: F401 (remote is a fixture)
from test_outside import outside
from test_pr import RED_TESTS
from test_start import CHANGE, DELTA, change, fresh_branch, merge_step  # noqa: F401 (change is a fixture)

ONE_HOLD = delta(HOLDS.split("#### Scenario GREET.H2")[0])  # GREET.H1 alone, its premises citing greet.py
NO_CODE = ONE_HOLD.replace("`greet.py:1` (`placeholder`)", "`README.md:1`")  # premises citing no Python file
FAILING = 'import pytest\nfrom greet import placeholder\n\n@pytest.mark.spec("GREET.H1")\ndef test_h1():\n    assert placeholder() == "boom"\n'
NEW_ONLY = 'import pytest\n\n@pytest.mark.spec("GREET.H1", new=True)\ndef test_h1():\n    assert False\n'
RESULTS = ["failure", "cancelled", "skipped"]
SUITE = "suite: the test suite failed"


def ci(repo, capsys, *args: str) -> tuple[int, str]:
    """The command's exit code and everything it printed; argparse's exit counts as one."""
    try:
        code = main(["ci", *args, "--repo", str(repo.path)])
    except SystemExit as exit:
        code = exit.code
    out = capsys.readouterr()
    return code, out.out + out.err


def conftest(written: Path) -> dict[str, str]:
    return {"conftest.py": f"from pathlib import Path\n\nPath({str(written)!r}).write_text('ran', encoding='utf-8')\n"}


def r_step(repo, capsys, files: dict[str, str], spec: str = ONE_HOLD, hold: str = FAILING) -> None:
    """add-greet at its R step with GREET.H1 alone, whose test is `hold`, locked; every gate but check-break passes."""
    repo.commit("one hold scenario", {f"{CHANGE}/specs/greet/delta.md": spec, "README.md": "toy\n"})
    red_pr(repo, capsys, {"tests/test_greet.py": RED_TESTS, "test_hold.py": hold, **files})
    lock(repo, capsys)
    repo.commit("lock\n\nRedline-Step: add-greet/R")


def starting(out: str, *prefixes: str) -> list[str]:
    return [line for line in out.splitlines() if line.startswith(prefixes)]


@pytest.mark.parametrize("at", ["R", "outside"])
@pytest.mark.spec("CI.APART.S1", new=True)
def test_ci_pr_with_a_suite_result_of_success_runs_every_gate_and_none_of_the_prs_code(change, capsys, tmp_path, at):
    written = tmp_path / "ran"
    files = {"tests/test_broken.py": BROKEN, **conftest(written)}
    r_step(change, capsys, files) if at == "R" else outside(change, files)
    code, out = ci(change, capsys, "pr", "--base", "main", "--suite-result", "success")
    assert code == 0, out
    assert starting(out, "ok:") and not starting(out, "suite:", "check-break:"), out
    assert not written.exists()
    code, out = ci(change, capsys, "pr", "--base", "main")
    assert code == 1 and written.exists()


@pytest.mark.spec("CI.APART.S2", new=True)
def test_a_suite_result_other_than_success_fails_the_gate_beside_the_gates_failures(change, capsys, tmp_path, remote):
    over = "check-lines: 401 changed lines, over the limit of 400"
    outside(change, {"notes.md": "a note\n"})
    for result in RESULTS:
        code, out = ci(change, capsys, "pr", "--base", "main", "--suite-result", result)
        assert (code, starting(out, "suite:", "check-")) == (1, [f"suite: the suite job's result is {result}"]), out
    change.commit("big", {"notes.md": lines(401)})
    for result in RESULTS:
        code, out = ci(change, capsys, "pr", "--base", "main", "--suite-result", result)
        assert code == 1 and f"suite: the suite job's result is {result}" in out and over in out, out
    code, out = ci(change, capsys, "pr", "--base", "main", "--suite-result", "success")
    assert (code, starting(out, "suite:", "check-", "ok:")) == (1, [over]), out
    written = tmp_path / "ran"
    change.commit("a conftest", conftest(written))
    for args, said in [
        (("push", "--run-url", "u", "--suite-result", "success"), "redline: --suite-result is for ci pr only"),
        (("suite", "--suite-result", "success"), "redline: --suite-result is for ci pr only"),
        (("suite", "--pr", "1"), "redline: ci suite takes --base and --python alone"),
        (("suite", "--run-url", "u"), "redline: ci suite takes --base and --python alone"),
        (("suite", "--note", str(tmp_path / "note")), "redline: ci suite takes --base and --python alone"),
        (("push", "--run-url", "u", "--python", fake_python(tmp_path)),
         "redline: --python is for ci pr and ci suite only: a push run's suite is the merged code's own"),
    ]:
        assert ci(change, capsys, *args) == (2, said + "\n")
    assert not written.exists() and remote.pushed == []
    code, out = ci(change, capsys, "pr", "--base", "main", "--suite-result", "neutral")
    assert code == 2 and "--suite-result" in out


@pytest.mark.spec("CI.APART.S2", new=True)
def test_a_suite_result_fails_a_step_over_400_lines_beside_check_lines(change, capsys):
    merge_step(change, "S")
    change.commit("red\n\nRedline-Step: add-greet/R", {"tests/test_greet.py": RED_TESTS})
    fresh_branch(change, "g1")
    assert main(["ledger", "add-greet", "--repo", str(change.path)]) == 0
    capsys.readouterr()
    green = RED_TESTS.replace('"GREET.S1", new=True)\ndef test_s1():\n    assert False', '"GREET.S1")\ndef test_s1():\n    assert True')
    change.commit("G1\n\nRedline-Step: add-greet/G1", {"tests/test_greet.py": green, "notes.md": lines(401)})
    code, out = ci(change, capsys, "pr", "--base", "main", "--suite-result", "success")
    assert code == 1
    failures = out.splitlines()
    assert len(failures) == 1 and failures[0].startswith("check-lines: ") and "over the limit of 400" in failures[0], out
    for result in RESULTS:
        code, out = ci(change, capsys, "pr", "--base", "main", "--suite-result", result)
        assert code == 1 and f"suite: the suite job's result is {result}" in out and failures[0] in out, out


def logging_python(where: Path, log: Path) -> str:
    """An interpreter that runs nothing: it appends its arguments to `log` and exits 3."""
    if os.name == "nt":
        path = where / "python.cmd"
        path.write_text(f'@echo off\r\necho %* >> "{log}"\r\nexit /b 3\r\n', encoding="utf-8")
    else:
        path = where / "python"
        path.write_text(f'#!/bin/sh\necho "$*" >> "{log}"\nexit 3\n', encoding="utf-8")
        path.chmod(0o755)
    return str(path)


@pytest.mark.spec("CI.APART.S3", new=True)
def test_ci_suite_runs_check_break_at_an_r_step_then_the_suite_and_no_gate(change, capsys, tmp_path):
    r_step(change, capsys, {"tests/test_broken.py": BROKEN, "notes.md": lines(401)})
    code, out = ci(change, capsys, "suite", "--base", "main")
    assert code == 1
    assert starting(out, "check-break: GREET.H1:") and starting(out, SUITE) and not starting(out, "check-lines:"), out
    log = tmp_path / "python.log"
    code, out = ci(change, capsys, "suite", "--base", "main", "--python", logging_python(tmp_path, log))
    assert code == 1, out
    ran = log.read_text(encoding="utf-8").splitlines()
    assert len(ran) == 2 and sum("--redline-spec GREET.H1" in line for line in ran) == 1, ran
    merge_step(change, "R")
    fresh_branch(change, "g1")
    change.commit("G1\n\nRedline-Step: add-greet/G1", {"test_hold.py": FAILING, "tests/test_broken.py": BROKEN})
    code, out = ci(change, capsys, "suite", "--base", "main")
    assert starting(out, SUITE) and not starting(out, "check-break:"), out


@pytest.mark.spec("CI.APART.S3", new=True)
def test_ci_suite_outside_any_step_runs_the_suite_alone_and_refuses_two_steps(change, capsys):
    outside(change, {"notes.md": lines(401)})
    code, out = ci(change, capsys, "suite", "--base", "main")
    assert code == 0 and starting(out, "ok:"), out
    change.commit("one\n\nRedline-Step: add-greet/R")
    change.commit("two\n\nRedline-Step: add-greet/G1")
    code, out = ci(change, capsys, "suite", "--base", "main")
    assert code == 1 and starting(out, "refused:"), out


@pytest.mark.parametrize(("spec", "hold", "why"), [
    (ONE_HOLD, NEW_ONLY, "no test links it without new=True"),
    (NO_CODE, FAILING, "nothing to mutate: the change's premises cite no file its tests' runners mutate"),
], ids=["new-only", "no-code"])
@pytest.mark.spec("CI.APART.S5", new=True)
def test_at_an_r_step_ci_pr_with_a_suite_result_keeps_the_refusals_that_run_no_test(change, capsys, tmp_path, spec, hold, why):
    written = tmp_path / "ran"
    r_step(change, capsys, conftest(written), spec, hold)
    code, out = ci(change, capsys, "pr", "--base", "main", "--suite-result", "success")
    assert code == 1
    assert f"check-break: GREET.H1: {why}" in out.splitlines(), out
    assert not written.exists()
    if hold is FAILING:
        code, out = ci(change, capsys, "suite", "--base", "main")
        assert [line for line in starting(out, "check-break: GREET.H1: its")
                if line.endswith("tests fail on unmutated code")], out


@pytest.mark.parametrize("at", ["R", "outside"])
@pytest.mark.spec("CI.APART.H1")
def test_ci_pr_without_a_suite_result_still_runs_check_break_and_the_suite(change, capsys, at):
    files = {"tests/test_broken.py": BROKEN}
    r_step(change, capsys, files) if at == "R" else outside(change, files)
    code, out = ci(change, capsys, "pr", "--base", "main")
    assert code == 1
    assert starting(out, SUITE), out
    assert bool(starting(out, "check-break: GREET.H1:")) is (at == "R"), out
