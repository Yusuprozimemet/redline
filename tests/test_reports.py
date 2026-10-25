"""Report contract: real pytest execution, plus aggregate protocol negatives."""
import copy
import json
from dataclasses import replace

import pytest

from redline.runner import PYTEST, run


def execute(pytester, source, *args, files=None):
    pytester.makeini("[pytest]\ndisable_test_id_escaping_and_forfeit_all_rights_to_community_support = True\n")
    pytester.makepyfile(test_report="import pytest\n" + source)
    if "TOY.S2" in source:
        delta = pytester.path / "redline/changes/toy/specs/report/delta.md"
        delta.parent.mkdir(parents=True, exist_ok=True)
        delta.write_text('#### Scenario TOY.S1 [new]: first\n#### Scenario TOY.S2 [hold]: second\n', encoding="utf-8")
    for name, text in (files or {}).items():
        (pytester.path / name).write_text(text, encoding="utf-8")
    runner = replace(PYTEST, command=lambda sid: (PYTEST.command(sid)[0] + list(args), PYTEST.command(sid)[1]))
    done = run(pytester.path, runner)
    assert done.returncode in (0, 1, 2), done.stderr
    assert hasattr(done, "outcomes"), "runner must return this invocation's execution report"
    return done.outcomes


def codes(report):
    return {d["code"] for d in report["diagnostics"]}


@pytest.mark.parametrize("body", ["assert False", "raise ImportError()", "raise AttributeError()",
    "raise NameError()", "raise TypeError()", "pytest.fail('body')", "with pytest.raises(ValueError): pass"])
@pytest.mark.spec("REPORT.PY.S1", new=True)
def test_strict_body_failure_is_red(pytester, body):
    report = execute(pytester, '@pytest.mark.spec("TOY.S1", new=True)\ndef test_it():\n    ' + body)
    assert report["complete"] and report["scenarios"]["TOY.S1"]["qualification"] == "red"
    [record] = report["observed"]
    assert record["outcome"] == "expected-failure" and record["strict_new"]
    assert record["phases"]["setup"] == record["phases"]["teardown"] == "pass"


@pytest.mark.parametrize("marks,body,outcome,qualification", [
    ('', 'pass', 'pass', 'green'), (', new=True', 'pass', 'unexpected-pass', 'nonqualifying'),
    ('', 'assert False', 'error', 'nonqualifying'),
    ('', "pytest.skip('skip')", 'skip', 'nonqualifying'),
    ('', "pytest.xfail('unrelated')", 'expected-failure', 'nonqualifying'),
    (', new=True', 'assert False', 'expected-failure', 'nonqualifying'),
])
@pytest.mark.spec("REPORT.PY.S1", new=True)
def test_pytest_terminal_outcomes_and_overridden_xfail(pytester, marks, body, outcome, qualification):
    override = '@pytest.mark.xfail(reason="unrelated", strict=False)\n' if marks and body == 'assert False' else ''
    report = execute(pytester, override + f'@pytest.mark.spec("TOY.S1"{marks})\ndef test_it():\n    {body}')
    assert report["observed"][0]["outcome"] == outcome
    assert report["scenarios"]["TOY.S1"]["qualification"] == qualification


@pytest.mark.parametrize("phase,action", [(p, a) for p in ("setup", "teardown")
    for a in ("raise ValueError('hook')", "pytest.xfail('hook')")])
@pytest.mark.spec("REPORT.PY.S1", new=True)
def test_hook_failure_never_qualifies_as_body_red(pytester, phase, action):
    hook = action + '\n    yield' if phase == 'setup' else 'yield\n    ' + action
    report = execute(pytester, '@pytest.fixture(autouse=True)\ndef hook():\n    ' + hook +
        '\n@pytest.mark.spec("TOY.S1", new=True)\ndef test_it():\n    assert False')
    assert report["scenarios"]["TOY.S1"]["qualification"] == "nonqualifying"
    assert report["observed"][0]["phases"][phase] != "pass"


PARAMS = '@pytest.mark.spec("TOY.S1")\n@pytest.mark.spec("TOY.S2")\n@pytest.mark.parametrize("x", [1, 2], ids=["é", "Two"])\ndef test_it(x):\n    assert x > 0\n'


@pytest.mark.parametrize("selection,files,diagnostic", [
    ([], {}, None), (["-k", "Two"], {}, "deselected"),
    ([], {"hidden.py": 'import pytest\n@pytest.mark.spec("TOY.S1")\ndef test_hidden(): pass'}, "missing"),
    ([], {"test_bad.py": "raise ImportError('collection')"}, "collection-error"),
    ([], {"conftest.py": "def pytest_collection_modifyitems(items): items.pop()"}, "missing"),
    ([], {"conftest.py": "import pytest\ndef pytest_collection_modifyitems(items):\n    for item in items: item.add_marker(pytest.mark.skip(reason='skip'))\n"}, "skip"),
])
@pytest.mark.spec("REPORT.PY.S2", new=True)
def test_expected_instances_survive_selection_and_collection(pytester, selection, files, diagnostic):
    report = execute(pytester, PARAMS, *selection, files=files)
    expected = json.dumps(report["expected"], ensure_ascii=False)
    assert '"new"' in expected and '"hold"' in expected
    assert "test_report.py::test_it[é]" in expected and "test_report.py::test_it[Two]" in expected
    assert all(r["runner"] == "pytest" for r in report["observed"])
    assert not diagnostic or diagnostic in codes(report)
    assert report["complete"] == (diagnostic is None)
    if diagnostic is None:
        assert all(report["scenarios"][sid]["qualification"] == "green" for sid in ("TOY.S1", "TOY.S2"))


@pytest.mark.spec("REPORT.PY.S2", new=True)
def test_filtered_and_later_runs_cannot_replace_a_previous_full_report(pytester):
    full = execute(pytester, PARAMS)
    saved = copy.deepcopy(full)
    selected = run(pytester.path, PYTEST, "TOY.S1")
    assert selected.outcomes is not full and full == saved
    later = execute(pytester, PARAMS.replace("TOY.S1", "LATER.S1"))
    assert "TOY.S1" not in later["scenarios"] and full == saved


@pytest.mark.spec("REPORT.PY.S2", new=True)
def test_unicode_class_paths_and_nested_invocations_are_isolated(pytester):
    nested = 'import pytest\n@pytest.mark.spec("INNER.S1")\ndef test_inner(): pass\n'
    source = ('import os, subprocess, sys\nclass TestÉ:\n'
        '    @pytest.mark.spec("TOY.S1")\n    def test_outer(self):\n'
        f'        open("inner.py", "w", encoding="utf-8").write({nested!r})\n'
        '        subprocess.run([sys.executable, "-m", "pytest", "inner.py"], check=True)\n'
        '        pytest.main(["inner.py"])\n')
    report = execute(pytester, source, files={"test_É.py": 'import pytest\n@pytest.mark.spec("TOY.S1")\ndef test_path(): pass\n'})
    assert len(report["observed"]) == 2 and report["complete"]
    assert "TestÉ::test_outer" in json.dumps(report["observed"], ensure_ascii=False)
    assert "test_É.py::test_path" in json.dumps(report["observed"], ensure_ascii=False)
    assert "INNER.S1" not in report["scenarios"]


@pytest.mark.parametrize("fault,diagnostic", [("", None), ("exit", "missing-worker"),
    ("inventory", "inventory-conflict"), ("parameter", "missing"), ("duplicate", "duplicate")])
@pytest.mark.spec("REPORT.PY.S3", new=True)
def test_real_xdist_inventories_and_execution(pytester, fault, diagnostic):
    hooks = 'import os\n'
    if fault == "inventory":
        hooks += 'def pytest_collection_modifyitems(items):\n    if os.getenv("PYTEST_XDIST_WORKER") == "gw1": items.pop()\n'
    if fault == "parameter":
        hooks += 'def pytest_collection_modifyitems(items): items.pop()\n'
    if fault == "duplicate":
        hooks += 'def pytest_collection_modifyitems(items): items.append(items[0])\n'
    source = PARAMS.replace('assert x > 0', 'import os; os._exit(3)' if fault == 'exit' else 'assert x > 0')
    report = execute(pytester, source, "-n", "2", "--max-worker-restart=0", files={"conftest.py": hooks})
    assert report["complete"] == (not fault)
    assert diagnostic in codes(report) if diagnostic else len(report["observed"]) == 2


@pytest.mark.parametrize("fault", ["none", "missing", "extra", "duplicate", "conflicting", "malformed",
    "unsupported", "abort", "empty", "mixed-markers", "missing-phase"])
@pytest.mark.spec("REPORT.ALL.S1", new=True)
def test_cross_runner_aggregation_preserves_every_instance(pytester, fault):
    report = execute(pytester, PARAMS)
    from redline.reports import aggregate
    js = copy.deepcopy(report)
    for section in ("expected", "observed"):
        for row in js[section]:
            row["runner"] = "jest"
            row["identity"] = row["identity"].replace("test_report.py", "nested/É.test.js")
    if fault == "missing": js["observed"].pop()
    if fault == "extra": js["observed"].append(dict(js["observed"][0], identity="extra"))
    if fault == "duplicate": js["observed"].append(copy.deepcopy(js["observed"][0]))
    if fault == "conflicting": js["observed"].append(dict(js["observed"][0], outcome="error"))
    if fault == "malformed": js["observed"] = "invalid"
    if fault == "unsupported": js["version"] = 999
    if fault == "abort": js["complete"] = False; js["diagnostics"] = [{"code": "abort", "runner": "jest", "reason": "stopped"}]
    if fault == "empty": report["expected"] = report["observed"] = []; js = copy.deepcopy(report)
    if fault == "mixed-markers": js["expected"][0]["new"] = True
    if fault == "missing-phase": js["observed"][0]["phases"].pop("teardown")
    merged = aggregate([report, js], commit="a" * 40)
    assert merged == aggregate([js, report], commit="a" * 40)
    assert merged["version"] == 1 and merged["commit"] == "a" * 40
    if fault == "empty":
        assert all(s["qualification"] == "nonqualifying" for s in merged["scenarios"].values())
    else:
        assert merged["scenarios"]["TOY.S1"]["qualification"] == ("green" if fault == "none" else "nonqualifying")
    assert fault == "none" or fault in codes(merged)
    assert fault not in ("duplicate", "conflicting") or len(merged["observed"]) == 5
