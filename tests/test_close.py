import pytest

from redline.approval import Approvals
from redline.cli import main
from redline.pr import gates
from test_ledger import land, note
from test_pr import FakeGitHub
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


MANUAL = DELTA + "\n#### Scenario GREET.M1 [manual]: looks right\nManual: by eye\n- THEN it looks right\n"
CHECKED = "Redline-Manual: GREET.M1 checked-by @alice: the greeting fits a 360px screen"
UNCHECKED = ("GREET.M1: manual, with no person's check in this PR: add "
             "`Redline-Manual: GREET.M1 checked-by @person: <what was seen>` to one of its commits\n")
PENDING = "note: GREET.M1: manual, checked by @alice: CI will need the `redline:manual` label from a maintainer\n"
CLOSED = "ok: 3 scenarios, each with its evidence: 2 on main, 1 checked by a person\n"


def manual(repo) -> None:
    """main with a manual scenario and its change's red and green noted, then the C step's branch."""
    repo.commit("a manual scenario", {f"{CHANGE}/specs/greet/delta.md": MANUAL})
    for merged in red_and_green(repo):
        note(repo, merged, "pass")
    repo.git("checkout", "-q", "-b", "close")


def test_a_manual_scenario_closes_only_with_a_check_in_the_c_prs_own_commits(change, capsys):
    change.commit("a manual scenario", {f"{CHANGE}/specs/greet/delta.md": MANUAL})
    change.commit(f"checked too early\n\n{CHECKED}")  # on main already: not this PR's
    for merged in red_and_green(change):
        note(change, merged, "pass")
    change.git("checkout", "-q", "-b", "close")
    assert close(change, capsys) == (1, UNCHECKED)
    change.commit(f"checked\n\n{CHECKED}")
    assert close(change, capsys) == (0, PENDING + CLOSED)
    change.commit(f"checked again\n\n{CHECKED}")
    assert close(change, capsys) == (0, PENDING + PENDING + CLOSED)


@pytest.mark.parametrize("trailer, why", [
    ("Redline-Manual: GREET.M1 checked by alice", "allows nothing: it needs `<ID> checked-by @person: <what was seen>`"),
    ("Redline-Manual: GREET.M1 checked-by alice: fits", "allows nothing: it needs `<ID> checked-by @person: <what was seen>`"),
    ("Redline-Manual: GREET.S1 checked-by @alice: it greets", "GREET.S1 is no manual scenario of add-greet"),
    ("Redline-Manual: GREET.X9 checked-by @alice: it greets", "GREET.X9 is no manual scenario of add-greet"),
])
def test_a_manual_check_that_allows_nothing_fails(change, capsys, trailer, why):
    manual(change)
    change.commit(f"checked\n\n{CHECKED}\n{trailer}")
    code, out = close(change, capsys)
    assert code == 1
    assert out.splitlines()[0] == f"{trailer}: {why}", out
    assert "GREET.M1: manual, with no" not in out


def test_run_on_its_own_it_reads_the_prs_commits_from_base(change, capsys):
    change.commit("a manual scenario", {f"{CHANGE}/specs/greet/delta.md": MANUAL})
    for merged in red_and_green(change):
        note(change, merged, "pass")
    before = change.git("rev-parse", "HEAD")
    change.commit(f"checked\n\n{CHECKED}")
    assert close(change, capsys) == (1, UNCHECKED), "on main after the merge there are no PR commits"
    code = main(["check-close", "add-greet", "--repo", str(change.path), "--base", before])
    assert (code, capsys.readouterr().out) == (0, PENDING + CLOSED)


def test_in_ci_a_manual_check_needs_a_maintainers_label(change, capsys):
    manual(change)
    change.commit(f"checked\n\n{CHECKED}")

    def closing(applied: dict) -> list[str]:
        github = FakeGitHub(change, applied=applied, roles={"maintainer": "admin"})
        return [f for f in gates(change.path, "add-greet", "C", Approvals(github, 1)) if f.startswith("check-close")]

    assert closing({}) == ["check-close: GREET.M1: manual, checked by @alice: needs the `redline:manual` label from a maintainer"]
    assert closing({"redline:manual": "bob"}) == [
        "check-close: GREET.M1: manual, checked by @alice: `redline:manual` was applied by @bob, who isn't a maintainer"]
    assert closing({"redline:manual": "maintainer"}) == []
    local = Approvals()
    assert not [f for f in gates(change.path, "add-greet", "C", local) if f.startswith("check-close")]
    assert local.pending == [PENDING[len("note: "):-1]]


def test_a_manual_check_outside_the_c_step_fails(change, capsys):
    manual(change)
    change.commit(f"checked\n\n{CHECKED}")
    for step in ("S", "G1"):
        assert f"manual: {CHECKED}: a person's check counts at the C step only" in gates(change.path, "add-greet", step)
    assert not [f for f in gates(change.path, "add-greet", "C") if f.startswith("manual:")]


def test_pr_runs_it_at_the_c_step_only(change, capsys):
    assert "check-close: GREET.S1: no red on main" in gates(change.path, "add-greet", "C")
    assert not [f for f in gates(change.path, "add-greet", "G1") if f.startswith("check-close")]


def test_an_unknown_change_is_an_error(change, capsys):
    code = main(["check-close", "nope", "--repo", str(change.path)])
    assert code == 2 and "no scenarios declared in redline/changes/nope/specs" in capsys.readouterr().out
