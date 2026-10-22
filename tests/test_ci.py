import base64
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from redline.cli import main
from redline.pr import gates
from test_ledger import LEDGER, RED, land
from test_pr import RED_TESTS
from test_start import DELTA, STEPS, change, fresh_branch, merge_step  # noqa: F401 (change is a fixture)

RUN = "https://github.com/toy/toy/actions/runs/7"
WORKFLOW = Path(__file__).parent.parent / ".github/workflows/redline.yml"
BROKEN = "def test_broken():\n    assert False\n"


class FakeRemote:
    """Stands in for pushing refs/notes/redline-ci: records the note as it stood at each push."""

    def __init__(self):
        self.fail = False
        self.pushed: list[str] = []

    def __call__(self, repo):
        self.repo = repo
        return self

    def push_notes(self) -> None:
        if self.fail:
            raise RuntimeError("git push: refs/notes/redline-ci was rejected")
        shown = subprocess.run(["git", "notes", "--ref=redline-ci", "show", "HEAD"], cwd=self.repo, capture_output=True, text=True)
        self.pushed.append(shown.stdout.strip())


@pytest.fixture
def remote(monkeypatch) -> FakeRemote:
    fake = FakeRemote()
    monkeypatch.setattr("redline.ci.Remote", fake, raising=False)
    return fake


def ci(repo, capsys, *args: str) -> tuple[int, str]:
    code = main(["ci", *args, "--repo", str(repo.path)])
    return code, capsys.readouterr().out


def red_pr(repo, capsys, files: dict[str, str], trailers: tuple[str, ...] = ("add-greet/R",), ledger: bool = True) -> None:
    """The R step's branch, its commits carrying `trailers`, with the ledger as main stands."""
    merge_step(repo, "S")
    fresh_branch(repo, "r-step")
    if ledger:
        assert main(["ledger", "add-greet", "--repo", str(repo.path)]) == 0
        capsys.readouterr()
    repo.commit(f"red tests\n\nRedline-Step: {trailers[0]}" if trailers[0] else "red tests", files)
    for trailer in trailers[1:]:
        repo.commit(f"more\n\nRedline-Step: {trailer}")


def test_a_pr_that_passes_the_gates_the_suite_and_check_ledger(change, capsys):
    red_pr(change, capsys, {"tests/test_greet.py": RED_TESTS})
    code, out = ci(change, capsys, "pr", "--base", "main")
    assert code == 0, out
    assert "ok: add-greet/R passes the gates, the test suite and check-ledger" in out


def fake_python(where: Path) -> str:
    """An interpreter that runs nothing: it prints its arguments and exits 3."""
    if os.name == "nt":
        path = where / "python.cmd"
        path.write_text("@echo off\r\necho fake python ran %*\r\nexit /b 3\r\n", encoding="utf-8")
    else:
        path = where / "python"
        path.write_text('#!/bin/sh\necho "fake python ran $*"\nexit 3\n', encoding="utf-8")
        path.chmod(0o755)
    return str(path)


def test_a_pr_run_with_python_runs_the_suite_with_that_interpreter(change, capsys, tmp_path):  # O-SELF2
    change.commit("a test", {"tests/test_ok.py": "def test_ok():\n    assert True\n"})
    fresh_branch(change, "outside")
    change.commit("outside any step", {"notes.txt": "text\n"})
    code, out = ci(change, capsys, "pr", "--base", "main", "--python", fake_python(tmp_path))
    assert code == 1
    assert "suite: the test suite failed (pytest exit 3): fake python ran -m pytest -q -p no:cacheprovider" in out
    code, out = ci(change, capsys, "pr", "--base", "main")  # and the gate's own Python again after it
    assert code == 0, out


def test_python_must_be_a_file_and_is_for_a_pr_only(change, capsys, tmp_path, remote):
    code, out = ci(change, capsys, "pr", "--base", "main", "--python", str(tmp_path / "nowhere"))
    assert (code, out) == (2, f"redline: --python {tmp_path / 'nowhere'} isn't a file\n")
    code, out = ci(change, capsys, "push", "--run-url", RUN, "--python", fake_python(tmp_path))
    assert (code, out) == (2, "redline: --python is for ci pr only: a push run's suite is the merged code's own\n")
    assert remote.pushed == []


def test_a_pr_is_at_most_one_step(change, capsys):  # no step at all: test_outside.py
    red_pr(change, capsys, {"tests/test_greet.py": RED_TESTS}, ("add-greet/R", "add-greet/G1"))
    code, out = ci(change, capsys, "pr", "--base", "main")
    assert code == 1
    assert "refused: more than one step in main..HEAD: add-greet/G1, add-greet/R" in out
    assert "check-" not in out


def step_pr(repo, capsys, trailer: str, merged: tuple[str, ...] = (), files: dict[str, str] | None = None) -> str:
    """A branch whose one commit carries `trailer`, with `merged` steps landed on main first; CI's output."""
    for step in merged:
        merge_step(repo, step)
    fresh_branch(repo, "step")
    repo.commit(f"work\n\nRedline-Step: {trailer}", files or {"redline/specs/greet/spec.md": "# Greet\n"})
    code, out = ci(repo, capsys, "pr", "--base", "main")
    assert code == 1
    return out


@pytest.mark.parametrize(("trailer", "files"), [
    ("add-greet/X", None),
    ("add-greet/G3", {"redline/changes/add-greet/steps.md": STEPS.replace("## C:", "## G3: More\n\n## C:")}),
], ids=["unknown", "added-by-the-pr"])
def test_a_step_that_steps_md_lacks_at_the_merge_base_is_refused_before_any_gate(change, capsys, trailer, files):
    out = step_pr(change, capsys, trailer, ("S", "R", "G1", "G2"), files)
    step = trailer.partition("/")[2]
    assert f"refused: {trailer}: redline/changes/add-greet/steps.md at the merge-base has no step {step}" in out
    assert "check-" not in out and "suite:" not in out


@pytest.mark.parametrize(("merged", "missing"), [
    (("S",), "add-greet/R"),
    ((), "add-greet/S, add-greet/R"),  # invariant 1: the spec before the code
], ids=["R", "S-and-R"])
def test_a_step_whose_earlier_steps_arent_merged_is_refused(change, capsys, merged, missing):
    out = step_pr(change, capsys, "add-greet/G1", merged)
    assert f"refused: add-greet/G1 isn't next; not merged on main: {missing}" in out
    assert "check-" not in out


def test_a_step_already_merged_is_refused(change, capsys):
    out = step_pr(change, capsys, "add-greet/R", ("S", "R"))
    assert "refused: add-greet/R is already merged on main: a step is one PR" in out
    assert "check-" not in out


def test_a_step_before_c_that_edits_the_living_specs_fails_as_the_local_pr_says(change, capsys):
    out = step_pr(change, capsys, "add-greet/G1", ("S", "R"))
    line = ("check-specs: redline/specs/greet/spec.md changed since the merge-base with main; "
            "only the C step writes redline/specs/, from its delta")
    assert line in out.splitlines()
    assert line in gates(change.path, "add-greet", "G1")


def test_a_change_with_no_steps_md_at_the_merge_base_can_only_be_at_its_s_step(change, capsys):
    wave = {"redline/changes/add-wave/steps.md": STEPS, "redline/changes/add-wave/specs/wave/delta.md": DELTA.replace("GREET", "WAVE")}
    out = step_pr(change, capsys, "add-wave/G1", files=wave)
    assert ("refused: add-wave/G1: redline/changes/add-wave has no steps.md at the merge-base, "
            "so it can only be at its S step, which writes it") in out
    change.git("commit", "-q", "--amend", "-m", "the spec\n\nRedline-Step: add-wave/S")
    code, out = ci(change, capsys, "pr", "--base", "main")
    assert "refused" not in out
    assert "check-audit:" in out  # S's own gates ran


def test_a_pr_prints_every_failure(change, capsys):
    half = RED_TESTS.split('@pytest.mark.spec("GREET.S2"')[0] + BROKEN
    red_pr(change, capsys, {"tests/test_greet.py": half}, ledger=False)
    code, out = ci(change, capsys, "pr", "--base", "main")
    assert code == 1
    assert "check-links: unlinked scenario GREET.S2" in out
    assert "suite: the test suite failed" in out
    assert f"check-ledger: {LEDGER}: missing; run `redline ledger add-greet`" in out
    assert "ok:" not in out


def test_a_pr_checks_the_ledger_against_its_base(change, capsys):
    red_pr(change, capsys, {"tests/test_greet.py": RED_TESTS})
    before = change.git("rev-parse", "main")
    land(change, "red-elsewhere", {"tests/test_other.py": RED})  # main gains red evidence for GREET.S1
    change.git("checkout", "-q", "r-step")
    code, out = ci(change, capsys, "pr", "--base", "main")
    assert code == 1
    assert f"check-ledger: {LEDGER}: GREET.S1 doesn't match the history of main" in out
    code, out = ci(change, capsys, "pr", "--base", before)
    assert code == 0, out


def test_a_push_to_main_notes_the_suite_result_on_the_merged_commit(change, capsys, remote):
    _, merge = land(change, "red", {"tests/test_greet.py": RED})
    code, out = ci(change, capsys, "push", "--run-url", RUN)
    assert code == 0, out
    assert change.git("notes", "--ref=redline-ci", "show", merge) == f"result: pass\nrun: {RUN}"
    assert remote.pushed == [f"result: pass\nrun: {RUN}"]
    assert main(["ledger", "add-greet", "--repo", str(change.path)]) == 0
    ledger = yaml.safe_load((change.path / LEDGER).read_text(encoding="utf-8"))
    assert ledger["scenarios"]["GREET.S1"]["red"]["result"] == "pass"


def test_a_push_records_a_failed_run_and_fails(change, capsys, remote):
    _, merge = land(change, "broken", {"tests/test_broken.py": BROKEN})
    code, out = ci(change, capsys, "push", "--run-url", RUN)
    assert code == 1
    assert "suite: the test suite failed" in out
    assert change.git("notes", "--ref=redline-ci", "show", merge) == f"result: fail\nrun: {RUN}"
    assert remote.pushed == [f"result: fail\nrun: {RUN}"]


def test_a_rejected_notes_push_is_an_error(change, capsys, remote):
    remote.fail = True
    land(change, "red", {"tests/test_greet.py": RED})
    code, out = ci(change, capsys, "push", "--run-url", RUN)
    assert code == 2
    assert "refs/notes/redline-ci was rejected" in out


def test_the_workflow_runs_redline_ci_on_prs_and_on_pushes_to_main():
    flow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    triggers = flow.get("on", flow.get(True))  # YAML 1.1 reads a bare `on` key as true
    assert triggers["pull_request"]["branches"] == ["main"]
    assert triggers["push"]["branches"] == ["main"]
    runs = [step.get("run", "") for job in flow["jobs"].values() for step in job["steps"]]
    assert any("redline ci pr" in run for run in runs)
    assert any("redline ci push" in run for run in runs)


def test_a_push_with_note_writes_the_note_to_the_file_and_adds_and_pushes_nothing(change, capsys, remote, tmp_path):
    land(change, "red", {"tests/test_greet.py": RED})
    code, out = ci(change, capsys, "push", "--run-url", RUN, "--note", str(tmp_path / "note"))
    assert code == 0, out
    assert (tmp_path / "note").read_text(encoding="utf-8") == f"result: pass\nrun: {RUN}\n"
    assert change.git("notes", "--ref=redline-ci", "list") == "" and remote.pushed == []


def test_a_push_with_note_still_writes_a_failed_run(change, capsys, remote, tmp_path):
    land(change, "broken", {"tests/test_broken.py": BROKEN})
    code, out = ci(change, capsys, "push", "--run-url", RUN, "--note", str(tmp_path / "note"))
    assert code == 1 and "suite: the test suite failed" in out
    assert (tmp_path / "note").read_text(encoding="utf-8") == f"result: fail\nrun: {RUN}\n"
    assert remote.pushed == []


NOTE_LINES = {  # every line the job that writes the note may run: git alone, on the workflow's commit
    "printf '%s' \"$NOTE\" | base64 -d > \"$RUNNER_TEMP/note\"",
    "for attempt in 1 2 3 4 5; do",
    "git fetch --no-tags origin '+refs/notes/*:refs/notes/*'",
    'git -c user.name=redline-ci -c user.email=redline-ci@users.noreply.github.com '
    'notes --ref=redline-ci add -f -F "$RUNNER_TEMP/note" "$GITHUB_SHA"',
    "git push origin refs/notes/redline-ci && exit 0",
    'sleep "$attempt"',
    "done",
    "exit 1",
}


def test_only_the_note_job_can_write_and_it_runs_no_repository_code():
    flow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert flow["permissions"] == {"contents": "read"}
    writers = [name for name, job in flow["jobs"].items() if job.get("permissions", {}).get("contents") != "read"]
    assert writers == ["note"] and flow["jobs"]["note"]["permissions"] == {"contents": "write"}
    job = flow["jobs"]["note"]
    assert job["needs"] == "redline" and "github.event_name == 'push'" in job["if"]
    for step in job["steps"]:
        if "uses" in step:
            assert step["uses"].startswith("actions/checkout@") and "run" not in step, step
            assert not {"submodules", "lfs"} & set(step.get("with", {})), step
        else:
            lines = [line.strip() for line in step["run"].splitlines() if line.strip()]
            assert all(line in NOTE_LINES for line in lines), lines
            assert "${{" not in step["run"]
    assert {line.strip() for s in job["steps"] for line in s.get("run", "").splitlines() if line.strip()} == NOTE_LINES
    assert next(s for s in job["steps"] if "run" in s)["env"] == {"NOTE": "${{ needs.redline.outputs.note }}"}


def test_every_job_that_runs_repository_code_is_read_only_and_drops_its_credentials():
    flow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    for name, job in flow["jobs"].items():
        if name != "note":
            assert job["permissions"]["contents"] == "read", name
            checkouts = [s for s in job["steps"] if s.get("uses", "").startswith("actions/checkout@")]
            assert checkouts and all(s["with"]["persist-credentials"] is False for s in checkouts), name
    steps = flow["jobs"]["redline"]["steps"]
    fetch = next(s for s in steps if "refs/notes/*" in s.get("run", ""))
    assert "http.extraheader" in fetch["run"] and fetch["env"]["GH_TOKEN"] == "${{ github.token }}"
    push = next(s for s in steps if "redline ci push" in s.get("run", ""))
    assert '--note "$RUNNER_TEMP/note"' in push["run"]
    handed = next(s for s in steps if s.get("id") == "note")
    assert "always()" in handed["if"] and "base64 -w0" in handed["run"] and "GITHUB_OUTPUT" in handed["run"]
    assert flow["jobs"]["redline"]["outputs"] == {"note": "${{ steps.note.outputs.note }}"}


def test_a_push_run_has_a_concurrency_group_of_its_own_and_a_pr_run_shares_its_refs():
    group = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["concurrency"]["group"]
    push, _, pr = group.partition("||")
    assert "github.event_name == 'push'" in push and "github.run_id" in push and "github.ref" not in push, group
    assert "github.ref" in pr and "github.run_id" not in pr, group


def bash() -> str | None:
    """Git's own bash, the shell the note job runs in; on Windows not WSL's, which `bash` may name."""
    if os.name != "nt":
        return shutil.which("bash")
    found = shutil.which("git")  # Git\cmd\git.exe or Git\mingw64\bin\git.exe, beside Git\bin\bash.exe
    shells = [parent / "bin" / "bash.exe" for parent in Path(found).resolve().parents] if found else []
    return next((str(shell) for shell in shells if shell.is_file()), None)


def git_in(where: Path, *args: str) -> str:
    done = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=where, capture_output=True, text=True, check=True)
    return done.stdout.strip()


def run_note_job(tmp_path: Path, hook: str) -> tuple[subprocess.CompletedProcess, Path, str, str]:
    """The note job's own script, read from the workflow, on a clone of a bare origin whose pre-receive hook is `hook`.

    `$OTHER` in the hook is a commit another run notes; the hook's git runs outside the push's quarantine."""
    shell = bash()
    if not shell:
        pytest.skip("no Git bash to run the note job's script")
    origin, work, job, bin_dir = (tmp_path / name for name in ("origin", "work", "job", "bin"))
    git_in(tmp_path, "init", "-q", "--bare", str(origin))
    git_in(tmp_path, "init", "-q", str(work))
    git_in(work, "commit", "-q", "--allow-empty", "-m", "other run's merge")
    other = git_in(work, "rev-parse", "HEAD")
    git_in(work, "commit", "-q", "--allow-empty", "-m", "this run's merge")
    git_in(work, "push", "-q", str(origin), "HEAD:refs/heads/main")
    git_in(tmp_path, "clone", "-q", "--branch", "main", str(origin), str(job))
    mine = git_in(job, "rev-parse", "HEAD")
    quarantine = "env -u GIT_QUARANTINE_PATH -u GIT_OBJECT_DIRECTORY -u GIT_ALTERNATE_OBJECT_DIRECTORIES"
    (origin / "hooks" / "pre-receive").write_bytes(f"#!/bin/sh\nOTHER={other}\nQ='{quarantine}'\n{hook}".encode())
    (origin / "hooks" / "pre-receive").chmod(0o755)
    bin_dir.mkdir()
    (bin_dir / "sleep").write_bytes(b'#!/bin/sh\necho "$1" >> "$SLEEPS"\n')  # no waiting, and each wait counted
    (bin_dir / "sleep").chmod(0o755)
    note = f"result: pass\nrun: {RUN}\n"
    script = next(s["run"] for s in yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["note"]["steps"] if "run" in s)
    env = {**os.environ, "NOTE": base64.b64encode(note.encode()).decode(), "RUNNER_TEMP": str(tmp_path),
           "GITHUB_SHA": mine, "SLEEPS": str(tmp_path / "sleeps"), "PUSHES": str(tmp_path / "pushes")}
    done = subprocess.run([shell, "-eo", "pipefail", "-c", f'export PATH="$(cygpath -u "{bin_dir}" 2>/dev/null || echo "{bin_dir}"):$PATH"\n{script}'],
                          cwd=job, env=env, capture_output=True, text=True)
    return done, origin, other, mine


def test_the_note_job_overtaken_by_another_run_fetches_re_adds_and_keeps_both_notes(tmp_path):
    hook = ('if [ -f "$PUSHES" ]; then echo x >> "$PUSHES"; exit 0; fi\n'
            'echo x >> "$PUSHES"\n'
            '$Q git -c user.name=o -c user.email=o@o notes --ref=redline-ci add -m "result: fail" "$OTHER"\n'
            'exit 1\n')  # another run pushed between this run's fetch and its push
    done, origin, other, mine = run_note_job(tmp_path, hook)
    assert done.returncode == 0, done.stderr
    assert git_in(origin, "notes", "--ref=redline-ci", "show", other) == "result: fail"
    assert git_in(origin, "notes", "--ref=redline-ci", "show", mine) == f"result: pass\nrun: {RUN}"
    assert (tmp_path / "pushes").read_text().count("x") == 2 and (tmp_path / "sleeps").read_text().split() == ["1"]


def test_the_note_job_stops_after_five_refused_pushes_and_fails(tmp_path):
    done, origin, _, _ = run_note_job(tmp_path, 'echo x >> "$PUSHES"\nexit 1\n')
    assert done.returncode == 1
    assert (tmp_path / "pushes").read_text().count("x") == 5
    assert (tmp_path / "sleeps").read_text().split() == ["1", "2", "3", "4", "5"]
    assert subprocess.run(["git", "show-ref", "refs/notes/redline-ci"], cwd=origin, capture_output=True).returncode == 1
