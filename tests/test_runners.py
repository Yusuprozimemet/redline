"""The real Jest and Stryker on the toy project in tests/toys/jest. Skipped unless REDLINE_REAL_RUNNERS=1,
which `runners` and the evidence-counting push run set after `npm ci` there; with it, a missing tool fails. They prove the helper,
REDLINE_SPEC, Stryker's counts, and check-break end to end on a git repository holding the toy.
See specs/, §5."""

import os
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from redline.breaks import Stryker, check_break
from redline.runner import install

TOY = Path(__file__).parent / "toys" / "jest"
pytestmark = pytest.mark.skipif(os.environ.get("REDLINE_REAL_RUNNERS") != "1",
                                reason="the real Jest and Stryker run in runners and evidence-counting push CI")
# Written by the toy fixture, never committed or read in Redline's tree: no spec there declares TOY.H1 or TOY.H2 (O-SELF5)
TESTS = """const { spec } = require("../redline/runners/jest");
const { adult } = require("./adult");

spec("TOY.H1").test("a grown-up is an adult", () => {
  expect(adult(30)).toBe(true);
});

spec("TOY.H2").test("an adult starts at 18", () => {
  expect(adult(18)).toBe(true);
  expect(adult(17)).toBe(false);
});
"""


@pytest.fixture(scope="module")
def toy():
    install(TOY, "jest")
    (TOY / "src" / "adult.test.js").write_text(TESTS, encoding="utf-8")
    yield TOY
    shutil.rmtree(TOY / "redline")
    (TOY / "src" / "adult.test.js").unlink()


def jest(toy, *paths, sid=None) -> subprocess.CompletedProcess:
    npx = shutil.which("npx")
    assert npx, "npx isn't installed"
    env = {key: value for key, value in os.environ.items() if key != "REDLINE_SPEC"}
    env |= {"REDLINE_SPEC": sid} if sid else {}
    return subprocess.run([npx, "--no-install", "jest", "--ci", *paths], cwd=toy, capture_output=True,
                          encoding="utf-8", errors="replace", env=env)


def test_jest_runs_every_test_and_doesnt_take_the_helper_for_a_test_file(toy):
    done = jest(toy)
    assert done.returncode == 0, done.stderr
    assert "Test Suites: 1 passed, 1 total" in done.stderr
    assert "Tests:       2 passed, 2 total" in done.stderr


def test_redline_spec_runs_one_scenarios_tests_alone(toy):
    done = jest(toy, sid="TOY.H1")
    assert done.returncode == 0, done.stderr
    assert "Tests:       1 skipped, 1 passed, 2 total" in done.stderr


@pytest.mark.parametrize("expected, code", [("2", 0), ("1", 1)])
def test_a_new_test_runs_as_test_failing_so_one_that_passes_fails_the_run(toy, expected, code):
    path = toy / "src" / "new.test.js"
    path.write_text('const { spec } = require("../redline/runners/jest");\n\n'
                    f'spec("TOY.S1", {{ new: true }}).test("not built yet", () => {{\n  expect(1).toBe({expected});\n}});\n')
    try:
        done = jest(toy, "src/new.test.js")
    finally:
        path.unlink()
    assert done.returncode == code, done.stderr


def test_stryker_kills_only_what_the_scenarios_tests_kill(toy):
    stryker = Stryker(toy)
    assert stryker.unavailable() is None
    assert stryker.kills(["src/adult.js"], "TOY.H1") == (6, 4)  # REDLINE_SPEC reaches its Jest workers
    assert stryker.kills(["src/adult.js"], "TOY.H2") == (6, 6)
    assert not (toy / "reports").exists()


DELTA = """## ADDED Requirements

### Requirement: Adults

#### Scenario TOY.H1 [hold]: a grown-up is an adult
- THEN adult(30) is true

#### Scenario TOY.H2 [hold]: an adult starts at 18
- THEN adult(18) is true AND adult(17) is false

#### Scenario TOY.H3 [hold]: arithmetic still works
- THEN 1 + 1 is 2

### Premises
- P1: adult compares the age with 18 — `src/adult.js:1-3` (`adult`)
"""
H3 = 'spec("TOY.H3").test("asserts nothing about adult", () => {\n  expect(1 + 1).toBe(2);\n});\n'


@pytest.fixture
def toy_repo(toy, tmp_path):
    """A git repository holding the toy and a change whose premise cites src/adult.js; node_modules is linked."""
    repo = tmp_path / "toy"
    shutil.copytree(toy, repo, ignore=shutil.ignore_patterns("node_modules"))
    link = repo / "node_modules"
    try:
        link.symlink_to(toy / "node_modules", target_is_directory=True)
    except OSError:  # Windows without the right to make symlinks: a junction
        import _winapi
        _winapi.CreateJunction(str(toy / "node_modules"), str(link))
    with open(repo / "src" / "adult.test.js", "a", encoding="utf-8") as tests:
        tests.write("\n" + H3)
    (repo / ".gitignore").write_text("node_modules\nreports/\n.stryker-tmp/\n", encoding="utf-8")  # the toy's ignores redline/
    (repo / "redline" / "changes" / "toy" / "specs" / "adult").mkdir(parents=True)
    (repo / "redline" / "changes" / "toy" / "specs" / "adult" / "delta.md").write_text(DELTA, encoding="utf-8")
    for command in (["init", "-q", "-b", "main"], ["add", "-A"],
                    ["-c", "user.name=Toy", "-c", "user.email=toy@example.com", "commit", "-q", "-m", "toy"]):
        subprocess.run(["git", *command], cwd=repo, check=True, capture_output=True)
    yield repo
    try:
        link.unlink()
    except OSError:
        os.rmdir(link)  # a junction; removing it leaves the toy's node_modules alone


def test_check_break_runs_jest_and_stryker_end_to_end(toy_repo):
    report = check_break(toy_repo, "toy")
    assert report.skipped == {}
    assert report.results == {"TOY.H1": None, "TOY.H2": None,
                              "TOY.H3": "its tests survive every mutant (0 of 6 killed, in src/adult.js)"}


# O-REPORT1: PR #97 merged; per-case push execution is unpublished, so evidence stays HELD.
# Local/optional-job execution below is validation, never credited red/green.
@pytest.mark.parametrize("body,new,hooks,qualification,outcome", [
    ("throw new Error('body')", True, "", "red", "expected-failure"),
    ("return Promise.reject(new TypeError('absent'))", True, "", "red", "expected-failure"),
    ("missing.method()", True, "", "red", "expected-failure"),
    ("expect(1).toBe(1)", True, "", "nonqualifying", "unexpected-pass"),
    ("expect(1).toBe(1)", False, "", "green", "pass"),
    ("throw new Error('body')", True, "beforeEach(() => {throw Error('hook')});", "nonqualifying", "error"),
    ("throw new Error('body')", True, "afterEach(() => {throw Error('hook')});", "nonqualifying", "error"),
    ("throw new Error('body')", False, "", "nonqualifying", "error"),
])
@pytest.mark.spec("REPORT.JS.S1")
def test_real_jest_report_provenance(toy_repo, body, new, hooks, qualification, outcome):
    from redline.runner import JEST, run
    source = ('const {spec} = require("../redline/runners/jest");\n' + hooks +
        f'\nspec("TOY.S1", {{new: {str(new).lower()}}}).test("body", () => {{{body}}});\n' +
        'test.failing("unrelated", () => {throw Error("unrelated")});\n')
    (toy_repo / "src/adult.test.js").write_text(source, encoding="utf-8")
    done = run(toy_repo, replace(JEST, command=lambda sid: (JEST.command(sid)[0] + ["--runInBand"], JEST.command(sid)[1])))
    assert hasattr(done, "outcomes"), "Jest must return execution detail, not its passed count"
    assert done.returncode == (0 if qualification in ("red", "green") else 1), done.stderr
    report = done.outcomes
    assert report["scenarios"]["TOY.S1"]["qualification"] == qualification
    [record] = [r for r in report["observed"] if "TOY.S1" in r["links"]]
    assert record["outcome"] == outcome and record["new"] == new
    assert record["strict_new"] == (qualification == "red")


@pytest.mark.parametrize("fault,diagnostic", [("join", None), ("parameters", None), ("skip", "skip"), ("pending", "skip"),
    ("omit", "missing"), ("duplicate", "duplicate"), ("ambiguous", "ambiguous"),
    ("refused", "collection-error"), ("nested", None)])
@pytest.mark.spec("REPORT.JS.S2")
def test_real_jest_inventory_joins_and_isolation(toy_repo, fault, diagnostic):
    from redline.runner import JEST, run
    title = r"escaped \' É"
    source = ('const {spec} = require("../redline/runners/jest");\n' +
        f"describe('parent', () => {{spec('TOY.S1').test('{title}', () => {{expect(1).toBe(1)}});}});\n")
    if fault == "skip": source = source.replace("describe(", "describe.skip(")
    if fault == "pending": source = source.replace("const {spec}", 'const original = global.test; global.test = Object.assign((...a) => original.skip(...a), original);\nconst {spec}')
    if fault == "omit": (toy_repo / "jest.config.js").write_text("module.exports={testPathIgnorePatterns:['adult.test.js']};")
    if fault == "refused": source += source.splitlines()[-1] + "\n"
    if fault == "duplicate": source += source.splitlines()[-1].replace("escaped", r"esc\u0061ped") + "\n"
    if fault in ("parameters", "ambiguous"):
        source += f"spec('TOY.S1').test.each({[1, 2] if fault == 'parameters' else [1, 1]})('parameter %s', x => expect(x).toBeGreaterThan(0));\n"
    if fault == "nested":
        source = source.replace("expect(1).toBe(1)", 'require("fs").writeFileSync("src/inner.test.js", "test(\'inner\',()=>{});"); require("child_process").execFileSync(process.execPath, [require.resolve("jest/bin/jest"), "--runInBand", "--runTestsByPath", "src/inner.test.js"], {env: process.env})')
    (toy_repo / "src/adult.test.js").write_text(source, encoding="utf-8")
    done = run(toy_repo, replace(JEST, command=lambda sid: (JEST.command(sid)[0] + ["--runInBand"], JEST.command(sid)[1])))
    assert hasattr(done, "outcomes"), "Jest inventory/report is absent"
    report = done.outcomes
    assert report["complete"] == (diagnostic is None)
    assert diagnostic is None or diagnostic in {d["code"] for d in report["diagnostics"]}
    if diagnostic is None:
        records = [r for r in report["observed"] if "TOY.S1" in r["links"]]
        assert len(records) == len({r["identity"] for r in records}) == (3 if fault == "parameters" else 1)
        record = next(r for r in records if "parent" in r["identity"])
        assert "parent" in record["identity"] and "É" in record["identity"] and record["source"]
        assert "inner" not in str(report["observed"])


@pytest.mark.parametrize("fault", ["none", "xpass", "omit"])
@pytest.mark.spec("REPORT.ALL.S1")
def test_real_cross_runner_qualification(toy_repo, fault):
    from redline.reports import aggregate
    from redline.runner import JEST, PYTEST, run
    (toy_repo / "test_cross.py").write_text('import pytest\n@pytest.mark.spec("TOY.S1")\ndef test_cross(): pass\n')
    (toy_repo / "src/adult.test.js").write_text('const {spec}=require("../redline/runners/jest");\n' +
        f'spec("TOY.S1", {{new: {str(fault == "xpass").lower()}}}).test("cross", () => {{}});\n')
    (toy_repo / "src/kept.test.js").write_text('const {spec}=require("../redline/runners/jest"); spec("TOY.S1").test("kept", () => {});\n')
    if fault == "omit":
        (toy_repo / "jest.config.js").write_text("module.exports={testPathIgnorePatterns:['adult.test.js']};")
    py = run(toy_repo, PYTEST)
    js = run(toy_repo, replace(JEST, command=lambda sid: (JEST.command(sid)[0] + ["--runInBand"], {})))
    assert py.returncode == 0 and js.returncode == (1 if fault == "xpass" else 0)
    report = aggregate([py.outcomes, js.outcomes], commit="b" * 40)
    assert report["scenarios"]["TOY.S1"]["qualification"] == ("green" if fault == "none" else "nonqualifying")
    assert fault != "omit" or "missing" in {d["code"] for d in report["diagnostics"]}
