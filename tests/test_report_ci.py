"""Report transport and frozen regressions for the existing evidence boundary."""
import base64
import os
import subprocess
from importlib.resources import files
from pathlib import Path

import pytest
import yaml

from redline.ci import ci_push
from redline.close import check_close
from redline.ledger import rebuild
from redline.runner import PYTHON
from test_ci import RUN, bash, remote  # noqa: F401
from test_ledger import land
from test_start import change  # noqa: F401


@pytest.mark.parametrize("failed,route,defect", [(f, r, d) for f in (False, True)
    for r in ("file", "direct") for d in ("complete", "missing", "malformed", "incomplete", "skip")])
@pytest.mark.spec("REPORT.CI.S1")
def test_current_report_survives_both_note_routes(change, remote, actions, monkeypatch, tmp_path, failed, route, defect):
    from types import SimpleNamespace
    import redline.ci as producer
    sha = change.commit("report suite", {"test_ok.py": "def test_ok(): pass\n"})
    report = {"version": 1, "commit": sha, "complete": defect == "complete", "expected": [], "observed": [],
        "scenarios": {}, "diagnostics": [] if defect == "complete" else [{"code": "abort" if defect == "incomplete" else defect, "runner": "pytest", "reason": "toy"}]}
    from redline.reports import row
    entry = row("test_ok.py::test_ok", [("TOY.S1", False)])
    report["expected"] = [entry]
    report["observed"] = [dict(entry, outcome="skip" if defect == "skip" else "pass", strict_new=False,
        phases={"setup": "pass", "call": "skip" if defect == "skip" else "pass", "teardown": "pass"})]
    payload = None if defect == "missing" else "invalid" if defect == "malformed" else report
    monkeypatch.setattr(producer, "run", lambda *a, **k: SimpleNamespace(returncode=int(failed), stdout="", stderr="", outcomes=payload))
    target = tmp_path / "note"
    target.write_text("outcomes: {version: 999, commit: stale}\n", encoding="utf-8")
    errors = ci_push(change.path, RUN, to=target if route == "file" else None, python=PYTHON[-1])
    data = yaml.safe_load(target.read_text(encoding="utf-8") if route == "file" else remote.pushed[-1])
    assert bool(errors) == failed and data["result"] == ("fail" if failed else "pass") and data["run"] == RUN
    actual = data["outcomes"]
    assert actual["version"] == 1 and actual["commit"] == sha and actual["complete"] == (defect == "complete")
    assert defect == "complete" or ("abort" if defect == "incomplete" else defect) in {d["code"] for d in actual["diagnostics"]}
    if route == "file": change.git("notes", "--ref=redline-ci", "add", "-f", "-F", str(target), sha)
    actions.push_run(sha, data["result"], url=RUN)
    from redline.ledger import ci_result
    from redline.pr import GitHub
    assert ci_result(change.path, sha, GitHub(change.path)) == data["result"]


@pytest.mark.parametrize("state", ["pass", "skip", "fail"])
@pytest.mark.spec("REPORT.CI.S1")
def test_real_report_and_stripped_report_at_isolated_handoff(change, monkeypatch, tmp_path, state):
    from redline.reports import aggregate
    monkeypatch.setattr("redline.ci.record", lambda *a: {})
    body = "pytest.skip('partial')" if state == "skip" else f"assert {state == 'pass'}"
    sha = change.commit("linked suite", {"test_report.py": 'import pytest\n@pytest.mark.spec("TOY.S1")\ndef test_case(): ' + body + '\n'})
    target = tmp_path / "note"
    assert bool(ci_push(change.path, RUN, to=target, python=PYTHON[-1])) == (state == "fail")
    expected = target.read_bytes()
    detail = yaml.safe_load(expected)["outcomes"]
    assert detail["commit"] == sha and detail["complete"] == (state != "skip")
    assert detail["observed"][0]["outcome"] == {"pass": "pass", "skip": "skip", "fail": "error"}[state]
    assert detail["scenarios"]["TOY.S1"]["qualification"] == ("green" if state == "pass" else "nonqualifying")
    sources = [Path(__file__).parents[1] / ".github/workflows/redline.yml", files("redline").joinpath("helpers/redline.yml")]
    for source in sources:
        workflow = yaml.safe_load(source.read_text(encoding="utf-8"))
        writer = next(s["run"] for s in workflow["jobs"]["note"]["steps"] if "run" in s)
        script = tmp_path / "writer.sh"
        script.write_text('git() { if [ "$1" = fetch ] || [ "$1" = push ]; then return 0; fi; command git "$@"; }\n' + writer, encoding="utf-8", newline="\n")
        for stripped in (False, True):
            data = yaml.safe_load(expected)
            if stripped: data.pop("outcomes")
            sent = yaml.safe_dump(data, allow_unicode=True, sort_keys=False).encode() if stripped else expected
            env = {**os.environ, "NOTE": base64.b64encode(sent).decode(), "RUNNER_TEMP": str(tmp_path), "GITHUB_SHA": sha}
            done = subprocess.run([bash(), str(script)], cwd=change.path, env=env, capture_output=True)
            assert done.returncode == 0, done.stderr
            shown = subprocess.run(["git", "notes", "--ref=redline-ci", "show", sha], cwd=change.path, capture_output=True, check=True).stdout
            assert shown == sent
            received = yaml.safe_load(shown)
            if stripped:
                # Transport success alone is no execution proof. No ledger enforcement is added here.
                unavailable = aggregate([received.get("outcomes")], commit=sha)
                assert not unavailable["complete"] and unavailable["diagnostics"]
                assert not unavailable["scenarios"]
            else: assert received["outcomes"] == detail


@pytest.mark.spec("REPORT.CI.S1")
@pytest.mark.parametrize("failed", [False, True])
def test_push_carries_all_runner_reports_even_after_first_runner_fails(change, monkeypatch, tmp_path, failed):
    from types import SimpleNamespace
    from redline.reports import aggregate, finish, row
    from redline.runner import PYTEST, JEST
    change.commit("runners")
    monkeypatch.setattr("redline.ci.uses", lambda *a: True)
    monkeypatch.setattr("redline.ci.shutil.which", lambda _: "npx")
    monkeypatch.setattr("redline.ci.record", lambda *a: {})
    (change.path / "node_modules/jest").mkdir(parents=True)
    parts, calls = [], []
    for runner in (PYTEST, JEST):
        entry = dict(row(runner.name + "::case", [("TOY.S1", False)]), runner=runner.name)
        parts.append(finish([], {"expected": [entry], "observed": [dict(entry, outcome="pass", strict_new=False,
            phases={"setup": "pass", "call": "pass", "teardown": "pass"})], "diagnostics": []}))
    def run(repo, runner):
        calls.append(runner.name)
        return SimpleNamespace(returncode=int(failed and runner is PYTEST), stdout="", stderr="", outcomes=parts[len(calls) - 1])
    monkeypatch.setattr("redline.ci.run", run)
    target = tmp_path / "note"
    assert bool(ci_push(change.path, RUN, to=target)) == failed
    data = yaml.safe_load(target.read_text(encoding="utf-8"))
    assert calls == ["pytest", "jest"] and data["result"] == ("fail" if failed else "pass")
    assert data["outcomes"] == aggregate(parts, commit=change.git("rev-parse", "HEAD"))


@pytest.mark.spec("REPORT.CI.S1")
def test_lost_suite_report_is_incomplete_even_when_suite_passes(change, monkeypatch, tmp_path):
    change.commit("suite run")
    monkeypatch.setattr("redline.ci.suite", lambda _: [])
    monkeypatch.setattr("redline.ci.record", lambda *a: {})
    target = tmp_path / "note"
    assert not ci_push(change.path, RUN, to=target)
    data = yaml.safe_load(target.read_text(encoding="utf-8"))
    assert data["result"] == "pass" and not data["outcomes"]["complete"]
    assert "missing" in {d["code"] for d in data["outcomes"]["diagnostics"]}


@pytest.mark.spec("REPORT.CI.H1")
def test_outcomes_never_upgrade_existing_evidence_or_leak_python(change, actions, monkeypatch):
    from redline.ledger import ci_result
    from redline.pr import GitHub
    from test_close import red_and_green
    red, green = red_and_green(change)
    before = list(PYTHON)
    for result, confirmation in [("pass", "good"), ("fail", "good"), ("pass", "missing"), ("pass", "wrong")]:
        run = actions.push_run(green, result)
        if confirmation == "wrong": actions.register(int(run.rsplit('/', 1)[1]), red)
        for detail in (None, {}, "malformed", {"version": 999}, {"version": 1, "complete": False}, {"version": 1, "complete": True}):
            note = {"result": result, "run": run if confirmation != "missing" else "unavailable", "break": {"X.H1": "pass"}, "claims": {"kept": True}}
            if detail is not None: note["outcomes"] = detail
            change.git("notes", "--ref=redline-ci", "add", "-f", "-m", yaml.safe_dump(note), green)
            current = (rebuild(change.path, "add-greet"), check_close(change.path, "add-greet"))
            if detail is None: baseline = current
            assert current == baseline
            assert ci_result(change.path, green, GitHub(change.path)) == (result if confirmation == "good" else "unconfirmed")
    from test_window import step
    from test_close import HOLD, HELD
    change.commit("declare hold", {"redline/changes/add-greet/specs/greet/delta.md": HOLD})
    land(change, "old-hold", {"tests/test_hold.py": HELD})
    step(change, "add-greet/S")
    for stage in ("S", "R", "G1", "C", "later"):
        if stage != "S":
            if stage == "later": change.commit("after close")
            else: step(change, "add-greet/" + stage)
        sha = change.git("rev-parse", "HEAD")
        run = actions.push_run(sha, "pass", {"GREET.H1": "pass"})
        for detail in (None, "malformed", {"version": 1, "complete": False}):
            note = {"result": "pass", "run": run, "break": {"GREET.H1": "pass"}}
            if detail is not None: note["outcomes"] = detail
            change.git("notes", "--ref=redline-ci", "add", "-f", "-m", yaml.safe_dump(note), sha)
            current = (rebuild(change.path, "add-greet"), check_close(change.path, "add-greet"))
            if detail is None: baseline = current
            assert current == baseline
            assert current[0]["scenarios"]["GREET.S1"]["red"] is None
            assert (current[0]["scenarios"]["GREET.H1"]["break"] is None) == (stage == "S")
    for fail in (False, True):
        def suite(_):
            assert PYTHON[-1] == "project-python"
            if fail: raise RuntimeError("suite error")
            return []
        monkeypatch.setattr("redline.ci.suite", suite)
        monkeypatch.setattr("redline.ci.record", lambda *a: {})
        if fail:
            with pytest.raises(RuntimeError, match="suite error"): ci_push(change.path, RUN, python="project-python")
        else: assert not ci_push(change.path, RUN, to=change.path / "note", python="project-python")
        assert PYTHON == before
    from redline.breaks import BreakReport
    monkeypatch.setattr("redline.ci.suite", lambda _: [])
    monkeypatch.setattr("redline.ci.pr_step", lambda *a: "add-greet/R")
    monkeypatch.setattr("redline.ci.check_break", lambda *a: BreakReport(results={"GREET.H1": "broken"}))
    note = change.path / "failure-note"
    assert ci_push(change.path, RUN, to=note)
    data = yaml.safe_load(note.read_text(encoding="utf-8"))
    assert data["result"] == "pass" and data["break"] == {"GREET.H1": "fail"}
    monkeypatch.setattr("redline.ci.record", lambda *a: (_ for _ in ()).throw(RuntimeError("claims unavailable")))
    assert any("claims:" in error for error in ci_push(change.path, RUN, to=note))
    assert yaml.safe_load(note.read_text(encoding="utf-8"))["result"] == "pass"


@pytest.mark.spec("REPORT.CI.H2")
def test_file_direct_and_isolated_writer_keep_identical_bytes(change, remote, monkeypatch, tmp_path):
    shell = bash()
    assert shell, "Git bash is needed to exercise the isolated writer"
    from redline.breaks import BreakReport
    monkeypatch.setattr("redline.ci.pr_step", lambda *a: "add-greet/R")
    monkeypatch.setattr("redline.ci.check_break", lambda *a: BreakReport(results={"GREET.H1": None}))
    monkeypatch.setattr("redline.ci.record", lambda *a: {"kept": "É"})
    script = next(s["run"] for s in yaml.safe_load(files("redline").joinpath("helpers/redline.yml").read_text(encoding="utf-8"))["jobs"]["note"]["steps"] if "run" in s)
    for failed in (False, True):
        monkeypatch.setattr("redline.ci.suite", lambda _: ["suite failed"] if failed else [])
        note = tmp_path / "note"
        pushed = len(remote.pushed)
        read = ["git", "notes", "--ref=redline-ci", "show", "HEAD"]
        previous = subprocess.run(read, cwd=change.path, capture_output=True).stdout
        assert bool(ci_push(change.path, RUN, to=note)) == failed
        assert len(remote.pushed) == pushed
        assert subprocess.run(read, cwd=change.path, capture_output=True).stdout == previous
        expected = note.read_bytes()
        data = yaml.safe_load(expected)
        assert data["result"] == ("fail" if failed else "pass") and data["run"] == RUN
        assert data["break"] == {"GREET.H1": "pass"} and data["claims"] == {"kept": "É"}
        assert bool(ci_push(change.path, RUN)) == failed
        assert (remote.pushed[-1] + "\n").encode() == expected
        script_file = tmp_path / "writer.sh"
        script_file.write_text('git() { if [ "$1" = fetch ] || [ "$1" = push ]; then return 0; fi; command git "$@"; }\n' + script, encoding="utf-8", newline="\n")
        env = {**os.environ, "NOTE": base64.b64encode(expected).decode(), "RUNNER_TEMP": str(tmp_path), "GITHUB_SHA": change.git("rev-parse", "HEAD")}
        done = subprocess.run([shell, str(script_file)], cwd=change.path, env=env, capture_output=True)
        assert done.returncode == 0, done.stderr
        assert (tmp_path / "note").read_bytes() == expected
        shown = subprocess.run(["git", "notes", "--ref=redline-ci", "show", "HEAD"], cwd=change.path, capture_output=True, check=True)
        assert shown.stdout == expected
