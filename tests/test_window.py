"""A change's evidence is its own: only the PRs from its S step to its C step count (§4)."""

from redline.ledger import rebuild
from test_close import HELD, HOLD, TESTS, close
from test_ledger import land, note
from test_start import CHANGE, change  # noqa: F401 (change is a fixture)

RED, GREEN = TESTS.replace("{new}", ", new=True"), TESTS.replace("{new}", "")


def step(repo, name: str, files: dict[str, str] | None = None) -> tuple[str, str]:
    """Land one commit of the step `name` with its Redline-Step trailer, merged as GitHub does."""
    branch = name.replace("/", "-")
    repo.git("checkout", "-q", "-b", branch)
    commit = repo.commit(f"{name}\n\nRedline-Step: {name}", files)
    repo.git("checkout", "-q", "main")
    repo.git("merge", "-q", "--no-ff", "--no-edit", branch)
    return commit, repo.git("rev-parse", "HEAD")


def earlier(repo) -> None:
    """An earlier change made GREET.S1 and S2 red, then green, and CI passed both."""
    for branch, tests in (("old-red", RED), ("old-green", GREEN)):
        note(repo, land(repo, branch, {"tests/test_greet.py": tests})[1], "pass")


def test_a_later_change_that_never_makes_the_scenario_red_again_has_no_evidence(change, capsys):
    earlier(change)
    step(change, "add-greet/S")
    code, out = close(change, capsys)
    assert code == 1
    assert out == ("GREET.S1: no red on main\nGREET.S1: no green on main\n"
                   "GREET.S2: no red on main\nGREET.S2: no green on main\n")


def test_a_later_change_is_paired_with_its_own_red_and_the_s_prs_own_commits_count(change):
    earlier(change)
    red, _ = step(change, "add-greet/S", {"tests/test_greet.py": RED})  # as at lite, S and R in one PR
    green, _ = step(change, "add-greet/G1", {"tests/test_greet.py": GREEN})
    entry = rebuild(change.path, "add-greet")["scenarios"]["GREET.S1"]
    assert (entry["red"]["commit"], entry["green"]["commit"]) == (red, green)


def test_a_closed_changes_ledger_stays_as_it_was(change):
    step(change, "add-greet/S")
    step(change, "add-greet/R", {"tests/test_greet.py": RED})
    step(change, "add-greet/G1", {"tests/test_greet.py": GREEN})
    step(change, "add-greet/C")
    before = rebuild(change.path, "add-greet")
    land(change, "later-red", {"tests/test_greet.py": RED})
    land(change, "later-green", {"tests/test_greet.py": GREEN})
    assert rebuild(change.path, "add-greet") == before


def test_a_modified_hold_scenarios_break_is_the_later_changes_r_step(change, actions):
    change.commit("a hold scenario", {f"{CHANGE}/specs/greet/delta.md": HOLD})
    _, old = land(change, "old-hold", {"tests/test_hold.py": HELD})
    run = actions.push_run(old, "pass", {"GREET.H1": "pass"})
    change.git("notes", "--ref=redline-ci", "add", "-m", f"result: pass\nrun: {run}\nbreak:\n  GREET.H1: pass\n", old)
    step(change, "add-greet/S")
    assert rebuild(change.path, "add-greet")["scenarios"]["GREET.H1"]["break"] is None
    commit, merged = step(change, "add-greet/R", {"tests/test_greet.py": RED})
    run = actions.push_run(merged, "pass", {"GREET.H1": "fail"})
    change.git("notes", "--ref=redline-ci", "add", "-m", f"result: pass\nrun: {run}\nbreak:\n  GREET.H1: fail\n", merged)
    entry = rebuild(change.path, "add-greet")["scenarios"]["GREET.H1"]
    assert entry["break"] == {"commit": commit, "merged": merged, "result": "fail"}
