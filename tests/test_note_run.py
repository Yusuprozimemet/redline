"""A CI note is checked against its run on GitHub (docs/design.md, section 4): the change note-run.

Each note names a run through FakeActions (conftest.py), which answers only the runs a test registers.
A forged note, a crafted event, branch, workflow or job, a missing field, any other note's run, a
404 or another error each reads differently from a note CI wrote on its own push run.
"""

import json
import re
import time
from pathlib import Path

import pytest
import yaml

from conftest import OWN
from redline.pr import GitHub
from test_close import close, red_and_green
from test_ledger import LEDGER, land, ledger, rebuilt
from test_start import CHANGE, DELTA, change  # noqa: F401 (change is a fixture)

RED = 'import pytest\n\n' + "".join(
    f'@pytest.mark.spec("GREET.{sid}", new=True)\ndef test_{sid}():\n    assert False\n\n' for sid in ("S1", "S2"))
GREEN = RED.replace(", new=True", "").replace("assert False", "assert True")
WORKFLOW = Path(__file__).resolve().parent.parent / ".github/workflows/redline.yml"
FAILURE = {"redline": "failure"}


def noted(repo, commit: str, result: str, run: str | None = None, breaks: dict | None = None) -> None:
    """A note on `commit`, as CI writes it or anyone with the write role could."""
    lines = [f"result: {result}"] + [f"run: {run}"] * bool(run)
    lines += ["break:", *(f"  {sid}: {outcome}" for sid, outcome in breaks.items())] if breaks else []
    repo.git("notes", "--ref=redline-ci", "add", "-f", "-m", "\n".join(lines) + "\n", commit)


def held(repo, *holds: str) -> str:
    """The change with `hold` scenarios, and its R merge, which lands their tests beside the reds."""
    repo.commit("holds", {f"{CHANGE}/specs/greet/delta.md": DELTA + "".join(
        f"\n#### Scenario {sid} [hold]: {sid} stays\n- THEN it stays\n" for sid in holds)})
    tests = "import pytest\n\n" + "".join(
        f'@pytest.mark.spec("{sid}")\ndef test_{sid[-2:]}():\n    assert True\n\n' for sid in holds)
    return land(repo, "red", {"tests/test_greet.py": RED, "tests/test_hold.py": tests})[1]


def read(repo, capsys) -> tuple[str, str]:
    """The R merge's result, as GREET.S1's red, and GREET.H1's break."""
    scenarios = rebuilt(repo, capsys)["scenarios"]
    return scenarios["GREET.S1"]["red"]["result"], scenarios["GREET.H1"]["break"]["result"]


def test_fake_actions_answers_only_the_runs_a_test_registers_and_404_for_any_other(actions, tmp_path):
    github, runs = GitHub(tmp_path), f"repos/{OWN}/actions/runs"
    url = actions.register(5, "abc", {"redline": "failure"}, event="pull_request", head_branch=None)
    assert json.loads(github.run("gh", "api", f"{runs}/5")) == {
        "id": 5, "html_url": url, "event": "pull_request", "head_sha": "abc", "path": ".github/workflows/redline.yml",
        "status": "completed", "repository": {"full_name": "acme/toy"}}
    assert json.loads(github.run("gh", "api", f"{runs}/5/jobs"))["jobs"] == [
        {"name": "redline", "status": "completed", "conclusion": "failure"}]
    assert json.loads(github.run("gh", "api", f"repos/{OWN}"))["full_name"] == "acme/toy"
    for path in (f"{runs}/6", f"{runs}/6/jobs", "repos/other/repo/actions/runs/5", "repos/other/repo"):
        with pytest.raises(RuntimeError, match=re.escape(f"gh api {path}: gh: Not Found (HTTP 404)")):
            github.run("gh", "api", path)
    assert actions.asked == [f"{runs}/5", f"{runs}/5/jobs", f"repos/{OWN}", f"{runs}/6", f"{runs}/6/jobs",
                             "repos/other/repo/actions/runs/5", "repos/other/repo"]
    assert github.run("git", "--version").startswith("git version")  # any other command runs as before


@pytest.mark.spec("LEDGER.RUN.S1", new=True)
def test_a_note_on_its_own_run_keeps_its_result_and_a_copy_on_another_commit_is_unconfirmed(change, capsys, actions):
    _, red = land(change, "red", {"tests/test_greet.py": RED})
    _, green = land(change, "green", {"tests/test_greet.py": GREEN})
    run = actions.register(1, red)
    noted(change, red, "pass", run)
    noted(change, green, "pass", run)  # the red's note, copied onto a commit whose run it isn't
    entry = rebuilt(change, capsys)["scenarios"]["GREET.S1"]
    assert entry["red"]["result"] == "pass"
    assert entry["green"]["result"] == "unconfirmed"


CRAFTED = {  # each run is on the noted commit and its redline job concluded success
    "pull_request": ({"event": "pull_request"}, None),
    "another branch": ({"head_branch": "feature"}, None),
    "a branch named like main": ({"head_branch": "main-forged"}, None),
    "main as a ref": ({"head_branch": "refs/heads/main"}, None),
    "another workflow": ({"path": ".github/workflows/other.yml"}, None),
    "a workflow named like redline.yml": ({"path": ".github/workflows/redline.yml.forged"}, None),
    "redline.yml in another directory": ({"path": "forged/.github/workflows/redline.yml"}, None),
    "another html_url": ({"html_url": "https://github.com/acme/forged/actions/runs/1"}, None),
    "a note naming another host": ({}, "https://forged.example/acme/toy/actions/runs/1"),
    "a note naming another scheme": ({}, "http://github.com/acme/toy/actions/runs/1"),
    "no event": ({"event": None}, None),
    "no head_branch": ({"head_branch": None}, None),
    "no path": ({"path": None}, None),
    "no html_url": ({"html_url": None}, None),
    "no head_sha": ({"head_sha": None}, None),
}


@pytest.mark.parametrize(("fields", "named"), CRAFTED.values(), ids=CRAFTED)
@pytest.mark.spec("LEDGER.RUN.S2", new=True)
def test_a_run_of_another_event_branch_workflow_or_url_confirms_nothing(change, capsys, actions, fields, named):
    _, red = land(change, "red", {"tests/test_greet.py": RED})
    noted(change, red, "pass", actions.register(1, red))
    assert rebuilt(change, capsys)["scenarios"]["GREET.S1"]["red"]["result"] == "pass"
    run = actions.register(1, red, **fields)
    noted(change, red, "pass", named or run)
    assert rebuilt(change, capsys)["scenarios"]["GREET.S1"]["red"]["result"] == "unconfirmed"


@pytest.mark.spec("LEDGER.RUN.S2", new=True)
def test_another_repositorys_run_confirms_nothing_though_github_has_it_there(change, capsys, actions):
    _, red = land(change, "red", {"tests/test_greet.py": RED})
    noted(change, red, "pass", actions.register(1, red))
    assert rebuilt(change, capsys)["scenarios"]["GREET.S1"]["red"]["result"] == "pass"
    noted(change, red, "pass", actions.register(77, red, where="other/repo"))  # this repository has no run 77
    assert rebuilt(change, capsys)["scenarios"]["GREET.S1"]["red"]["result"] == "unconfirmed"
    assert f"repos/{OWN}/actions/runs/77" in actions.asked and not any("other/repo" in p for p in actions.asked)


DISAGREE = {  # (the note's result, its break map, the run's jobs)
    "pass beside a failed job": ("pass", {"GREET.H1": "pass"}, FAILURE),
    "pass, no entry for H, beside a failed job": ("pass", None, FAILURE),
    "fail beside a job that succeeded": ("fail", {"GREET.H1": "pass"}, None),
    "fail, no entry for H, beside a job that succeeded": ("fail", None, None),
    "a failed break beside a job that succeeded": ("pass", {"GREET.H1": "fail"}, None),
    "an entry fail for a scenario never in the change": ("pass", {"GREET.H1": "pass", "GREET.H9": "fail"}, FAILURE),
    "no redline job": ("pass", {"GREET.H1": "pass"}, {"note": "success"}),
    "no jobs": ("pass", {"GREET.H1": "pass"}, {}),
    "a job named Redline": ("pass", {"GREET.H1": "pass"}, {"Redline": "success"}),
    "a job named like redline": ("pass", {"GREET.H1": "pass"}, {"redline / forged": "success", "note": "success"}),
    "a redline job not concluded": ("pass", {"GREET.H1": "pass"}, {"redline": None}),
}


@pytest.mark.parametrize(("result", "breaks", "jobs"), DISAGREE.values(), ids=DISAGREE)
@pytest.mark.spec("LEDGER.RUN.S3", new=True)
def test_a_note_its_redline_job_disagrees_with_reads_unconfirmed_and_so_do_its_breaks(change, capsys, actions,
                                                                                      result, breaks, jobs):
    merged = held(change, "GREET.H1")
    noted(change, merged, result, actions.register(1, merged, jobs), breaks)
    assert read(change, capsys) == ("unconfirmed", "unconfirmed")


@pytest.mark.spec("LEDGER.RUN.S3", new=True)
def test_a_note_its_redline_job_agrees_with_keeps_its_result_and_a_fail_note_fails_every_break(change, capsys, actions):
    merged = held(change, "GREET.H1")
    agree = [("pass", {"GREET.H1": "pass"}, None, ("pass", "pass")),
             ("pass", {"GREET.H1": "fail"}, FAILURE, ("pass", "fail")),  # CI's own note of a failed break
             ("pass", {"GREET.H1": "pass", "GREET.H9": "fail"}, None, ("pass", "pass")),
             ("fail", {"GREET.H1": "fail"}, FAILURE, ("fail", "fail")),
             ("fail", {"GREET.H1": "pass"}, FAILURE, ("fail", "fail")),  # a forged entry can't pass a failed run
             ("fail", None, FAILURE, ("fail", "fail"))]
    for result, breaks, jobs, want in agree:
        noted(change, merged, result, actions.register(1, merged, jobs), breaks)
        assert read(change, capsys) == want, (result, breaks, jobs)


@pytest.mark.parametrize("how", ["dropped", "retagged"])
@pytest.mark.spec("LEDGER.RUN.S3", new=True)
def test_an_entry_for_a_scenario_the_change_no_longer_holds_counts_for_nothing(change, capsys, actions, how):
    merged = held(change, "GREET.H1", "GREET.H2")
    delta = (change.path / f"{CHANGE}/specs/greet/delta.md").read_text(encoding="utf-8")
    later = delta.split("\n#### Scenario GREET.H2")[0] if how == "dropped" else delta.replace("H2 [hold]", "H2 [new]")
    change.commit(f"GREET.H2 {how} after R", {f"{CHANGE}/specs/greet/delta.md": later})
    noted(change, merged, "pass", actions.register(1, merged), {"GREET.H1": "pass", "GREET.H2": "fail"})
    assert read(change, capsys) == ("pass", "pass")
    actions.register(1, merged, FAILURE)  # H2's failed break failed the job; the ledger no longer reads it
    assert read(change, capsys) == ("unconfirmed", "unconfirmed")


@pytest.mark.spec("LEDGER.RUN.S3", new=True)
def test_a_greens_note_whose_entry_fails_beside_a_failed_job_is_unconfirmed_and_reads_no_break(change, capsys, actions):
    merged = held(change, "GREET.H1")
    noted(change, merged, "pass", actions.register(1, merged), {"GREET.H1": "pass"})
    _, green = land(change, "green", {"tests/test_greet.py": GREEN})
    noted(change, green, "pass", actions.register(2, green, FAILURE), {"GREET.H1": "fail"})
    scenarios = rebuilt(change, capsys)["scenarios"]
    assert scenarios["GREET.H1"]["break"]["result"] == "pass"
    assert scenarios["GREET.S1"]["green"]["result"] == "unconfirmed"


NO_RUN = {  # what the green's note names, beside run 2, a push run on the green's merge that would check out
    "a run GitHub doesn't have": "https://github.com/acme/toy/actions/runs/9",
    "not a URL of GitHub's": "https://ci/2",
    "a run's attempt": "https://github.com/acme/toy/actions/runs/2/attempts/1",
    "a run's URL and a slash": "https://github.com/acme/toy/actions/runs/2/",
    "a run's URL and a query": "https://github.com/acme/toy/actions/runs/2?pr=1",
    "an id that isn't a number": "https://github.com/acme/toy/actions/runs/two",
    "a pull request": "https://github.com/acme/toy/pull/2",
    "no run line": None,
}


@pytest.mark.parametrize("named", NO_RUN.values(), ids=NO_RUN)
@pytest.mark.spec("LEDGER.RUN.S4", new=True)
def test_a_missing_run_a_url_that_isnt_a_run_or_no_run_line_reads_unconfirmed(change, capsys, actions, named):
    _, red = land(change, "red", {"tests/test_greet.py": RED})
    _, green = land(change, "green", {"tests/test_greet.py": GREEN})
    noted(change, red, "pass", actions.register(1, red))
    actions.register(2, green)
    noted(change, green, "pass", named)
    entry = rebuilt(change, capsys)["scenarios"]["GREET.S1"]
    assert (entry["red"]["result"], entry["green"]["result"]) == ("pass", "unconfirmed")


@pytest.mark.spec("LEDGER.RUN.S4", new=True)
def test_each_run_is_asked_about_once_in_a_rebuild_and_a_404_at_once(change, capsys, actions, monkeypatch):
    waits = []
    monkeypatch.setattr(time, "sleep", waits.append)
    _, red = land(change, "red", {"tests/test_greet.py": RED})  # GREET.S1's and S2's reds, both on this note
    _, green = land(change, "green", {"tests/test_greet.py": GREEN})
    noted(change, red, "pass", actions.register(1, red))
    noted(change, green, "pass", actions.url(9))
    scenarios = rebuilt(change, capsys)["scenarios"]
    assert [actions.asked.count(f"repos/{OWN}/actions/runs/{run}") for run in (1, 9)] == [1, 1], actions.asked
    assert actions.asked.count(f"repos/{OWN}/actions/runs/1/jobs") <= 1 and waits == []
    assert {(entry["red"]["result"], entry["green"]["result"]) for entry in scenarios.values()} == {("pass", "unconfirmed")}


ERRORS = {
    "500": "gh: Server Error (HTTP 500)",
    "502": "gh: HTTP 502: Bad Gateway",
    "403": "gh: API rate limit exceeded for installation. (HTTP 403)",
    "401": "gh: Bad credentials (HTTP 401)",
}


@pytest.mark.parametrize("error", ERRORS.values(), ids=ERRORS)
@pytest.mark.spec("LEDGER.RUN.S5", new=True)
def test_any_other_failure_to_read_a_run_is_an_error_naming_it_and_writes_no_ledger(change, capsys, actions,
                                                                                     monkeypatch, error):
    monkeypatch.setattr(time, "sleep", lambda seconds: None)
    _, red = land(change, "red", {"tests/test_greet.py": RED})
    run = actions.register(1, red)
    noted(change, red, "pass", run)
    actions.errors[OWN, "1"] = error
    code, out = ledger(change, capsys)
    assert code == 2 and run in out, out
    assert not (change.path / LEDGER).exists()
    actions.errors.clear()
    assert ledger(change, capsys)[0] == 0


@pytest.mark.spec("LEDGER.RUN.S5", new=True)
def test_a_repository_github_doesnt_show_or_no_gh_is_an_error_and_no_run_is_asked_for(change, capsys, actions):
    _, red = land(change, "red", {"tests/test_greet.py": RED})
    noted(change, red, "pass", actions.register(1, red))
    actions.hidden = True
    code, out = ledger(change, capsys)
    assert code == 2 and "GitHub doesn't show the checkout's repository to the token" in out, out
    assert actions.asked and not any("/actions/" in path for path in actions.asked)
    actions.hidden, actions.missing = False, True
    code, out = ledger(change, capsys)
    assert code == 2 and "`gh` is needed to check the CI notes" in out, out
    actions.missing = False
    assert ledger(change, capsys)[0] == 0


@pytest.mark.spec("LEDGER.RUN.S5", new=True)
def test_a_note_that_isnt_yaml_or_has_no_result_is_an_error_naming_its_commit_before_github_is_asked(
        change, capsys, actions):
    _, red = land(change, "red", {"tests/test_greet.py": RED})
    run = actions.register(1, red)
    for text in (f"result: maybe\nrun: {run}\n", f"{{result: pass\nrun: {run}\n", f"result: pass\n\trun: {run}\n"):
        change.git("notes", "--ref=redline-ci", "add", "-f", "-m", text, red)
        code, out = ledger(change, capsys)
        assert code == 2 and red[:7] in out and actions.asked == [], (text, out)


@pytest.mark.spec("LEDGER.RUN.S6", new=True)
def test_check_close_refuses_a_note_that_doesnt_match_its_run_and_isnt_waiting(change, capsys, actions):
    red, green = red_and_green(change)
    noted(change, red, "pass", actions.register(1, red))
    noted(change, green, "pass", actions.register(2, green, event="pull_request"))
    code, out = close(change, capsys)
    lines = [line for line in out.splitlines() if line.startswith("GREET.S1: green")]
    assert code == 1 and lines, out
    assert green[:7] in lines[0] and "doesn't match its run on GitHub" in lines[0], out
    assert "waiting" not in out and "unverified" not in out
    actions.register(2, green)
    assert close(change, capsys) == (0, "ok: 2 scenarios, each with its evidence on main\n")


@pytest.mark.spec("LEDGER.RUN.S7", new=True)
def test_the_workflow_notes_its_own_run_and_grants_actions_read_to_the_jobs_that_read_runs():
    flow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    push = next(s for s in flow["jobs"]["redline"]["steps"] if "redline ci push" in s.get("run", ""))
    url = "${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"
    assert f'--run-url "{url}"' in push["run"]
    grants = [flow["permissions"], *(job["permissions"] for job in flow["jobs"].values())]
    assert all(isinstance(grant, dict) and grant.get("actions") != "write" for grant in grants), grants
    assert [flow["jobs"][name]["permissions"].get("actions") for name in ("redline", "runners")] == ["read", "read"]
