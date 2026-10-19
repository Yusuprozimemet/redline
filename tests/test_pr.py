import pytest

from redline.cli import main
from redline.start import open_step_file
from test_start import change, fresh_branch, merge_step, start  # noqa: F401 (change is a fixture)

URL = "https://github.com/toy/toy/pull/1"


class FakeGitHub:
    """Stands in for git push and gh: records what would have gone over the network."""

    def __init__(self, repo, fail: bool = False):
        self.repo = repo
        self.fail = fail
        self.calls: list[tuple] = []

    def push(self, branch: str) -> None:
        self.calls.append(("push", branch))

    def create_pr(self, title: str, body: str) -> str:
        if self.fail:
            raise RuntimeError("gh: could not create the pull request")
        self.calls.append(("pr", title, body))
        return URL


class Seam:
    def __init__(self):
        self.fail = False
        self.fakes: list[FakeGitHub] = []

    def __call__(self, repo) -> FakeGitHub:
        self.fakes.append(FakeGitHub(repo, self.fail))
        return self.fakes[-1]


@pytest.fixture
def github(monkeypatch) -> Seam:
    seam = Seam()
    monkeypatch.setattr("redline.pr.GitHub", seam, raising=False)
    return seam


def pr(repo, capsys) -> tuple[int, str]:
    code = main(["pr", "--repo", str(repo.path)])
    return code, capsys.readouterr().out


def trailers(repo, rev_range: str) -> list[str]:
    return repo.git("log", rev_range, "--format=%(trailers:key=Redline-Step,valueonly,separator=|)").splitlines()


def begin(repo, capsys, step: str, branch: str) -> None:
    fresh_branch(repo, branch)
    assert start(repo, capsys, f"add-greet/{step}")[0] == 0


def test_pr_pushes_opens_the_pr_and_ends_the_step(change, capsys, github):
    begin(change, capsys, "S", "spec")
    change.commit("proposal", {"redline/changes/add-greet/proposal.md": "why\n"})
    code, out = pr(change, capsys)
    assert code == 0, out
    assert URL in out
    calls = github.fakes[0].calls
    assert calls[0] == ("push", "spec")
    assert calls[1][:2] == ("pr", "add-greet/S: Spec for greeting")
    assert calls[1][2].rstrip().endswith("Redline-Step: add-greet/S")
    assert not open_step_file(change.path).exists()


def test_every_commit_of_the_step_carries_the_trailer_once(change, capsys, github):
    begin(change, capsys, "S", "spec")
    change.commit("one", {"a.md": "a\n"})
    change.commit("two\n\nRedline-Step: add-greet/S\nCo-Authored-By: Toy <toy@example.com>", {"b.md": "b\n"})
    change.commit("three", {"c.md": "c\n"})
    assert pr(change, capsys)[0] == 0
    assert trailers(change, "main..spec") == ["add-greet/S"] * 3
    assert trailers(change, "main") == [""]  # main's own commits are left alone


def test_refuses_with_no_open_step(change, capsys, github):
    fresh_branch(change, "spec")
    change.commit("work", {"a.md": "a\n"})
    code, out = pr(change, capsys)
    assert code == 1
    assert "no step is open" in out
    assert github.fakes == [] or github.fakes[0].calls == []


def test_refuses_with_uncommitted_changes_or_no_commits(change, capsys, github):
    begin(change, capsys, "S", "spec")
    code, out = pr(change, capsys)
    assert code == 1
    assert "no commits" in out
    change.commit("work", {"a.md": "a\n"})
    (change.path / "a.md").write_text("changed\n", encoding="utf-8")
    code, out = pr(change, capsys)
    assert code == 1
    assert "uncommitted changes" in out


def test_refuses_over_400_lines_and_keeps_the_step_open(change, capsys, github):
    begin(change, capsys, "S", "spec")
    change.commit("big", {"big.md": "x\n" * 401})
    code, out = pr(change, capsys)
    assert code == 1
    assert "401 changed lines" in out
    assert all(not fake.calls for fake in github.fakes)
    assert open_step_file(change.path).read_text().strip() == "add-greet/S"
    assert trailers(change, "main..spec") == [""]


RED_TESTS = """import pytest

@pytest.mark.spec("GREET.S1", new=True)
def test_s1():
    assert False

@pytest.mark.spec("GREET.S2", new=True)
def test_s2():
    assert False
"""


def test_red_step_with_every_scenario_linked_passes(change, capsys, github):
    merge_step(change, "S")
    begin(change, capsys, "R", "red")
    change.commit("red tests", {"tests/test_greet.py": RED_TESTS})
    code, out = pr(change, capsys)
    assert code == 0, out


def test_from_the_red_step_on_an_unlinked_scenario_refuses(change, capsys, github):
    merge_step(change, "S")
    begin(change, capsys, "R", "red")
    change.commit("half the tests", {"tests/test_greet.py": RED_TESTS.split("@pytest.mark.spec(\"GREET.S2\"")[0]})
    code, out = pr(change, capsys)
    assert code == 1
    assert "unlinked scenario GREET.S2" in out
    assert all(not fake.calls for fake in github.fakes)


def test_from_the_red_step_on_green_without_red_refuses(change, capsys, github):
    merge_step(change, "S")
    begin(change, capsys, "R", "red")
    change.commit("green too soon", {"tests/test_greet.py": RED_TESTS.replace(", new=True", "")})
    code, out = pr(change, capsys)
    assert code == 1
    assert "GREET.S1" in out and "no red commit" in out


def test_spec_step_skips_the_link_check(change, capsys, github):
    begin(change, capsys, "S", "spec")  # the delta declares GREET.S1 and S2; no tests yet
    change.commit("proposal", {"redline/changes/add-greet/proposal.md": "why\n"})
    assert pr(change, capsys)[0] == 0


def test_a_failed_pr_keeps_the_step_open(change, capsys, github):
    github.fail = True
    begin(change, capsys, "S", "spec")
    change.commit("proposal", {"redline/changes/add-greet/proposal.md": "why\n"})
    code, out = pr(change, capsys)
    assert code == 2
    assert "could not create the pull request" in out
    assert open_step_file(change.path).read_text().strip() == "add-greet/S"
