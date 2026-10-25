import pytest
import yaml

from redline import breaks
from redline.cli import main
from test_ci import RUN, ci, fake_python, remote  # noqa: F401 (remote is a fixture)
from test_ledger import LEDGER, note
from test_pr import RED_TESTS, github, pr  # noqa: F401 (github is a fixture)
from test_start import CHANGE, DELTA, change, fresh_branch, merge_step, start  # noqa: F401

HOLDS = """#### Scenario GREET.H1 [hold]: the placeholder returns nothing
- THEN placeholder() is None

#### Scenario GREET.H2 [hold]: the placeholder takes no arguments
- THEN placeholder(1) raises

#### Scenario GREET.H3 [hold]: the placeholder is callable
- THEN it can be called

"""
HOLD_TESTS = """import pytest
from greet import placeholder

@pytest.mark.spec("GREET.H1")
def test_h1():
    assert placeholder() is None

@pytest.mark.spec("GREET.H2", new=True)
def test_h2():
    assert False

@pytest.mark.spec("GREET.H3")
def test_h3():
    assert placeholder() == "boom"
"""
PASSING = HOLD_TESTS.replace(", new=True)\ndef test_h2():\n    assert False", ")\ndef test_h2():\n    assert True").replace(
    'placeholder() == "boom"', "placeholder() is None")
UNRELATED = "def test_unrelated():\n    assert False\n"


class FakeMutator:
    """Stands in for every runner's mutation tool: `made` mutants per scenario, of which its tests kill `killed`."""

    def __init__(self):
        self.unavailable_reason = None
        self.outcomes: dict[str, tuple[int, int]] = {}
        self.calls: list[tuple[list[str], str]] = []
        self.tests: list[list[str]] = []  # each call's test files

    def __call__(self, repo):
        return self

    def unavailable(self) -> str | None:
        return self.unavailable_reason

    def kills(self, files: list[str], sid: str, tests=()) -> tuple[int, int]:
        self.calls.append((files, sid))
        self.tests.append(list(tests))
        return self.outcomes.get(sid, (3, 1))


@pytest.fixture
def mutator(monkeypatch) -> FakeMutator:
    fake = FakeMutator()  # the whole registry, from its own keys, so a runner added later is replaced too
    monkeypatch.setattr(breaks, "MUTATORS", {name: fake for name in breaks.MUTATORS})
    return fake


def delta(holds: str) -> str:
    return DELTA.replace("### Premises", holds + "### Premises") + "- P2: The readme says nothing — `README.md:1`\n"


@pytest.fixture
def holds(change):
    change.commit("hold scenarios", {f"{CHANGE}/specs/greet/delta.md": delta(HOLDS), "README.md": "toy\n"})
    return change


def check_break(repo, capsys) -> tuple[int, str]:
    code = main(["check-break", "add-greet", "--repo", str(repo.path)])
    return code, capsys.readouterr().out


def test_a_hold_scenario_holds_when_its_tests_pass_and_kill_a_mutant(holds, capsys, mutator):
    holds.commit("only H1", {f"{CHANGE}/specs/greet/delta.md": delta(HOLDS.split("#### Scenario GREET.H2")[0]),
                             "test_hold.py": HOLD_TESTS.split('@pytest.mark.spec("GREET.H2"')[0], "test_unrelated.py": UNRELATED})
    code, out = check_break(holds, capsys)  # test_unrelated fails, but isn't linked to GREET.H1
    assert code == 0, out
    assert "ok: 1 hold scenario(s): tests pass unmutated and fail under a mutant" in out
    assert mutator.calls == [(["greet.py"], "GREET.H1")]  # premise-cited Python files only


def test_check_break_prints_each_hold_scenario_that_isnt_proved(holds, capsys, mutator):
    mutator.outcomes["GREET.H1"] = (4, 0)
    holds.commit("hold tests", {"test_hold.py": HOLD_TESTS})
    code, out = check_break(holds, capsys)
    assert code == 1
    assert "GREET.H1: its tests survive every mutant (0 of 4 killed, in greet.py)" in out
    assert "GREET.H2: no test links it without new=True" in out
    assert "GREET.H3: its pytest tests fail on unmutated code" in out
    assert [sid for _, sid in mutator.calls] == ["GREET.H1"]
    assert "ok:" not in out


def test_check_break_runs_the_scenarios_tests_with_the_python_its_given(holds, capsys, mutator, tmp_path):  # O-SELF2
    from redline.runner import interpreter
    holds.commit("hold tests", {"test_hold.py": PASSING})
    with interpreter(fake_python(tmp_path)):
        code, out = check_break(holds, capsys)
    assert code == 1
    assert "GREET.H1: its pytest tests fail on unmutated code" in out
    assert mutator.calls == []
    code, out = check_break(holds, capsys)  # and its own Python again after it
    assert code == 0, out


def test_where_mutmut_cannot_run_the_mutation_is_skipped_not_failed(holds, capsys, mutator):
    mutator.unavailable_reason = "mutmut doesn't run on Windows"
    holds.commit("hold tests", {"test_hold.py": PASSING})
    code, out = check_break(holds, capsys)
    assert code == 0, out
    assert "skipped GREET.H1: mutmut doesn't run on Windows; CI runs the mutation" in out
    assert "skipped GREET.H3: mutmut doesn't run on Windows" in out
    assert mutator.calls == []


def test_in_ci_a_skipped_mutation_fails_the_scenario(holds, capsys, mutator, remote):
    mutator.unavailable_reason = "mutmut isn't installed"
    hold = holds.commit("R\n\nRedline-Step: add-greet/R", {"tests/test_greet.py": RED_TESTS, "test_hold.py": PASSING})
    code, out = ci(holds, capsys, "push", "--run-url", RUN)
    assert code == 1
    assert "check-break: GREET.H1: not mutated: mutmut isn't installed" in out
    assert yaml.safe_load(holds.git("notes", "--ref=redline-ci", "show", hold))["break"]["GREET.H1"] == "fail"


def test_the_red_step_gates_run_check_break_and_skip_check_order_for_hold(holds, capsys, mutator, github):
    merge_step(holds, "S")
    fresh_branch(holds, "red")
    assert start(holds, capsys, "add-greet/R")[0] == 0
    mutator.outcomes["GREET.H1"] = (2, 0)
    holds.commit("red tests", {"tests/test_greet.py": RED_TESTS, "test_hold.py": HOLD_TESTS})
    code, out = pr(holds, capsys)
    assert code == 1
    assert "check-break: GREET.H1: its tests survive every mutant" in out
    assert "check-break: GREET.H2" in out and "check-break: GREET.H3" in out
    assert "check-order" not in out


def test_check_break_does_not_run_at_a_green_step(holds, capsys, mutator, github):
    merge_step(holds, "S")
    merge_step(holds, "R")
    fresh_branch(holds, "g1")
    assert start(holds, capsys, "add-greet/G1")[0] == 0
    holds.commit("green", {"tests/test_greet.py": RED_TESTS, "test_hold.py": HOLD_TESTS})
    assert "check-break" not in pr(holds, capsys)[1]
    assert mutator.calls == []


def test_a_push_after_the_red_step_notes_each_break_and_fills_the_ledger(holds, capsys, mutator, remote, actions):
    mutator.outcomes["GREET.H3"] = (2, 0)
    hold = holds.commit("R\n\nRedline-Step: add-greet/R", {"tests/test_greet.py": RED_TESTS, "test_hold.py": PASSING})
    code, out = ci(holds, capsys, "push", "--run-url", RUN)
    assert code == 1
    assert "check-break: GREET.H3: its tests survive every mutant" in out
    noted = yaml.safe_load(holds.git("notes", "--ref=redline-ci", "show", hold))
    assert noted.pop("outcomes")["commit"] == hold
    assert noted == {"result": "pass", "run": RUN, "break": {"GREET.H1": "pass", "GREET.H2": "pass", "GREET.H3": "fail"}}
    actions.push_run(hold, "pass", noted["break"], RUN)
    assert main(["ledger", "add-greet", "--repo", str(holds.path)]) == 0
    scenarios = yaml.safe_load((holds.path / LEDGER).read_text(encoding="utf-8"))["scenarios"]
    assert scenarios["GREET.H1"] == {"red": None, "green": None, "break": {"commit": hold, "merged": hold, "result": "pass"}}
    assert scenarios["GREET.H3"]["break"]["result"] == "fail"
    assert scenarios["GREET.S1"]["break"] is None
    assert main(["check-ledger", "add-greet", "--repo", str(holds.path)]) == 0


def test_a_push_after_another_step_runs_no_mutation(holds, capsys, mutator, remote):
    merge_step(holds, "S")
    ci(holds, capsys, "push", "--run-url", RUN)
    assert mutator.calls == [] and "break" not in holds.git("notes", "--ref=redline-ci", "show", "HEAD")


def test_a_hold_break_without_a_noted_result_is_unverified_and_hand_edits_are_caught(holds, capsys):
    hold = holds.commit("R\n\nRedline-Step: add-greet/R", {"test_hold.py": HOLD_TESTS})
    note(holds, hold, "pass")  # a run that recorded no break
    assert main(["ledger", "add-greet", "--repo", str(holds.path)]) == 0
    path = holds.path / LEDGER
    entry = yaml.safe_load(path.read_text(encoding="utf-8"))["scenarios"]["GREET.H1"]
    assert entry["break"] == {"commit": hold, "merged": hold, "result": "unverified"}
    path.write_text(path.read_text(encoding="utf-8").replace("unverified", "pass"), encoding="utf-8")
    assert main(["check-ledger", "add-greet", "--repo", str(holds.path)]) == 1
    assert "GREET.H1 doesn't match the history of main" in capsys.readouterr().out
