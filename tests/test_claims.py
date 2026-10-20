"""`redline claims <initiative>`: the claims main's history holds, for the process auditor. See docs/design.md §4, §7, §9."""

from pathlib import Path

import pytest
import yaml

from redline.cli import main
from test_merged import merged, remote  # noqa: F401 (remote is a fixture)
from test_plan import PLAN, VALID, complete, planned  # noqa: F401 (planned is a fixture)
from test_plan_audit import critical, phase_one_complete  # noqa: F401 (critical is a fixture)
from test_start import change  # noqa: F401 (change is a fixture)

AGENT = Path(__file__).parent.parent / ".claude/agents/redline-process-auditor.md"


class FakeGitHub:
    """Each commit's merged PR, and each PR's labels with who applied them."""

    pulled: dict[str, list[int]] = {}
    applied: dict[int, dict[str, str]] = {}
    roles = {"alice": "admin"}

    def __init__(self, repo):
        self.repo = repo

    def pulls(self, sha: str) -> list[int]:
        return self.pulled.get(sha, [])

    def labels(self, number: int) -> dict[str, str]:
        return self.applied.get(number, {})

    def role(self, login: str) -> str:
        return self.roles.get(login, "write")


@pytest.fixture
def github(monkeypatch):
    FakeGitHub.pulled, FakeGitHub.applied = {}, {}
    monkeypatch.setattr("redline.claims.GitHub", FakeGitHub, raising=False)
    return FakeGitHub


def claims(repo, capsys, name: str = "greetings") -> tuple[int, str]:
    code = main(["claims", name, "--repo", str(repo.path)])
    return code, capsys.readouterr().out


def step(repo, name: str, *trailers: str) -> str:
    repo.git("checkout", "-q", "main")
    return repo.commit(f"{name} done\n\n" + "".join(f"{t}\n" for t in trailers) + f"Redline-Step: {name}")


def test_prints_each_claim_of_the_initiative_with_its_pr_and_label(planned, capsys, github):
    track = step(planned, "add-greet/G1", "Redline-Track: the helper moved to greet.py")
    step(planned, "add-greet/G2")
    rigor = planned.commit("raise the plan\n\nRedline-Rigor: greetings is about logins", {PLAN: f"Rigor: critical\n{VALID}"})
    step(planned, "other/G1", "Oversized: not this initiative's")
    planned.commit("elsewhere\n\nOversized: not this initiative's either", {"other.py": "x = 1\n"})
    github.pulled = {track: [12], rigor: [13]}
    github.applied = {12: {"redline:track": "alice"}, 13: {"redline:rigor": "bob"}}
    code, out = claims(planned, capsys)
    assert code == 0, out
    lines = out.splitlines()
    assert lines[0] == "# Claims: greetings"
    assert lines[1].startswith("From main: 2 claims on 4 commits: the steps of add-greet, add-wave, add-farewell,"), out
    assert "every commit that touches redline/initiatives/greetings/ or redline/config.yaml." in out
    assert f"## {track[:7]} add-greet/G1 (PR #12): add-greet/G1 done\nRedline-Track: the helper moved to greet.py\n" \
           "Label: redline:track, applied by @alice, now admin\n" in out
    assert f"## {rigor[:7]} outside any step (PR #13): raise the plan\nRedline-Rigor: greetings is about logins\n" \
           "Label: redline:rigor, applied by @bob, now write\n" in out
    assert out.index(track[:7]) < out.index(rigor[:7]), "oldest first"
    assert "not this initiative's" not in out and "add-greet/G2" not in out


def test_a_missing_label_and_a_commit_with_no_pr_are_said(planned, capsys, github):
    departed = step(planned, "add-greet/G1", "Redline-Departure: tests/test_greet.py::test_x approved-by @alice: why")
    oversized = step(planned, "add-greet/G2", "Oversized: one change")
    github.pulled = {departed: [12]}
    code, out = claims(planned, capsys)
    assert code == 0, out
    assert f"## {departed[:7]} add-greet/G1 (PR #12): " in out
    assert "Label: redline:departure: not on PR #12\n" in out
    assert f"## {oversized[:7]} add-greet/G2: add-greet/G2 done\nOversized: one change\n" \
           "Label: no merged PR found for this commit\n" in out


def test_only_main_counts(planned, capsys, github):
    planned.git("checkout", "-q", "-b", "branch")
    planned.commit("unmerged\n\nOversized: big\nRedline-Step: add-greet/G1")
    code, out = claims(planned, capsys)
    assert code == 0, out
    assert "From main: 0 claims on 1 commit:" in out and "No claims.\n" in out and "big" not in out


def test_an_unknown_initiative_is_an_error(planned, capsys, github):
    code, out = claims(planned, capsys, "nope")
    assert code == 2 and "no plan redline/initiatives/nope/plan.md on main" in out, out


def test_merged_at_the_last_stopping_point_says_to_give_the_process_auditor_the_claims(critical, capsys, remote):
    phase_one_complete(critical)
    complete(critical, "add-farewell", ("S",))
    remote.landing = "add-farewell/C"
    critical.git("checkout", "-q", "-b", "close")
    critical.git("commit", "-q", "--allow-empty", "-m", "close")
    code, out = merged(critical, capsys, "add-farewell/C")
    assert code == 0, out
    assert "Give redline-process-auditor, after its arguments, the text `redline claims greetings` prints.\n" in out


def test_the_process_auditor_is_given_the_claims():
    _, front, body = AGENT.read_text(encoding="utf-8").split("---\n", 2)
    assert "redline claims <initiative>" in yaml.safe_load(front)["description"]
    assert "## Claims" in body and "redline claims" in body
    assert "If you were not given the text `redline claims` prints" in body
