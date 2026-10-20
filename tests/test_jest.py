"""Jest beside pytest: the spec helper, and its markers in the links, the order and the lock. See docs/design.md, §5."""

import hashlib
from importlib.resources import files

import yaml

from redline.cli import main
from redline.order import check_order
from redline.pr import gates
from test_check_break import check_break, holds, mutator  # noqa: F401 (fixtures)
from test_lock import LOCK, check_lock, lock
from test_start import CHANGE, change  # noqa: F401 (change is a fixture)

HELPER = "redline/runners/jest.js"
H1 = """spec("GREET.H1").test('returns nothing (or ")")', () => {
  expect(`${placeholder()} {`).toBe("undefined {"); // a ) in a comment
})"""
JEST = ('const { spec } = require("./redline/runners/jest");\nconst { placeholder } = require("./greet");\n\n' + H1
        + ';\n\nspec("GREET.H2", { new: true }).test("takes no arguments", () => {\n  expect(() => placeholder(1)).toThrow();\n});\n')
NAME = 'greet.test.ts::returns nothing (or ")")'


def install(repo) -> int:
    return main(["install", "jest", "--repo", str(repo.path)])


def test_install_jest_writes_the_helper_redline_ships(repo, capsys):
    repo.commit("start")
    assert install(repo) == 0
    shipped = files("redline").joinpath("helpers", "jest.js").read_text(encoding="utf-8")
    assert (repo.path / HELPER).read_text(encoding="utf-8") == shipped
    assert "test.failing" in shipped and "REDLINE_SPEC" in shipped
    assert f"ok: wrote {HELPER}" in capsys.readouterr().out


def test_every_gate_fails_on_an_edited_helper(change, capsys):
    install(change)
    assert not [bad for bad in gates(change.path, "add-greet", "S") if bad.startswith("check-helpers")]
    path = change.path / HELPER
    path.write_text(path.read_text(encoding="utf-8").replace("test.failing", "test"), encoding="utf-8")
    failures = gates(change.path, "add-greet", "S")
    assert f"check-helpers: {HELPER} differs from the helper Redline ships; run `redline install jest`" in failures


def test_check_links_reads_jest_markers_in_jest_files_only(repo, capsys):
    repo.commit("spec", {
        "redline/specs/greet/spec.md": "#### Scenario GREET.S1 [hold]: greets\n- THEN hi\n",
        "greet.test.ts": 'spec("GREET.S1").test("greets", () => {});\nspec("GREET.S9").test("unknown", () => {});\n',
        "test_greet.py": 'spec("GREET.S8").test("not a pytest marker")\n',
    })
    code = main(["check-links", "--repo", str(repo.path)])
    out = capsys.readouterr().out
    assert code == 1
    assert "unlinked scenario GREET.S1" not in out
    assert "unknown scenario GREET.S9 (greet.test.ts:2)" in out
    assert "GREET.S8" not in out


def test_check_order_reads_jest_red_and_green(repo):
    red = repo.commit("red", {"greet.test.js": 'spec("TOY.S1", { new: true }).test("t", () => {});\n'})
    green = repo.commit("green", {"greet.test.js": 'spec("TOY.S1").test("t", () => {});\n'})
    [result] = check_order(repo.path)
    assert (result.scenario, result.status, result.red, result.green) == ("TOY.S1", "ok", red, green)


def test_lock_hashes_a_jest_test_from_spec_to_the_end_of_its_test_call(holds, capsys):
    holds.commit("jest", {"greet.test.ts": JEST})
    lock(holds, capsys)
    locked = yaml.safe_load((holds.path / LOCK).read_text(encoding="utf-8"))["add-greet"]
    assert locked == {"GREET.H1": {NAME: hashlib.sha256(f"{H1}\n".encode()).hexdigest()}}  # H2 is new
    holds.commit("outside the test", {"greet.test.ts": "// a header\n" + JEST})
    assert check_lock(holds, capsys)[0] == 0
    holds.commit("weaken", {"greet.test.ts": JEST.replace('toBe("undefined {")', "toBeDefined()")})
    code, out = check_lock(holds, capsys)
    assert code == 1
    assert f"GREET.H1: {NAME} changed since it was locked" in out


def test_a_jest_test_whose_brackets_never_close_is_an_error(holds, capsys):
    holds.commit("jest", {"greet.test.ts": 'spec("GREET.H1").test("t", () => {\n  expect(`)`).toBe(1);\n'})
    code = main(["lock", "add-greet", "--repo", str(holds.path)])
    out = capsys.readouterr().out
    assert code == 2
    assert "redline: greet.test.ts:1: the brackets opened here never close" in out


def test_at_critical_a_jest_test_is_locked_without_reach_and_check_lock_says_so(holds, capsys):
    holds.commit("critical", {f"{CHANGE}/proposal.md": "# add-greet\nRigor: critical\n", "greet.test.ts": JEST})
    lock(holds, capsys)
    code, out = check_lock(holds, capsys)
    assert code == 1
    assert f"GREET.H1: {NAME} is locked without what it reaches; a Jest test has no reach yet (O-RUN3)" in out


def test_check_break_fails_a_scenario_with_a_jest_test_until_jest_runs(holds, capsys, mutator):
    holds.commit("jest", {"greet.test.ts": JEST})
    code, out = check_break(holds, capsys)
    assert code == 1
    assert "GREET.H1: its tests include Jest tests, which check-break can't run yet (O-RUN1)" in out
    assert mutator.calls == []
