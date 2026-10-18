from redline.cli import main
from redline.order import check_order

RED = 'import pytest\n\n@pytest.mark.spec("TOY.S1", new=True)\ndef test_it():\n    assert False\n'
GREEN = 'import pytest\n\n@pytest.mark.spec("TOY.S1")\ndef test_it():\n    assert True\n'


def statuses(repo):
    return {r.scenario: r.status for r in check_order(repo.path)}


def test_red_then_green_is_ok(repo):
    red = repo.commit("red", test_toy__py=RED)
    green = repo.commit("green", test_toy__py=GREEN)
    [result] = check_order(repo.path)
    assert (result.scenario, result.status, result.red, result.green) == ("TOY.S1", "ok", red, green)


def test_green_without_red_fails(repo):
    repo.commit("green", test_toy__py=GREEN)
    assert statuses(repo) == {"TOY.S1": "fail"}


def test_red_without_green_is_pending(repo):
    repo.commit("red", test_toy__py=RED)
    assert statuses(repo) == {"TOY.S1": "pending"}


def test_green_on_a_branch_without_the_red_commit_fails(repo):
    repo.commit("base", README="toy\n")
    repo.git("checkout", "-q", "-b", "red-branch")
    repo.commit("red", test_toy__py=RED)
    repo.git("checkout", "-q", "main")
    repo.commit("green", tests__test_other__py=GREEN)
    repo.git("merge", "-q", "--no-edit", "red-branch")
    assert statuses(repo) == {"TOY.S1": "fail"}


def test_cli_exit_code_and_report(repo, capsys):
    repo.commit("red", test_toy__py=RED)
    assert main(["check-order", "--repo", str(repo.path)]) == 0
    repo.commit("green", test_toy__py=GREEN)
    assert main(["check-order", "--repo", str(repo.path)]) == 0
    assert "ok TOY.S1" in capsys.readouterr().out
    repo.commit("green 2", test_two__py=GREEN.replace("TOY.S1", "TOY.S2"))
    assert main(["check-order", "--repo", str(repo.path)]) == 1
    assert "FAIL TOY.S2" in capsys.readouterr().out
