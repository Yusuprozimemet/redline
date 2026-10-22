import pytest

from redline import order
from redline.cli import main
from redline.order import check_order

RED = 'import pytest\n\n@pytest.mark.spec("TOY.S1", new=True)\ndef test_it():\n    assert False\n'
GREEN = 'import pytest\n\n@pytest.mark.spec("TOY.S1")\ndef test_it():\n    assert True\n'
COMMENTED = 'import pytest\n\n# @pytest.mark.spec("TOY.S1", new=True)\ndef test_it():\n    assert True\n'
QUOTED = 'import pytest\n\nTOY = """\n@pytest.mark.spec("TOY.S1", new=True)\ndef test_it():\n    assert False\n"""\n'


def statuses(repo):
    return {r.scenario: r.status for r in check_order(repo.path)}


def test_red_then_green_is_ok(repo):
    red = repo.commit("red", {"test_toy.py": RED})
    green = repo.commit("green", {"test_toy.py": GREEN})
    [result] = check_order(repo.path)
    assert (result.scenario, result.status, result.red, result.green) == ("TOY.S1", "ok", red, green)


def test_green_without_red_fails(repo):
    repo.commit("green", {"test_toy.py": GREEN})
    assert statuses(repo) == {"TOY.S1": "fail"}


def test_red_without_green_is_pending(repo):
    repo.commit("red", {"test_toy.py": RED})
    assert statuses(repo) == {"TOY.S1": "pending"}


def test_green_on_a_branch_without_the_red_commit_fails(repo):
    # Red lands on main first, so it is seen before green: only ancestry can catch this.
    repo.commit("base", {"README": "toy\n"})
    repo.git("checkout", "-q", "-b", "green-branch")
    repo.commit("green", {"tests/test_other.py": GREEN})
    repo.git("checkout", "-q", "main")
    red = repo.commit("red", {"test_toy.py": RED})
    repo.git("merge", "-q", "--no-edit", "green-branch")
    order = repo.git("rev-list", "--reverse", "--topo-order", "HEAD").split()
    assert order.index(red) < order.index(repo.git("rev-parse", "green-branch"))
    assert statuses(repo) == {"TOY.S1": "fail"}


def test_cli_exit_code_and_report(repo, capsys):
    repo.commit("red", {"test_toy.py": RED})
    assert main(["check-order", "--repo", str(repo.path)]) == 0
    repo.commit("green", {"test_toy.py": GREEN})
    assert main(["check-order", "--repo", str(repo.path)]) == 0
    assert "ok TOY.S1" in capsys.readouterr().out
    repo.commit("green 2", {"test_two.py": GREEN.replace("TOY.S1", "TOY.S2")})
    assert main(["check-order", "--repo", str(repo.path)]) == 1
    assert "FAIL TOY.S2" in capsys.readouterr().out


@pytest.mark.parametrize("red", [COMMENTED, QUOTED], ids=["commented", "quoted"])
def test_a_marker_in_a_comment_or_a_string_makes_no_red(repo, red):
    repo.commit("no red", {"test_toy.py": red})
    assert statuses(repo) == {}
    repo.commit("green", {"test_toy.py": GREEN})
    assert statuses(repo) == {"TOY.S1": "fail"}


def test_a_file_that_doesnt_parse_at_a_commit_is_skipped_with_a_note(repo, capsys):
    red = repo.commit("red", {"test_toy.py": RED})
    broken = repo.commit("broken", {"test_toy.py": RED + "def (:\n"})
    green = repo.commit("green", {"test_toy.py": GREEN})
    [result] = check_order(repo.path)
    assert (result.status, result.red, result.green) == ("ok", red, green)
    assert main(["check-order", "--repo", str(repo.path)]) == 0
    assert f"skipped test_toy.py at {broken[:7]}: invalid syntax" in capsys.readouterr().out


def test_a_scenario_no_test_links_any_more_is_skipped_not_failed(repo, capsys):
    green = repo.commit("green", {"test_toy.py": GREEN})
    (repo.path / "test_toy.py").unlink()
    repo.commit("test gone")
    [result] = check_order(repo.path)
    assert (result.status, result.linked) == ("fail", False)
    assert order.failed([result], set()) == []
    assert main(["check-order", "--repo", str(repo.path)]) == 0
    assert f"skipped TOY.S1: no test at HEAD links it; its green {green[:7]} had no red" in capsys.readouterr().out


def test_a_scenario_linked_again_fails_again(repo):
    repo.commit("green", {"test_toy.py": GREEN})
    (repo.path / "test_toy.py").unlink()
    repo.commit("test gone")
    repo.commit("back", {"test_toy.py": GREEN})
    [result] = check_order(repo.path)
    assert result.linked and order.failed([result], set()) == [result]


def test_the_command_skips_a_hold_scenario_as_the_gate_does(repo, capsys):
    repo.commit("hold", {"redline/specs/toy/spec.md": "#### Scenario TOY.S1 [hold]: holds\n- THEN it holds\n",
                         "test_toy.py": GREEN})
    [result] = check_order(repo.path)
    assert result.status == "fail" and order.failed([result], {"TOY.S1"}) == []
    assert main(["check-order", "--repo", str(repo.path)]) == 0
    assert "hold TOY.S1: no red by design" in capsys.readouterr().out
