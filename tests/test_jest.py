"""Jest beside pytest: the spec helper, its markers in the links, the order and the lock, and its runs in
check-break, with Jest's run faked. See specs/, §5."""

import hashlib
import shutil
import subprocess
from importlib.resources import files

import pytest
import yaml

from redline import breaks
from redline.ci import suite
from redline.cli import main
from redline.order import check_order
from redline.pr import gates
from test_ci import RUN, ci, remote  # noqa: F401 (remote is a fixture)
from test_check_break import HOLD_TESTS, HOLDS, FakeMutator, check_break, delta, holds, mutator  # noqa: F401 (fixtures)
from test_lock import LOCK, check_lock, lock
from test_start import CHANGE, change, fresh_branch  # noqa: F401 (change is a fixture)

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


UNREAD = {
    "line comment": '// spec("TOY.S1", { new: true }).test("t", () => {});\n',
    "block comment": '/* a draft:\n  spec("TOY.S1", { new: true }).test("t", () => {});\n*/\n',
    "string": 'const draft = \'spec("TOY.S1", { new: true }).test("t", () => {})\';\n',
    "template": 'const draft = `\n  spec("TOY.S1", { new: true }).test("t", () => {});\n`;\n',
}
TOY_SPEC = {"redline/specs/toy/spec.md": "#### Scenario TOY.S1 [new]: toy\n- THEN it works\n"}


@pytest.mark.parametrize("red", UNREAD.values(), ids=UNREAD.keys())
def test_a_jest_marker_in_a_comment_or_a_string_makes_no_red(repo, red):
    repo.commit("no red", {"greet.test.js": red})
    assert check_order(repo.path) == []
    repo.commit("green", {"greet.test.js": 'spec("TOY.S1").test("t", () => {});\n'})
    [result] = check_order(repo.path)
    assert (result.scenario, result.status) == ("TOY.S1", "fail")


@pytest.mark.parametrize("text", UNREAD.values(), ids=UNREAD.keys())
def test_a_jest_marker_in_a_comment_or_a_string_links_nothing(repo, capsys, text):
    repo.commit("unlinked", {**TOY_SPEC, "greet.test.js": text})
    assert main(["check-links", "--repo", str(repo.path)]) == 1
    assert "unlinked scenario TOY.S1 (redline/specs/toy/spec.md:1): no test has a spec marker for it" in capsys.readouterr().out


def test_a_jest_marker_in_a_templates_code_counts(repo):
    red = repo.commit("red", {"greet.test.js": 'const all = `${spec("TOY.S1", { new: true }).test("t", () => {})}`;\n'})
    green = repo.commit("green", {"greet.test.js": 'spec("TOY.S1").test("t", () => {});\n'})
    [result] = check_order(repo.path)
    assert (result.status, result.red, result.green) == ("ok", red, green)


@pytest.mark.parametrize("text, kind", [("const re = /`/;\n", "template"), ("const re = /x\\/*/;\n", "comment")],
                         ids=["template", "block comment"])
def test_a_template_or_block_comment_never_closed_is_a_gap(repo, capsys, text, kind):
    repo.commit("unclosed", {**TOY_SPEC, "greet.test.js": text + 'spec("TOY.S1").test("t", () => {});\n'})
    assert main(["check-links", "--repo", str(repo.path)]) == 1
    out = capsys.readouterr().out
    assert f"unreadable test file greet.test.js: greet.test.js:1: the {kind} opened here never closes" in out


def test_a_commented_out_jest_hold_marker_locks_nothing(holds, capsys):
    holds.commit("jest", {"greet.test.ts": JEST.replace(H1, f"/*\n{H1}\n*/")})
    lock(holds, capsys)
    assert "greet.test.ts" not in (holds.path / LOCK).read_text(encoding="utf-8")


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


class FakeJest:
    """Stands in for `npx --no-install jest --ci`: the run fails for each REDLINE_SPEC in `failing` (None for
    a run of every test); any other command runs for real. Without `npx`, shutil.which finds none."""

    def __init__(self, run):
        self.real, self.failing, self.runs, self.npx = run, set(), [], True

    def __call__(self, argv, *args, **kwargs):
        if list(argv[1:3]) != ["--no-install", "jest"]:
            return self.real(argv, *args, **kwargs)
        self.runs.append((kwargs.get("env") or {}).get("REDLINE_SPEC"))
        failed = self.runs[-1] in self.failing
        return subprocess.CompletedProcess(argv, int(failed), "", "Tests:       1 failed, 1 total" if failed else "")


@pytest.fixture
def jest(monkeypatch) -> FakeJest:
    fake, which = FakeJest(subprocess.run), shutil.which
    monkeypatch.setattr(subprocess, "run", fake)
    monkeypatch.setattr(shutil, "which", lambda name, *a, **k: (fake.npx and "/bin/npx") if name == "npx" else which(name, *a, **k))
    monkeypatch.delenv("REDLINE_SPEC", raising=False)
    return fake


H1_ONLY = HOLDS.split("#### Scenario GREET.H2")[0]
JS_PREMISE = "- P3: The placeholder in JavaScript — `greet.js:1`\n"


@pytest.fixture
def jest_holds(holds):
    holds.commit("jest", {f"{CHANGE}/specs/greet/delta.md": delta(H1_ONLY) + JS_PREMISE, "greet.test.ts": JEST,
                          "greet.js": "function placeholder() {}\nmodule.exports = { placeholder };\n"})
    return holds


def test_check_break_runs_a_scenarios_jest_tests_alone_then_mutates_the_cited_javascript(jest_holds, capsys, mutator, jest):
    code, out = check_break(jest_holds, capsys)
    assert code == 0, out
    assert "ok: 1 hold scenario(s): tests pass unmutated and fail under a mutant" in out
    assert jest.runs == ["GREET.H1"]
    assert mutator.calls == [(["greet.js"], "GREET.H1")]  # greet.py is pytest's, and no pytest test links GREET.H1


def test_jest_tests_that_fail_or_cant_start_unmutated_fail_the_scenario(jest_holds, capsys, mutator, jest):
    jest.failing.add("GREET.H1")
    assert "GREET.H1: its jest tests fail on unmutated code" in check_break(jest_holds, capsys)[1]
    jest.npx = False
    code, out = check_break(jest_holds, capsys)
    assert code == 1
    assert "GREET.H1: its jest tests can't run: npx isn't installed" in out
    assert mutator.calls == [] and jest.runs == ["GREET.H1"]


def test_a_scenario_with_tests_in_both_runners_adds_up_their_kills(jest_holds, capsys, mutator, jest):
    jest_holds.commit("pytest too", {"test_hold.py": HOLD_TESTS.split('@pytest.mark.spec("GREET.H2"')[0]})
    mutmut = breaks.MUTATORS["pytest"] = FakeMutator()
    mutmut.unavailable_reason = "mutmut doesn't run on Windows"
    code, out = check_break(jest_holds, capsys)
    assert code == 0 and "skipped" not in out, out  # Stryker killed one, so mutmut's absence changes nothing
    mutator.outcomes["GREET.H1"] = (4, 0)
    code, out = check_break(jest_holds, capsys)
    assert code == 0, out
    assert "skipped GREET.H1: mutmut doesn't run on Windows; CI runs the mutation" in out
    mutmut.unavailable_reason, mutator.calls = None, []
    assert check_break(jest_holds, capsys)[0] == 0
    assert mutmut.calls == [(["greet.py"], "GREET.H1")] and mutator.calls == []  # the first kill is enough
    mutmut.outcomes["GREET.H1"] = (3, 0)
    code, out = check_break(jest_holds, capsys)
    assert code == 1
    assert "GREET.H1: its tests survive every mutant (0 of 7 killed, in greet.py, greet.js)" in out
    jest.failing.add("GREET.H1")  # pytest's run passes, Jest's doesn't
    assert "GREET.H1: its jest tests fail on unmutated code" in check_break(jest_holds, capsys)[1]


def test_a_scenario_whose_runners_have_no_cited_file_has_nothing_to_mutate(jest_holds, capsys, mutator, jest):
    jest_holds.commit("no JS premise", {f"{CHANGE}/specs/greet/delta.md": delta(H1_ONLY)})
    code, out = check_break(jest_holds, capsys)
    assert code == 1
    assert "GREET.H1: nothing to mutate: the change's premises cite no file its tests' runners mutate" in out
    assert mutator.calls == []


def test_a_departure_can_name_a_jest_test_whose_name_has_spaces(holds, capsys):
    holds.commit("jest", {"greet.test.ts": JEST})
    lock(holds, capsys)
    holds.commit("locked")
    fresh_branch(holds, "g1")
    holds.commit("edit", {"greet.test.ts": JEST.replace('toBe("undefined {")', 'toBe("undefined {") ')})
    lock(holds, capsys)
    holds.commit(f"relock\n\nRedline-Departure: {NAME} approved-by @maintainer: a space after the assertion")
    code, out = check_lock(holds, capsys, "--base", "main")
    assert code == 0, out
    assert "CI will need the `redline:departure` label applied by @maintainer, a maintainer" in out


PACKAGE = '{"devDependencies": {"jest": "29.7.0"}}\n'
NOTHING_RAN = "suite: no tests ran: git tracks no pytest test file, and package.json doesn't list jest"


def test_the_suite_runs_jest_when_package_json_lists_it_and_pytest_only_with_its_test_files(repo, jest):
    repo.commit("jest only", {"package.json": PACKAGE, "greet.test.js": ""})
    (repo.path / "node_modules" / "jest").mkdir(parents=True)
    assert suite(repo.path) == []  # no pytest test file, so no pytest run that collects nothing
    assert jest.runs == [None]
    jest.failing.add(None)
    assert suite(repo.path) == ["suite: the test suite failed (jest exit 1): Tests:       1 failed, 1 total"]
    repo.commit("pytest too", {"test_ok.py": "def test_ok():\n    assert False\n", "package.json": '{"dependencies": {}}\n'})
    jest.runs = []
    assert suite(repo.path)[0].startswith("suite: the test suite failed (pytest exit 1)")
    assert jest.runs == []


def test_jest_listed_but_not_installed_fails_the_suite(repo, jest):
    repo.commit("jest listed", {"package.json": PACKAGE})
    assert suite(repo.path) == ["suite: jest is listed in package.json, but node_modules/jest isn't installed"]
    jest.npx = False
    assert suite(repo.path) == ["suite: jest is listed in package.json, but npx isn't installed"]
    assert jest.runs == []


def test_a_repository_that_uses_no_runner_fails_the_suite(repo, jest):
    repo.commit("no tests", {"greet.js": "", "package.json": '{"devDependencies": {"eslint": "9.0.0"}}\n'})
    assert suite(repo.path) == [NOTHING_RAN]
    assert jest.runs == []


def test_a_push_notes_a_failed_jest_suite(repo, capsys, jest, remote):
    repo.commit("start")
    merge = repo.commit("jest", {"package.json": PACKAGE, "greet.test.js": ""})
    (repo.path / "node_modules" / "jest").mkdir(parents=True)
    jest.failing.add(None)
    code, out = ci(repo, capsys, "push", "--run-url", RUN)
    assert code == 1
    assert "suite: the test suite failed (jest exit 1)" in out
    assert remote.pushed == [f"result: fail\nrun: {RUN}"]
    assert repo.git("notes", "--ref=redline-ci", "show", merge) == f"result: fail\nrun: {RUN}"
