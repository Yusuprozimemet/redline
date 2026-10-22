"""`redline claims <initiative>`: the claims main's history holds, for the process auditor. See docs/design.md §4, §7, §9."""

from pathlib import Path

import pytest
import yaml

from redline.cli import main
from test_ci import RUN, WORKFLOW, FakeRemote
from test_ledger import note
from test_merged import merged, remote  # noqa: F401 (remote is a fixture)
from test_plan import PLAN, VALID, complete, planned  # noqa: F401 (planned is a fixture)
from test_plan_audit import critical, phase_one_complete  # noqa: F401 (critical is a fixture)
from test_pr import HEAD, LABELLED, PUSHED
from test_start import change  # noqa: F401 (change is a fixture)

AGENT = Path(__file__).parent.parent / ".claude/agents/redline-process-auditor.md"


class FakeGitHub:
    """Each commit's merged PR, and each PR's labels with who applied them."""

    pulled: dict[str, list[int]] = {}
    applied: dict[int, dict[str, str]] = {}
    heads: dict[int, tuple[str, str]] = {}
    roles = {"alice": "admin"}
    fail = False

    def __init__(self, repo):
        self.repo = repo

    def pulls(self, sha: str) -> list[int]:
        if self.fail:
            raise RuntimeError("gh api: HTTP 502")
        return self.pulled.get(sha, [])

    def labels(self, number: int) -> dict[str, tuple[str, str]]:
        return {label: (who, LABELLED) for label, who in self.applied.get(number, {}).items()}

    def pushed(self, number: int) -> tuple[str, str] | None:
        return self.heads.get(number, HEAD)

    def role(self, login: str) -> str:
        return self.roles.get(login, "write")


@pytest.fixture
def github(monkeypatch):
    FakeGitHub.pulled, FakeGitHub.applied, FakeGitHub.roles, FakeGitHub.fail = {}, {}, {"alice": "admin"}, False
    FakeGitHub.heads = {}
    monkeypatch.setattr("redline.claims.GitHub", FakeGitHub, raising=False)
    monkeypatch.setattr("redline.ci.GitHub", FakeGitHub, raising=False)
    monkeypatch.setattr("redline.ci.Remote", FakeRemote(), raising=False)
    return FakeGitHub


def claims(repo, capsys, name: str = "greetings") -> tuple[int, str]:
    code = main(["claims", name, "--repo", str(repo.path)])
    return code, capsys.readouterr().out


def push(repo, capsys) -> tuple[int, str]:
    code = main(["ci", "push", "--run-url", RUN, "--repo", str(repo.path)])
    return code, capsys.readouterr().out


def recorded(repo, commit: str) -> dict:
    return yaml.safe_load(repo.git("notes", "--ref=redline-ci", "show", commit))


def land_claims(repo) -> tuple[str, str, str]:
    """A G1 PR with a track claim and an Oversized claim, merged as GitHub's merge button does."""
    repo.git("checkout", "-q", "main")
    repo.git("checkout", "-q", "-b", "g1")
    track = repo.commit("move\n\nRedline-Track: the helper moved\nRedline-Step: add-greet/G1",
                        {"tests/test_ok.py": "def test_ok():\n    pass\n"})
    big = repo.commit("grow\n\nOversized: one change\nRedline-Step: add-greet/G1")
    repo.git("checkout", "-q", "main")
    repo.git("merge", "-q", "--no-ff", "--no-edit", "g1")
    return track, big, repo.git("rev-parse", "HEAD")


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
           f"Label at the merge: not recorded: no CI note on {track[:7]}\n" \
           "Label now: redline:track, applied by @alice, now admin\n" in out
    assert f"## {rigor[:7]} outside any step (PR #13): raise the plan\nRedline-Rigor: greetings is about logins\n" \
           f"Label at the merge: not recorded: no CI note on {rigor[:7]}\n" \
           "Label now: redline:rigor, applied by @bob, now write\n" in out
    assert out.index(track[:7]) < out.index(rigor[:7]), "oldest first"
    assert "not this initiative's" not in out and "add-greet/G2" not in out


def test_a_missing_label_and_a_commit_with_no_pr_are_said(planned, capsys, github):
    departed = step(planned, "add-greet/G1", "Redline-Departure: tests/test_greet.py::test_x approved-by @alice: why")
    oversized = step(planned, "add-greet/G2", "Oversized: one change")
    github.pulled = {departed: [12]}
    code, out = claims(planned, capsys)
    assert code == 0, out
    assert f"## {departed[:7]} add-greet/G1 (PR #12): " in out
    assert "Label now: redline:departure: not on PR #12\n" in out
    assert f"## {oversized[:7]} add-greet/G2: add-greet/G2 done\nOversized: one change\n" \
           f"Label at the merge: not recorded: no CI note on {oversized[:7]}\n" \
           "Label now: no merged PR found for this commit\n" in out


def test_a_push_records_each_claim_of_the_merged_pr_in_the_ci_note(planned, capsys, github):
    track, big, merge = land_claims(planned)
    github.pulled = {track: [12], big: [12]}
    github.applied = {12: {"redline:track": "alice", "redline:rigor": "bob"}}
    code, out = push(planned, capsys)
    assert code == 0, out
    text = planned.git("notes", "--ref=redline-ci", "show", merge)
    assert text.startswith(f"result: pass\nrun: {RUN}\nclaims:\n"), text
    assert recorded(planned, merge)["claims"] == [
        {"commit": track, "claim": "Redline-Track: the helper moved", "pr": 12, "label": "redline:track",
         "by": "alice", "role": "admin", "at": LABELLED, "pushed": PUSHED},
        {"commit": big, "claim": "Oversized: one change", "pr": 12, "label": "redline:oversized",
         "by": None, "role": None, "at": None, "pushed": PUSHED},
    ]


def test_a_manual_check_is_recorded_at_the_merge_and_printed(planned, capsys, github):
    planned.git("checkout", "-q", "main")
    planned.git("checkout", "-q", "-b", "c")
    checked = planned.commit("close\n\nRedline-Manual: GREET.M1 checked-by @alice: it fits\nRedline-Step: add-greet/C",
                             {"tests/test_ok.py": "def test_ok():\n    pass\n"})
    planned.git("checkout", "-q", "main")
    planned.git("merge", "-q", "--no-ff", "--no-edit", "c")
    merge = planned.git("rev-parse", "HEAD")
    github.pulled = {checked: [14]}
    github.applied = {14: {"redline:manual": "alice"}}
    code, out = push(planned, capsys)
    assert code == 0, out
    assert recorded(planned, merge)["claims"] == [
        {"commit": checked, "claim": "Redline-Manual: GREET.M1 checked-by @alice: it fits", "pr": 14,
         "label": "redline:manual", "by": "alice", "role": "admin", "at": LABELLED, "pushed": PUSHED}]
    code, out = claims(planned, capsys)
    assert code == 0, out
    assert f"## {checked[:7]} add-greet/C (PR #14): close\nRedline-Manual: GREET.M1 checked-by @alice: it fits\n" \
           f"Label at the merge: redline:manual, applied by @alice, admin, at {LABELLED}, head pushed at {PUSHED} (CI note on {merge[:7]})\n" in out


def test_a_re_run_keeps_the_record_and_a_failed_read_writes_none(planned, capsys, github):
    track, big, merge = land_claims(planned)
    github.pulled, github.applied = {track: [12]}, {12: {"redline:track": "alice"}}
    assert push(planned, capsys)[0] == 0
    first = recorded(planned, merge)["claims"]
    github.applied, github.roles = {}, {}
    assert push(planned, capsys)[0] == 0
    assert recorded(planned, merge)["claims"] == first, "labels read later are what the record avoids"
    planned.git("notes", "--ref=redline-ci", "remove", merge)
    github.fail = True
    code, out = push(planned, capsys)
    assert code == 1 and "claims: could not read the merged PR's labels: gh api: HTTP 502" in out, out
    assert planned.git("notes", "--ref=redline-ci", "show", merge) == f"result: pass\nrun: {RUN}"


def test_claims_reads_the_labels_at_the_merge_from_the_ci_note(planned, capsys, github):
    track, big, merge = land_claims(planned)
    github.pulled, github.applied = {track: [12]}, {12: {"redline:track": "alice"}}
    assert push(planned, capsys)[0] == 0
    github.pulled, github.applied, github.roles = {}, {12: {"redline:oversized": "bob"}}, {}  # all changed since
    code, out = claims(planned, capsys)
    assert code == 0, out
    assert f"## {track[:7]} add-greet/G1 (PR #12): move\nRedline-Track: the helper moved\n" \
           f"Label at the merge: redline:track, applied by @alice, admin, at {LABELLED}, head pushed at {PUSHED} (CI note on {merge[:7]})\n" in out
    assert f"## {big[:7]} add-greet/G1 (PR #12): grow\nOversized: one change\n" \
           f"Label at the merge: redline:oversized: not on PR #12 (CI note on {merge[:7]})\n" in out
    assert "Label now" not in out and "bob" not in out


def test_a_label_applied_before_the_push_is_recorded_as_it_is_and_an_old_record_prints_as_before(planned, capsys, github):
    track, big, merge = land_claims(planned)
    later = "2026-10-22T12:00:00Z"
    github.pulled, github.applied, github.heads = {track: [12]}, {12: {"redline:track": "alice"}}, {12: ("e" * 40, later)}
    assert push(planned, capsys)[0] == 0, "the record judges nothing"
    entry = recorded(planned, merge)["claims"][0]
    assert (entry["at"], entry["pushed"]) == (LABELLED, later)
    assert f"applied by @alice, admin, at {LABELLED}, head pushed at {later} (CI note on {merge[:7]})\n" in claims(planned, capsys)[1]
    github.heads = {12: None}  # no push of the head found
    planned.git("notes", "--ref=redline-ci", "remove", merge)
    assert push(planned, capsys)[0] == 0
    assert recorded(planned, merge)["claims"][0]["pushed"] is None
    assert f"at {LABELLED}, no push of the head found (CI note on" in claims(planned, capsys)[1]
    old = {k: v for k, v in recorded(planned, merge)["claims"][0].items() if k not in ("at", "pushed")}
    planned.git("notes", "--ref=redline-ci", "add", "-f", "-m",
                yaml.safe_dump({"result": "pass", "run": RUN, "claims": [old]}, sort_keys=False), merge)
    assert f"Label at the merge: redline:track, applied by @alice, admin (CI note on {merge[:7]})\n" in claims(planned, capsys)[1]


def test_claims_says_when_the_note_has_no_record_or_no_pr(planned, capsys, github):
    track, big, merge = land_claims(planned)
    assert push(planned, capsys)[0] == 0  # no merged PR found
    code, out = claims(planned, capsys)
    assert f"Oversized: one change\nLabel at the merge: no merged PR found (CI note on {merge[:7]})\n" in out, out
    note(planned, merge, "pass")  # a note written before build 6 part 11
    github.pulled = {track: [12]}
    code, out = claims(planned, capsys)
    assert code == 0, out
    assert f"Redline-Track: the helper moved\nLabel at the merge: not recorded: the CI note on {merge[:7]} " \
           "has no record of it\nLabel now: redline:track: not on PR #12\n" in out


def test_the_workflow_gives_the_push_run_a_token():
    flow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    pushing = [s for job in flow["jobs"].values() for s in job["steps"] if "redline ci push" in s.get("run", "")]
    assert pushing and pushing[0].get("env", {}).get("GH_TOKEN") == "${{ github.token }}"


def test_only_main_counts(planned, capsys, github):
    planned.git("checkout", "-q", "-b", "branch")
    planned.commit("unmerged\n\nOversized: big\nRedline-Step: add-greet/G1")
    code, out = claims(planned, capsys)
    assert code == 0, out
    assert "From main: 0 claims on 1 commit:" in out and "No claims.\n" in out and "big" not in out


def test_a_change_taken_out_of_the_plan_keeps_its_claims(planned, capsys, github):
    wave = step(planned, "add-wave/G1", "Redline-Track: waving moved")
    dropped = planned.commit("drop waving\n\nRedline-Rigor: waving is its own work",
                             {PLAN: VALID.replace("add-greet, add-wave", "add-greet")})
    code, out = claims(planned, capsys)
    assert code == 0, out
    assert out.splitlines()[1].startswith("From main: 2 claims on 3 commits: the steps of add-greet, add-wave, add-farewell,"), out
    assert f"Left the plan: add-wave in {dropped[:7]}.\n" in out
    assert f"## {wave[:7]} add-wave/G1: add-wave/G1 done\nRedline-Track: waving moved\n" in out
    planned.commit("wave again", {PLAN: VALID})
    code, out = claims(planned, capsys)
    assert code == 0 and "Left the plan" not in out and wave[:7] in out, "a change put back isn't named"


def test_a_change_taken_out_in_a_merged_pr_left_at_the_merge(planned, capsys, github):
    planned.git("checkout", "-q", "-b", "drop")
    planned.commit("hug too", {PLAN: VALID.replace("add-farewell", "add-farewell, add-hug")})
    planned.commit("drop waving\n\nRedline-Rigor: waving is its own work",
                   {PLAN: VALID.replace("add-greet, add-wave", "add-greet")})
    planned.git("checkout", "-q", "main")
    planned.git("merge", "-q", "--no-ff", "--no-edit", "drop")
    merge = planned.git("rev-parse", "HEAD")
    code, out = claims(planned, capsys)
    assert code == 0, out
    assert f"Left the plan: add-wave in {merge[:7]}.\n" in out
    assert "add-hug" not in out, "a version only inside the PR isn't read"


def test_a_deleted_plan_still_has_its_claims(planned, capsys, github):
    greet = step(planned, "add-greet/G1", "Oversized: one change")
    planned.git("rm", "-q", PLAN)
    planned.git("commit", "-q", "-m", "drop greetings\n\nRedline-Rigor: not an initiative any more")
    gone = planned.git("rev-parse", "HEAD")
    code, out = claims(planned, capsys)
    assert code == 0, out
    assert f"Left the plan: add-greet, add-wave, add-farewell in {gone[:7]}.\n" \
           f"The plan was deleted from main in {gone[:7]}.\n" in out
    assert f"## {greet[:7]} add-greet/G1: " in out
    assert f"## {gone[:7]} outside any step: drop greetings\nRedline-Rigor: not an initiative any more\n" in out


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
