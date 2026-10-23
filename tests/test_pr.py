import pytest

from redline.cli import main
from redline.start import open_step_file
from test_start import CHANGE, DELTA, change, fresh_branch, merge_step, start  # noqa: F401 (change is a fixture)

URL = "https://github.com/toy/toy/pull/1"
AUDIT = {f"{CHANGE}/audit.md": f"# Audit: add-greet\nModel: claude-fable-5-1\nRound: 1\nAudited: {'0' * 40}\n\nNo findings.\n"}
PUSHED = "2026-10-22T10:00:00Z"  # when the fake PR's head was pushed
LABELLED = "2026-10-22T11:00:00Z"  # when a fake label given as its applier alone was applied, after the push
HEAD = ("f" * 40, PUSHED)


class FakeGitHub:
    """Stands in for git push and gh: records what would have gone over the network."""

    def __init__(self, repo, fail: bool = False, applied: dict | None = None, roles: dict | None = None,
                 head: tuple[str, str] | None = HEAD):
        self.repo = repo
        self.fail = fail
        self.applied = {} if applied is None else applied  # label -> who applied it, or (who, when)
        self.roles = {} if roles is None else roles
        self.head = head
        self.calls: list[tuple] = []

    def push(self, branch: str) -> None:
        self.calls.append(("push", branch))

    def create_pr(self, title: str, body: str) -> str:
        if self.fail:
            raise RuntimeError("gh: could not create the pull request")
        self.calls.append(("pr", title, body))
        return URL

    def labels(self, number: int) -> dict[str, tuple[str, str]]:
        self.calls.append(("labels", number))
        return {label: by if isinstance(by, tuple) else (by, LABELLED) for label, by in self.applied.items()}

    def pushed(self, number: int) -> tuple[str, str] | None:
        self.calls.append(("pushed", number))
        return self.head

    def role(self, login: str) -> str:
        return self.roles.get(login, "write")


class Seam:
    def __init__(self):
        self.fail = False
        self.applied: dict[str, str | tuple[str, str]] = {}
        self.roles = {"maintainer": "admin"}
        self.head: tuple[str, str] | None = HEAD
        self.fakes: list[FakeGitHub] = []

    def __call__(self, repo) -> FakeGitHub:
        self.fakes.append(FakeGitHub(repo, self.fail, self.applied, self.roles, self.head))
        return self.fakes[-1]


@pytest.fixture
def github(monkeypatch) -> Seam:
    seam = Seam()
    monkeypatch.setattr("redline.pr.GitHub", seam, raising=False)
    monkeypatch.setattr("redline.ci.GitHub", seam, raising=False)
    return seam


def pr(repo, capsys) -> tuple[int, str]:
    code = main(["pr", "--repo", str(repo.path)])
    return code, capsys.readouterr().out


def trailers(repo, rev_range: str) -> list[str]:
    log = repo.git("log", rev_range, "--format=>%(trailers:key=Redline-Step,valueonly,separator=|)")
    return [line[1:] for line in log.splitlines()]


def begin(repo, capsys, step: str, branch: str) -> None:
    fresh_branch(repo, branch)
    assert start(repo, capsys, f"add-greet/{step}")[0] == 0


def test_pr_pushes_opens_the_pr_and_ends_the_step(change, capsys, github):
    begin(change, capsys, "S", "spec")
    change.commit("proposal", {"redline/changes/add-greet/proposal.md": "why\n", **AUDIT})
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
    change.commit("one", {"a.md": "a\n", **AUDIT})
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
    change.commit("proposal", {"redline/changes/add-greet/proposal.md": "why\n", **AUDIT})
    assert pr(change, capsys)[0] == 0


def test_a_failed_pr_keeps_the_step_open(change, capsys, github):
    github.fail = True
    begin(change, capsys, "S", "spec")
    change.commit("proposal", {"redline/changes/add-greet/proposal.md": "why\n", **AUDIT})
    code, out = pr(change, capsys)
    assert code == 2
    assert "could not create the pull request" in out
    assert open_step_file(change.path).read_text().strip() == "add-greet/S"


def test_spec_step_refuses_on_a_premise_that_does_not_resolve(change, capsys, github):
    begin(change, capsys, "S", "spec")
    change.commit("stale premise", {f"{CHANGE}/specs/greet/delta.md": DELTA + "- P2: Greeting happens at `greet.py:9`\n"})
    code, out = pr(change, capsys)
    assert code == 1
    assert (
        f"check-premises: {CHANGE}/specs/greet/delta.md:16: greet.py:9: "
        "line 9 is past the end of the file (2 lines)"
    ) in out
    assert all(not fake.calls for fake in github.fakes)
    assert open_step_file(change.path).read_text().strip() == "add-greet/S"


def test_spec_step_checks_only_its_own_changes_premises(change, capsys, github):
    change.commit("another change", {"redline/changes/old/specs/x/delta.md": "### Premises\n- P1: Gone — `gone.py:1`\n"})
    begin(change, capsys, "S", "spec")
    change.commit("proposal", {f"{CHANGE}/proposal.md": "why\n", **AUDIT})
    code, out = pr(change, capsys)
    assert code == 0, out


def test_spec_step_refuses_without_an_audit(change, capsys, github):
    begin(change, capsys, "S", "spec")
    change.commit("proposal", {f"{CHANGE}/proposal.md": "why\n"})
    code, out = pr(change, capsys)
    assert code == 1
    assert f"check-audit: {CHANGE}/audit.md: missing; run the auditor on the change" in out
    assert all(not fake.calls for fake in github.fakes)
    assert open_step_file(change.path).read_text().strip() == "add-greet/S"


def test_spec_step_refuses_on_an_unresolved_finding(change, capsys, github):
    begin(change, capsys, "S", "spec")
    change.commit("audit", {f"{CHANGE}/audit.md": (
        f"# Audit: add-greet\nModel: claude-fable-5-1\nRound: 1\nAudited: {'0' * 40}\n\n"
        "## F1 [open]: P1 says only a placeholder exists; say what greet.py must not do yet\n"
        "## F2 [waived]: GREET.S2's THEN clause is vague\n"
    )})
    code, out = pr(change, capsys)
    assert code == 1
    assert f"check-audit: {CHANGE}/audit.md:6: F1 is open: P1 says only a placeholder exists" in out
    assert f"check-audit: {CHANGE}/audit.md:7: F2 is waived with no `Waived-by: @person: <reason>` line" in out
    assert all(not fake.calls for fake in github.fakes)


def test_from_the_red_step_on_the_audit_is_not_checked(change, capsys, github):
    merge_step(change, "S")
    begin(change, capsys, "R", "red")  # the change has no audit.md; R doesn't ask for one
    change.commit("red tests", {"tests/test_greet.py": RED_TESTS})
    assert pr(change, capsys)[0] == 0
