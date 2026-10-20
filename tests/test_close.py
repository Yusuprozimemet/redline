from redline.cli import main
from redline.pr import gates
from test_ledger import land, note
from test_start import CHANGE, DELTA, change  # noqa: F401 (change is a fixture)

TESTS = "import pytest\n\n" + "".join(
    f'@pytest.mark.spec("GREET.{sid}"{{new}})\ndef test_{sid}():\n    assert True\n\n' for sid in ("S1", "S2"))
HOLD = DELTA + "\n#### Scenario GREET.H1 [hold]: the placeholder stays\n- THEN it returns nothing\n"
HELD = 'import pytest\n\n@pytest.mark.spec("GREET.H1")\ndef test_h1():\n    assert True\n'
WAITING = ("waiting, not wrong: once CI's push run notes those commits, fetch the notes "
           "(git fetch origin 'refs/notes/*:refs/notes/*'), run redline ledger add-greet, commit and push; "
           "nothing else needs to change")


def close(repo, capsys) -> tuple[int, str]:
    code = main(["check-close", "add-greet", "--repo", str(repo.path)])
    return code, capsys.readouterr().out


def red_and_green(repo) -> tuple[str, str]:
    _, red = land(repo, "red", {"tests/test_greet.py": TESTS.replace("{new}", ", new=True")})
    _, green = land(repo, "green", {"tests/test_greet.py": TESTS.replace("{new}", "")})
    return red, green


def test_a_change_whose_every_red_and_green_ci_passed_closes(change, capsys):
    for merged in red_and_green(change):
        note(change, merged, "pass")
    code, out = close(change, capsys)
    assert code == 0, out
    assert out == "ok: 2 scenarios, each with its evidence on main\n"


def test_a_new_scenario_with_no_red_or_no_green_on_main_refuses(change, capsys):
    code, out = close(change, capsys)
    assert code == 1
    assert "GREET.S1: no red on main\nGREET.S1: no green on main\nGREET.S2: no red on main\n" in out
    _, red = land(change, "red", {"tests/test_greet.py": TESTS.replace("{new}", ", new=True")})
    note(change, red, "pass")
    code, out = close(change, capsys)
    assert code == 1
    assert out == "GREET.S1: no green on main\nGREET.S2: no green on main\n"


def test_an_unverified_result_says_it_is_waiting_and_a_failed_one_refuses(change, capsys):
    red, green = red_and_green(change)
    note(change, red, "pass")
    code, out = close(change, capsys)
    assert code == 1
    assert out == (f"GREET.S1: green is unverified: no CI note on {green[:7]} yet\n"
                   f"GREET.S2: green is unverified: no CI note on {green[:7]} yet\n{WAITING}\n")
    note(change, green, "fail")
    code, out = close(change, capsys)
    assert code == 1
    assert out == (f"GREET.S1: green failed: the CI note on {green[:7]} says fail\n"
                   f"GREET.S2: green failed: the CI note on {green[:7]} says fail\n")


def test_a_hold_scenario_needs_a_break_that_passed(change, capsys):
    change.commit("a hold scenario", {f"{CHANGE}/specs/greet/delta.md": HOLD})
    for merged in red_and_green(change):
        note(change, merged, "pass")
    assert close(change, capsys)[1] == "GREET.H1: no break on main\n"
    _, merged = land(change, "hold", {"tests/test_hold.py": HELD})
    change.git("notes", "--ref=redline-ci", "add", "-m", "result: pass\nrun: https://ci/2\nbreak:\n  GREET.H1: fail\n", merged)
    assert close(change, capsys) == (1, f"GREET.H1: break failed: the CI note on {merged[:7]} says fail\n")
    change.git("notes", "--ref=redline-ci", "add", "-f", "-m", "result: pass\nrun: https://ci/2\nbreak:\n  GREET.H1: pass\n", merged)
    assert close(change, capsys) == (0, "ok: 3 scenarios, each with its evidence on main\n")


def test_pr_runs_it_at_the_c_step_only(change, capsys):
    assert "check-close: GREET.S1: no red on main" in gates(change.path, "add-greet", "C")
    assert not [f for f in gates(change.path, "add-greet", "G1") if f.startswith("check-close")]


def test_an_unknown_change_is_an_error(change, capsys):
    code = main(["check-close", "nope", "--repo", str(change.path)])
    assert code == 2 and "no scenarios declared in redline/changes/nope/specs" in capsys.readouterr().out
