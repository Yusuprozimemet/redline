import subprocess

import pytest

from redline.cli import main
from redline.start import open_step_file
from conftest import Repo
from test_start import change, fresh_branch, merge_step, start  # noqa: F401 (change is a fixture)


class FakeRemote:
    """Stands in for fetching and fast-forwarding main: may land a step's merge on main first."""

    def __init__(self, repo, landing: str = "", fail: bool = False):
        self.repo = repo
        self.landing = landing
        self.fail = fail
        self.synced = 0

    def sync(self) -> None:
        if self.fail:
            raise RuntimeError("git fetch: could not reach origin")
        self.synced += 1
        if self.landing:  # the PR was merged on GitHub; main moves without a checkout
            def git(*args: str) -> str:
                return subprocess.run(["git", *args], cwd=self.repo, check=True, capture_output=True, text=True).stdout.strip()

            tree = git("rev-parse", "main^{tree}")
            merge = git("commit-tree", tree, "-p", "main", "-m", f"Merge\n\nRedline-Step: {self.landing}")
            git("update-ref", "refs/heads/main", merge)


class Seam:
    def __init__(self):
        self.landing = ""
        self.fail = False
        self.fakes: list[FakeRemote] = []

    def __call__(self, repo) -> FakeRemote:
        self.fakes.append(FakeRemote(repo, self.landing, self.fail))
        return self.fakes[-1]


@pytest.fixture
def remote(monkeypatch) -> Seam:
    seam = Seam()
    monkeypatch.setattr("redline.merged.Remote", seam, raising=False)
    return seam


def merged(repo, capsys, step: str) -> tuple[int, str]:
    code = main(["merged", step, "--repo", str(repo.path)])
    return code, capsys.readouterr().out


def branch(repo) -> str:
    return repo.git("branch", "--show-current")


def on_step(repo, capsys, step: str, name: str) -> None:
    """A step that was started, worked on and sent off with `redline pr`, record left behind."""
    fresh_branch(repo, name)
    assert start(repo, capsys, f"add-greet/{step}")[0] == 0
    repo.commit(f"{step} work\n\nRedline-Step: add-greet/{step}", {f"{step}.md": "work\n"})


def test_syncs_confirms_switches_to_main_and_hands_off(change, capsys, remote):
    remote.landing = "add-greet/S"
    on_step(change, capsys, "S", "spec")
    code, out = merged(change, capsys, "add-greet/S")
    assert code == 0, out
    assert remote.fakes[0].synced == 1
    assert "add-greet/S is merged on main" in out
    assert "redline start add-greet/R" in out
    assert "# Brief: add-greet/R\n" in out
    assert "Goal: Red tests for greeting" in out
    assert branch(change) == "main"
    assert not open_step_file(change.path).exists()


def test_refuses_when_the_trailer_is_not_on_main(change, capsys, remote):
    on_step(change, capsys, "S", "spec")  # the trailer is on the branch, not on main
    code, out = merged(change, capsys, "add-greet/S")
    assert code == 1
    assert "add-greet/S is not merged on main" in out
    assert remote.fakes[0].synced == 1  # main was synced before looking
    assert "Brief" not in out
    assert branch(change) == "spec"
    assert open_step_file(change.path).read_text().strip() == "add-greet/S"


def test_last_step_says_the_change_is_complete(change, capsys, remote):
    for step in ("S", "R", "G1", "G2"):
        merge_step(change, step)
    remote.landing = "add-greet/C"
    on_step(change, capsys, "C", "close")
    code, out = merged(change, capsys, "add-greet/C")
    assert code == 0, out
    assert "change add-greet is complete" in out
    assert "Brief" not in out
    assert branch(change) == "main"


def test_keeps_the_record_of_a_step_that_is_still_open(change, capsys, remote):
    merge_step(change, "S")
    on_step(change, capsys, "R", "red")
    code, out = merged(change, capsys, "add-greet/S")
    assert code == 0, out
    assert open_step_file(change.path).read_text().strip() == "add-greet/R"


def test_refuses_with_uncommitted_changes_before_syncing(change, capsys, remote):
    remote.landing = "add-greet/S"
    on_step(change, capsys, "S", "spec")
    (change.path / "S.md").write_text("changed\n", encoding="utf-8")
    code, out = merged(change, capsys, "add-greet/S")
    assert code == 1
    assert "uncommitted changes" in out
    assert all(fake.synced == 0 for fake in remote.fakes)
    assert branch(change) == "spec"


def test_a_failed_sync_is_an_error(change, capsys, remote):
    remote.fail = True
    on_step(change, capsys, "S", "spec")
    code, out = merged(change, capsys, "add-greet/S")
    assert code == 2
    assert "could not reach origin" in out
    assert branch(change) == "spec"


@pytest.mark.parametrize(("step", "message"), [
    ("add-greet/G9", "no step G9 in redline/changes/add-greet/steps.md"),
    ("nope/S", "no steps file redline/changes/nope/steps.md"),
    ("add-greet", "a step is <change>/<step>"),
])
def test_unknown_step_is_an_error(change, capsys, remote, step, message):
    code, out = merged(change, capsys, step)
    assert code == 2
    assert message in out


@pytest.mark.parametrize("where", ["main", "step branch"])
def test_the_real_remote_fetches_and_fast_forwards_main(repo, tmp_path, where):
    from redline.merged import Remote

    repo.commit("first")
    origin = tmp_path / "origin.git"  # a local origin: no network
    repo.git("clone", "-q", "--bare", str(repo.path), str(origin))
    repo.git("remote", "add", "origin", str(origin))
    other = Repo.__new__(Repo)
    other.path = tmp_path / "other"
    repo.git("clone", "-q", str(origin), str(other.path))
    other.git("config", "user.email", "toy@example.com")
    other.git("config", "user.name", "Toy")
    landed = other.commit("Merge\n\nRedline-Step: add-greet/S")
    other.git("push", "-q", "origin", "main")
    if where == "step branch":
        repo.git("checkout", "-q", "-b", "spec")
    Remote(repo.path).sync()
    assert repo.git("rev-parse", "main") == landed
    assert branch(repo) == ("main" if where == "main" else "spec")
