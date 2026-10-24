"""`redline install workflow`: an adopting repository's workflow, from the commit Redline was installed from
(the change install-workflow). Each test sets the running Redline's `direct_url.json` (PEP 610) through
FakeDistribution, which stands in for `importlib.metadata.distribution` as `redline.runner` imports it."""

import copy
import json
import shutil
import subprocess
import sys
import zipfile
from importlib.resources import files
from pathlib import Path

import pytest
import yaml

from redline.cli import main
from redline.runner import check_helpers

ROOT = Path(__file__).resolve().parent.parent
OWN = ROOT / ".github/workflows/redline.yml"
WRITTEN = ".github/workflows/redline.yml"
URL = "https://github.com/Yusuprozimemet/redline"
COMMIT = "dea7b6981106798b773ae799e71a404488e5b33d"
# what pip wrote on 2026-10-23 for `pip install --no-deps "redline @ git+<URL>@dea7b69"` (proposal.md)
GIT = {"url": URL, "vcs_info": {"commit_id": COMMIT, "requested_revision": "dea7b69", "vcs": "git"}}
GATE = 'redline ci pr --base main --pr ${{ github.event.pull_request.number }} --suite-result "$SUITE"'
SUITE = "redline ci suite --base main"
JOBS = ("suite", "redline")  # the jobs with an install step, in the template's order
HELPER = "redline/runners/jest.js"


class FakeDistribution:
    """The installed Redline, holding `direct_url.json` as a test sets it (None: no such file)."""

    def __init__(self):
        self.direct_url: dict | None = GIT

    def __call__(self, name: str):
        assert name == "redline"
        return self

    def read_text(self, filename: str) -> str | None:
        return json.dumps(self.direct_url) if filename == "direct_url.json" and self.direct_url is not None else None


@pytest.fixture
def installed(monkeypatch) -> FakeDistribution:
    fake = FakeDistribution()
    monkeypatch.setattr("redline.runner.distribution", fake, raising=False)
    return fake


def install(repo, capsys, runner: str = "workflow") -> tuple[int, str]:
    """The command's exit code and everything it printed; argparse's exit counts as one."""
    try:
        code = main(["install", runner, "--repo", str(repo.path)])
    except SystemExit as exit:
        code = exit.code
    out = capsys.readouterr()
    return code, out.out + out.err


def runs(step: dict, *text: str) -> bool:
    return any(part in step.get("run", "") for part in text)


def own() -> dict:
    return yaml.safe_load(OWN.read_text(encoding="utf-8"))


def own_install(job: str = "redline") -> dict:
    """Redline's own editable install step in `job`."""
    return next(step for step in own()["jobs"][job]["steps"] if runs(step, "-e ."))


def pip_lines(step: dict) -> list[str]:
    return [line.strip() for line in step["run"].splitlines() if line.strip().startswith("python -m pip")]


def written(repo, capsys) -> dict:
    """The workflow, parsed, as `redline install workflow` writes it into a repository with none."""
    repo.commit("start")
    code, out = install(repo, capsys)
    assert code == 0, out
    return yaml.safe_load((repo.path / WRITTEN).read_text(encoding="utf-8"))


def core(workflow: dict) -> dict:
    """The workflow without the jobs and steps the written one differs in: S2's comparison."""
    workflow = copy.deepcopy(workflow)
    for job in ("runners", "windows"):
        workflow["jobs"].pop(job, None)
    for job in JOBS:
        steps = workflow["jobs"].get(job, {}).get("steps", [])
        steps[:] = [step for step in steps if not runs(step, "git worktree add", "pip install")]
        for step in steps:
            if runs(step, "ci pr", "ci suite"):
                del step["run"]
    return workflow


@pytest.mark.spec("INSTALL.WF.S1", new=True)
def test_the_workflow_installs_the_commit_redline_was_installed_from(repo, capsys, installed):
    repo.commit("start")
    code, out = install(repo, capsys)
    assert code == 0, out
    assert f"ok: wrote {WRITTEN}" in out
    text = (repo.path / WRITTEN).read_text(encoding="utf-8")
    raw = text.splitlines()
    indent = next(len(line) - len(line.lstrip()) for line in raw if line.lstrip().startswith("- uses: actions/checkout"))
    pips = [line.replace(" -e .", " .") for line in pip_lines(own_install())]
    ends = [i for i, line in enumerate(raw) if line.strip() == pips[-1]]
    assert len(pips) == 3 and len(ends) == len(JOBS), ends
    for job, end in zip(JOBS, ends):  # the template's jobs are in JOBS' order
        steps = yaml.safe_load(text)["jobs"][job]["steps"]
        [at] = [i for i, step in enumerate(steps) if runs(step, "pip install")]
        step, lines = steps[at], [line.strip() for line in steps[at]["run"].splitlines()]
        clone = next(i for i, line in enumerate(lines) if line.startswith("git clone") and URL in line and "$RUNNER_TEMP" in line)
        checkout = next(i for i, line in enumerate(lines) if "checkout" in line and COMMIT in line)
        assert pip_lines(step) == pips and clone < checkout < lines.index(pips[0]), job
        if job == "redline":
            assert "if" not in step
        assert {k: v for k, v in step.items() if k not in ("name", "run", "if")} == {
            k: v for k, v in own_install(job).items() if k not in ("name", "run", "if")}, job
        ours = [s for s in own()["jobs"][job]["steps"] if not runs(s, "git worktree add", "pip install")]
        assert steps[:at] == ours[:at], job
        assert [s.get("uses", s.get("name", "")).split("@")[0] for s in steps[:at]] == [
            "actions/checkout", "Fetch main and the CI notes", "actions/setup-python"], job
        after = raw[end + 1]
        assert after.lstrip().startswith("#") and len(after) - len(after.lstrip()) == indent, after
        assert not any(after.strip() in s.get("run", "") for s in steps)
        assert ("if: github.event_name == 'push'" in after) is (job == "redline"), after
    assert check_helpers(repo.path) == []
    (repo.path / WRITTEN).write_text(text + " " * indent + "- run: npm ci --no-audit --no-fund\n", encoding="utf-8")
    assert check_helpers(repo.path) == []


@pytest.mark.spec("INSTALL.WF.S2", new=True)
def test_the_workflow_is_redlines_own_outside_the_installs_the_pr_gate_and_the_suite(repo, capsys, installed):
    workflow = written(repo, capsys)
    assert core(workflow) == core(own())
    for job, command, run in (("redline", "ci pr", GATE), ("suite", "ci suite", SUITE)):
        ours = [step for step in own()["jobs"][job]["steps"] if not runs(step, "git worktree add")]
        theirs = workflow["jobs"][job]["steps"]
        assert [i for i, step in enumerate(theirs) if runs(step, "pip install")] == [ours.index(own_install(job))], job
        [step] = [step for step in theirs if runs(step, command)]
        assert step["run"].strip() == run
    assert list(workflow["jobs"]) == ["suite", "redline", "note"]


@pytest.mark.parametrize("direct_url", [
    None,
    {"url": "file:///home/me/redline", "dir_info": {"editable": True}},
    {"url": URL, "vcs_info": {"commit_id": COMMIT, "vcs": "hg"}},
    {"url": URL, "vcs_info": {"commit_id": "dea7b69", "vcs": "git"}},
], ids=["no-direct-url", "dir-info", "hg", "short-commit"])
@pytest.mark.spec("INSTALL.WF.S3")
def test_a_redline_with_no_git_commit_to_install_writes_nothing(repo, capsys, installed, direct_url):
    repo.commit("start")
    installed.direct_url = direct_url
    code, out = install(repo, capsys)
    assert "installed from a git commit" in out and 'pip install "redline @ git+<url>@<commit>"' in out, out
    assert code == 2
    assert not (repo.path / WRITTEN).exists()


@pytest.mark.spec("INSTALL.WF.S4")
def test_an_existing_workflow_file_is_left_as_it_was(repo, capsys, installed):
    repo.commit("start")
    mine = b"# the repository's own\r\nname: mine\r\non: push\r\n"
    (repo.path / WRITTEN).parent.mkdir(parents=True)
    (repo.path / WRITTEN).write_bytes(mine)
    code, out = install(repo, capsys)
    assert WRITTEN in out, out
    assert code == 2
    assert (repo.path / WRITTEN).read_bytes() == mine


@pytest.mark.spec("INSTALL.WF.S5")
def test_the_wheel_built_from_the_tree_ships_the_template(tmp_path):
    tree, out = tmp_path / "tree", tmp_path / "wheel"
    tree.mkdir()
    shutil.copy(ROOT / "pyproject.toml", tree / "pyproject.toml")
    shutil.copytree(ROOT / "src", tree / "src", ignore=shutil.ignore_patterns("__pycache__", "*.egg-info"))
    subprocess.run([sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation", "--no-index",
                    "-q", "-w", str(out), str(tree)], check=True, capture_output=True)
    [wheel] = out.glob("redline-*.whl")
    with zipfile.ZipFile(wheel) as built:
        assert "redline/helpers/redline.yml" in built.namelist()
        assert built.read("redline/helpers/redline.yml") == (ROOT / "src/redline/helpers/redline.yml").read_bytes()


@pytest.mark.spec("INSTALL.WF.H1")
def test_install_jest_writes_over_an_edited_helper(repo, capsys):
    shipped = files("redline").joinpath("helpers", "jest.js").read_text(encoding="utf-8")
    repo.commit("edited", {HELPER: shipped.replace("test.failing", "test")})
    assert check_helpers(repo.path) != []
    code, out = install(repo, capsys, "jest")
    assert code == 0, out
    assert (repo.path / HELPER).read_bytes() == shipped.encode()
    assert check_helpers(repo.path) == []
