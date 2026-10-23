import yaml

from conftest import FakeActions
from redline.cli import main
from test_start import CHANGE, change  # noqa: F401 (change is a fixture)

LEDGER = f"{CHANGE}/ledger.yaml"
RED = 'import pytest\n\n@pytest.mark.spec("GREET.S1", new=True)\ndef test_s1():\n    assert False\n'
GREEN = 'import pytest\n\n@pytest.mark.spec("GREET.S1")\ndef test_s1():\n    assert True\n'
NOTHING = {"red": None, "green": None, "break": None}


def land(repo, branch: str, files: dict[str, str]) -> tuple[str, str]:
    """Commit on a step branch and merge it into main as GitHub's merge button does."""
    repo.git("checkout", "-q", "main")
    repo.git("checkout", "-q", "-b", branch)
    commit = repo.commit(branch, files)
    repo.git("checkout", "-q", "main")
    repo.git("merge", "-q", "--no-ff", "--no-edit", branch)
    return commit, repo.git("rev-parse", "HEAD")


def note(repo, commit: str, result: str) -> None:
    """What CI records after a run on a merged commit, from the push run it names."""
    run = FakeActions.current.push_run(commit, result)
    repo.git("notes", "--ref=redline-ci", "add", "-f", "-m", f"result: {result}\nrun: {run}", commit)


def ledger(repo, capsys, command: str = "ledger") -> tuple[int, str]:
    code = main([command, "add-greet", "--repo", str(repo.path)])
    return code, capsys.readouterr().out


def rebuilt(repo, capsys) -> dict:
    code, out = ledger(repo, capsys)
    assert code == 0, out
    return yaml.safe_load((repo.path / LEDGER).read_text(encoding="utf-8"))


def test_every_scenario_of_the_change_is_listed_with_no_evidence_yet(change, capsys):
    change.commit("another change", {"redline/changes/other/specs/x/delta.md": "#### Scenario OTHER.S1 [new]: x\n"})
    assert rebuilt(change, capsys) == {
        "change": "add-greet",
        "scenarios": {"GREET.S1": NOTHING, "GREET.S2": NOTHING},
    }
    assert (change.path / LEDGER).read_text(encoding="utf-8").startswith("# A cache of evidence")


def test_a_manual_scenario_is_listed_with_no_evidence(change, capsys):
    delta = (change.path / f"{CHANGE}/specs/greet/delta.md").read_text(encoding="utf-8")
    change.commit("manual", {f"{CHANGE}/specs/greet/delta.md": delta + "\n#### Scenario GREET.M1 [manual]: looks right\n"
                                                                     "Manual: by eye\n- THEN it looks right\n"})
    assert rebuilt(change, capsys)["scenarios"] == {"GREET.S1": NOTHING, "GREET.S2": NOTHING, "GREET.M1": NOTHING}


def test_red_evidence_is_the_red_commit_the_merge_ci_ran_on_and_its_result(change, capsys):
    red, merge = land(change, "red", {"tests/test_greet.py": RED})
    note(change, merge, "pass")
    scenarios = rebuilt(change, capsys)["scenarios"]
    assert scenarios["GREET.S1"] == {"red": {"commit": red, "merged": merge, "result": "pass"}, "green": None, "break": None}
    assert scenarios["GREET.S2"] == NOTHING


def test_without_a_ci_note_the_result_is_unverified_and_a_failed_run_is_recorded(change, capsys):
    _, merge = land(change, "red", {"tests/test_greet.py": RED})
    assert rebuilt(change, capsys)["scenarios"]["GREET.S1"]["red"]["result"] == "unverified"
    note(change, merge, "fail")
    assert rebuilt(change, capsys)["scenarios"]["GREET.S1"]["red"]["result"] == "fail"


def test_green_evidence_and_a_commit_made_on_main_itself(change, capsys):
    red, red_merge = land(change, "red", {"tests/test_greet.py": RED})
    green = change.commit("green, squashed onto main", {"tests/test_greet.py": GREEN})
    note(change, red_merge, "pass")
    note(change, green, "pass")
    entry = rebuilt(change, capsys)["scenarios"]["GREET.S1"]
    assert entry["red"] == {"commit": red, "merged": red_merge, "result": "pass"}
    assert entry["green"] == {"commit": green, "merged": green, "result": "pass"}


def test_commits_not_merged_on_main_are_not_evidence(change, capsys):
    land(change, "red", {"tests/test_greet.py": RED})
    change.git("checkout", "-q", "-b", "green")
    change.commit("green, not merged yet", {"tests/test_greet.py": GREEN})
    assert rebuilt(change, capsys)["scenarios"]["GREET.S1"]["green"] is None


def test_check_ledger_fails_when_missing_or_stale_and_passes_once_rebuilt(change, capsys):
    code, out = ledger(change, capsys, "check-ledger")
    assert code == 1
    assert f"{LEDGER}: missing; run `redline ledger add-greet`" in out
    assert ledger(change, capsys)[0] == 0
    code, out = ledger(change, capsys, "check-ledger")
    assert code == 0, out
    assert "ok: 2 scenarios match the history of main" in out
    _, merge = land(change, "red", {"tests/test_greet.py": RED})
    note(change, merge, "pass")
    code, out = ledger(change, capsys, "check-ledger")
    assert code == 1
    assert f"{LEDGER}: GREET.S1 doesn't match the history of main; run `redline ledger add-greet`" in out
    assert "GREET.S2" not in out


def test_check_ledger_catches_a_hand_edited_result(change, capsys):
    _, merge = land(change, "red", {"tests/test_greet.py": RED})
    ledger(change, capsys)
    path = change.path / LEDGER
    path.write_text(path.read_text(encoding="utf-8").replace("unverified", "pass"), encoding="utf-8")
    code, out = ledger(change, capsys, "check-ledger")
    assert code == 1
    assert "GREET.S1 doesn't match" in out


def test_a_malformed_ci_note_or_an_unknown_change_is_an_error(change, capsys):
    _, merge = land(change, "red", {"tests/test_greet.py": RED})
    note(change, merge, "maybe")
    code, out = ledger(change, capsys)
    assert code == 2
    assert f"CI note on {merge[:7]} has no result: pass or fail" in out
    code, out = ledger(change, capsys, "check-ledger")
    assert code == 2
    assert main(["ledger", "no-such-change", "--repo", str(change.path)]) == 2
    assert "no scenarios declared in redline/changes/no-such-change" in capsys.readouterr().out
