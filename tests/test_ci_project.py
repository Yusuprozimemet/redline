"""O-CI11: one adopter setup action, and project tests outside the pinned gate's packages."""
import pytest
import yaml

from redline.cli import main
from redline.runner import PYTHON
from test_ci import RUN, ci, remote  # noqa: F401
from test_ci_suite import logging_python, r_step
from test_install_workflow import installed, written, install, WRITTEN  # noqa: F401
from test_start import change  # noqa: F401

ACTION = ".github/actions/redline-project/action.yml"
CALL = "./.github/actions/redline-project"


def test_generated_workflow_shares_project_setup_and_keeps_gate_packages_apart(repo, capsys, installed):
    jobs = written(repo, capsys)["jobs"]
    action = yaml.safe_load((repo.path / ACTION).read_text(encoding="utf-8"))
    assert action["runs"]["using"] == "composite"
    assert action["runs"]["steps"] and all(s.get("shell") == "bash" for s in action["runs"]["steps"])
    project_run = action["runs"]["steps"][0]["run"]
    assert 'cd "$RUNNER_TEMP/redline"' in project_run
    assert "python -m pip install --require-hashes" in project_run
    assert "--no-index ." in project_run
    for job in ("suite", "redline"):
        steps = jobs[job]["steps"]
        [setup] = [s for s in steps if s.get("uses") == CALL]
        assert setup.get("if") == ("github.event_name == 'push'" if job == "redline" else None)
        [gate] = [s for s in steps if "git clone" in s.get("run", "")]
        lines = gate["run"].splitlines()
        assert 'python -m venv "$RUNNER_TEMP/gate"' in lines
        pips = [line.strip() for line in lines if "-m pip" in line]
        assert len(pips) == 3 and all(line.startswith('"$RUNNER_TEMP/gate/bin/python" -m pip') for line in pips)
        assert steps.index(gate) < steps.index(setup)
        for step in steps:
            run = step.get("run", "")
            if "ci " in run:
                assert run.startswith('"$RUNNER_TEMP/gate/bin/redline" ci ')
                assert ('--python "$(command -v python)"' in run) == ("ci pr" not in run)


def test_existing_project_action_is_preserved_and_existing_workflow_writes_nothing(repo, capsys, installed):
    mine = b"# custom action\r\nname: mine\r\n"
    (repo.path / ACTION).parent.mkdir(parents=True)
    (repo.path / ACTION).write_bytes(mine)
    written(repo, capsys)
    assert (repo.path / ACTION).read_bytes() == mine
    (repo.path / ACTION).unlink()
    assert install(repo, capsys)[0] == 2
    assert not (repo.path / ACTION).exists() and (repo.path / WRITTEN).exists()


def test_invalid_metadata_writes_no_project_action(repo, capsys, installed):
    installed.direct_url = None
    assert install(repo, capsys)[0] == 2
    assert not (repo.path / ".github").exists()


def test_push_python_runs_suite_and_r_break_then_restores_selection(change, capsys, tmp_path, remote):
    r_step(change, capsys, {})
    note, log = tmp_path / "note", tmp_path / "python.log"
    before = list(PYTHON)
    code, out = ci(change, capsys, "push", "--run-url", RUN, "--note", str(note),
                   "--python", logging_python(tmp_path, log))
    assert code == 1 and "pytest exit 3" in out
    calls = log.read_text(encoding="utf-8").splitlines()
    assert len(calls) == 2 and sum("--redline-spec=GREET.H1" in line for line in calls) == 1
    result = yaml.safe_load(note.read_text(encoding="utf-8"))
    assert result["result"] == "fail" and result["run"] == RUN and "break" in result
    assert PYTHON == before and remote.pushed == []


def test_push_python_restores_selection_on_error(repo, monkeypatch):
    from redline.ci import ci_push

    before = list(PYTHON)
    def fail(_):
        assert PYTHON[-1] == "project-python"
        raise RuntimeError("suite failed unexpectedly")
    monkeypatch.setattr("redline.ci.suite", fail)
    with pytest.raises(RuntimeError, match="suite failed unexpectedly"):
        ci_push(repo.path, RUN, python="project-python")
    assert PYTHON == before
