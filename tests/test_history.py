"""History is read in a fixed number of git calls, however long it is (O-PERF1, §4, §5)."""

import subprocess

from conftest import Repo
from redline.claims import claims
from redline.ledger import rebuild
from redline.order import check_order
from test_check_order import GREEN, RED
from test_claims import github, land_claims  # noqa: F401 (github is a fixture)
from test_ledger import land
from test_plan import FAREWELL, PLAN, VALID, WAVE
from test_start import CHANGE, DELTA, STEPS
from test_window import GREEN as GREETED, RED as GREETING, step


def calls(monkeypatch, read) -> int:
    """How many git processes `read` starts, with no blob's markers read before."""
    count = 0
    run = subprocess.run

    def counting(args, *rest, **options):
        nonlocal count
        count += args[0] == "git"
        return run(args, *rest, **options)

    with monkeypatch.context() as patched:
        patched.setattr("redline.order.READ", {})
        patched.setattr(subprocess, "run", counting)
        read()
    return count


def change(repo: Repo, fillers: int, files: dict[str, str] | None = None) -> Repo:
    """A change on main, then `fillers` merged PRs that touch no test: main's first-parent line grows."""
    repo.commit("add-greet spec", {f"{CHANGE}/steps.md": STEPS, f"{CHANGE}/specs/greet/delta.md": DELTA,
                                   "greet.py": "def placeholder():\n    pass\n", **(files or {})})
    for n in range(fillers):
        land(repo, f"filler-{n}", {"README": f"{n}\n"})
    return repo


def test_check_order_reads_a_history_where_one_commit_of_many_touches_a_test_in_as_many_calls(tmp_path, monkeypatch):
    counted = []
    for fillers in (3, 30):
        repo = Repo(tmp_path / f"toy-{fillers}")
        repo.commit("red", {"test_toy.py": RED})
        for n in range(fillers):
            repo.commit(f"filler {n}", {"README": f"{n}\n"})
        repo.commit("green", {"test_toy.py": GREEN})
        counted.append(calls(monkeypatch, lambda: check_order(repo.path)))
        assert [(r.scenario, r.status) for r in check_order(repo.path)] == [("TOY.S1", "ok")]
    assert counted[0] == counted[1], f"git calls for 3 and 30 commits that touch no test: {counted}"


def test_the_ledger_finds_each_commits_merge_in_as_many_calls_however_long_main_is(tmp_path, monkeypatch):
    counted = []
    for fillers in (3, 30):
        repo = change(Repo(tmp_path / f"toy-{fillers}"), fillers)
        step(repo, "add-greet/S")
        red, _ = step(repo, "add-greet/R", {"tests/test_greet.py": GREETING})
        green, _ = step(repo, "add-greet/G1", {"tests/test_greet.py": GREETED})
        counted.append(calls(monkeypatch, lambda: rebuild(repo.path, "add-greet")))
        entry = rebuild(repo.path, "add-greet")["scenarios"]["GREET.S1"]
        assert (entry["red"]["commit"], entry["green"]["commit"]) == (red, green)
    assert counted[0] == counted[1], f"git calls for 3 and 30 merges before the change's: {counted}"


def test_claims_finds_each_claims_merge_in_as_many_calls_however_long_main_is(tmp_path, monkeypatch, github):
    counted = []
    for fillers in (3, 30):
        repo = change(Repo(tmp_path / f"toy-{fillers}"), fillers, {PLAN: VALID, **FAREWELL, **WAVE})
        _, _, merge = land_claims(repo)
        counted.append(calls(monkeypatch, lambda: claims(repo.path, "greetings")))
        assert f"no CI note on {merge[:7]}" in claims(repo.path, "greetings")
    assert counted[0] == counted[1], f"git calls for 3 and 30 merges before the claim's: {counted}"
