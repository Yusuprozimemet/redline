import pytest

from redline.cli import main
from redline.pr import gates
from test_merged import branch, merged, on_step, remote  # noqa: F401 (remote is a fixture)
from test_pr import AUDIT, begin, github, pr  # noqa: F401 (github is a fixture)
from test_start import CHANGE, change, merge_step, start, fresh_branch  # noqa: F401 (change is a fixture)

LOG = f"{CHANGE}/defects.md"
VALID = """# Defects: add-greet

## D1: the greeting cited the placeholder, not greet
Cause: premise
Found-by: add-greet/G1
P1 named the wrong function.

## D2: GREET.S2 passed before the code existed
Cause: test
Found-by: add-greet/R

## D3: a crowd of one was greeted twice
Cause: premise
Found-by: add-greet/G2
"""


def run(repo, capsys, *args: str) -> tuple[int, str]:
    code = main([*args, "--repo", str(repo.path)])
    return code, capsys.readouterr().out


def test_a_valid_log_passes(change, capsys):
    change.commit("log", {LOG: VALID})
    code, out = run(change, capsys, "check-defects", "add-greet")
    assert code == 0, out
    assert out.startswith("ok: 3 defects")


def test_an_empty_log_passes(change, capsys):
    change.commit("log", {LOG: "# Defects: add-greet\n\nNone found.\n"})
    assert run(change, capsys, "check-defects", "add-greet")[0] == 0


def test_found_by_a_commit_on_main_passes_but_not_one_on_a_branch(change, capsys):
    on_main = change.commit("a fix on main")
    fresh_branch(change, "side")
    on_branch = change.commit("a fix on a branch")
    entry = "## D1: wrong\nCause: code\nFound-by: {}\n"
    change.commit("log", {LOG: entry.format(on_main[:7])})
    assert run(change, capsys, "check-defects", "add-greet")[0] == 0
    change.commit("log", {LOG: entry.format(on_branch)})
    code, out = run(change, capsys, "check-defects", "add-greet")
    assert code == 1
    assert f"D1: Found-by: {on_branch} names no step and no commit on main" in out


@pytest.mark.parametrize(("log", "message"), [
    (VALID.replace("## D2: GREET", "## GREET"), ":8: not a defect; a defect is `## D<n>: <text>`"),
    (VALID.replace("## D3", "## D1"), ":12: D1 is repeated (first at line 3)"),
    (VALID.replace("Cause: test\n", ""), "D2 has no Cause: line"),
    (VALID.replace("Cause: test\n", "Cause: test\nCause: code\n"), "D2 has more than one Cause: line"),
    (VALID.replace("Cause: test", "Cause: haste"), "D2: Cause: haste is not one of premise, spec, test"),
    (VALID.replace("Found-by: add-greet/R\n", ""), "D2 has no Found-by: line"),
    (VALID.replace("add-greet/R", "add-greet/G9"), "D2: Found-by: add-greet/G9 names no step and no commit"),
], ids=["heading", "repeated", "no-cause", "two-causes", "unknown-cause", "no-found-by", "unknown-step"])
def test_a_broken_log_fails(change, capsys, log, message):
    change.commit("log", {LOG: log})
    code, out = run(change, capsys, "check-defects", "add-greet")
    assert code == 1
    assert message in out
    assert out.startswith(LOG)


def test_a_missing_log_fails_except_at_lite(change, capsys):
    code, out = run(change, capsys, "check-defects", "add-greet")
    assert code == 1
    assert f"{LOG}: missing" in out
    change.commit("lite", {f"{CHANGE}/proposal.md": "Rigor: lite\n"})
    assert run(change, capsys, "check-defects", "add-greet")[0] == 0


def test_the_gates_require_the_log_at_c_only(change):
    def missing(step):
        return [f for f in gates(change.path, "add-greet", step) if f.startswith("check-defects:")]
    assert missing("S") == []
    assert missing("C") == [f"check-defects: {LOG}: missing; at C a change keeps a defect log"]


def test_pr_refuses_a_broken_log_at_any_step(change, capsys, github):
    begin(change, capsys, "S", "spec")
    change.commit("audit and a log", {**AUDIT, LOG: VALID.replace("Cause: test", "Cause: haste")})
    code, out = pr(change, capsys)
    assert code == 1
    assert f"check-defects: {LOG}:" in out


def test_retro_groups_by_cause_and_proposes_one_rule_per_cause(change, capsys):
    config = "rules:\n  test:\n    - Run a new test once before marking it\n"
    change.commit("log", {LOG: VALID, "redline/config.yaml": config})
    code, out = run(change, capsys, "retro", "add-greet")
    assert code == 0, out
    assert out.index("premise: 2 (D1, D3); 0 rules so far") < out.index("test: 1 (D2); 1 rule so far")
    assert "  D1: the greeting cited the placeholder, not greet" in out
    assert "1. Add a rule under rules.premise against D1, D3" in out
    assert "2. Add a rule under rules.test against D2" in out
    assert "retro changes nothing" in out
    assert change.git("status", "--porcelain") == ""
    assert (change.path / "redline/config.yaml").read_text() == config


def test_retro_with_no_defects_proposes_nothing(change, capsys):
    change.commit("log", {LOG: "# Defects: add-greet\n"})
    code, out = run(change, capsys, "retro", "add-greet")
    assert code == 0, out
    assert "add-greet has no defects; nothing to propose" in out


def test_retro_refuses_a_broken_or_missing_log_whatever_the_level(change, capsys):
    change.commit("lite", {f"{CHANGE}/proposal.md": "Rigor: lite\n"})
    code, out = run(change, capsys, "retro", "add-greet")
    assert code == 1
    assert f"{LOG}: missing" in out
    change.commit("log", {LOG: VALID.replace("Cause: test", "Cause: haste")})
    assert run(change, capsys, "retro", "add-greet")[0] == 1


def test_the_brief_prints_the_rules(change, capsys):
    rules = "rules:\n  premise:\n    - Cite where a value is stored\n  code:\n    - Keep it small\n"
    change.commit("rules", {"redline/config.yaml": rules})
    fresh_branch(change, "spec")
    code, out = start(change, capsys, "add-greet/S")
    assert code == 0, out
    assert "## Rules\n- premise: Cite where a value is stored\n- code: Keep it small\n" in out


def test_closing_a_change_says_retro_comes_next(change, capsys, remote):
    for step in ("S", "R", "G1", "G2"):
        merge_step(change, step)
    remote.landing = "add-greet/C"
    on_step(change, capsys, "C", "close")
    code, out = merged(change, capsys, "add-greet/C")
    assert code == 0, out
    assert "Run `redline retro add-greet`" in out
