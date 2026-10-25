"""Report transport and frozen regressions for the existing evidence boundary."""
import base64
import os
import subprocess
from importlib.resources import files

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
