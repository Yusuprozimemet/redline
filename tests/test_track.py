import pytest

from redline.approval import Approvals
from redline.pr import gates
from test_ci import ci
from test_outside import OUTSIDE, outside
from test_pr import FakeGitHub, github  # noqa: F401 (github is a fixture)
from test_start import CHANGE, STEPS, change, fresh_branch, merge_step, start  # noqa: F401 (change is a fixture)

TRACKED = STEPS.replace("Owns: GREET.S1\n", "Owns: GREET.S1\nTrack: greet.py, lib/*.py\n", 1)
OUTSIDE_G1 = "check-track: web/app.py is outside add-greet/G1's track (greet.py, lib/*.py)"
NO_TRACK = "check-track: add-greet/G2 has no Track: line; at critical every G step names its track"
RIGOR = "rigor: `rigor:` in redline/config.yaml changed from standard to lite"


@pytest.fixture
def tracked(change):
    change.commit("tracks", {
        f"{CHANGE}/steps.md": TRACKED,
        f"{CHANGE}/proposal.md": "# Proposal\n\nRigor: critical\n",
        "redline/config.yaml": 'generated:\n  - "*.lock"\n',
    })
    merge_step(change, "S")
    merge_step(change, "R")
    fresh_branch(change, "g1")
    return change


def track(repo, step: str = "G1", approvals: Approvals | None = None) -> list[str]:
    return [f for f in gates(repo.path, "add-greet", step, approvals) if f.startswith("check-track")]


def test_a_green_pr_may_change_its_track_tests_redline_files_and_generated_files(tracked):
    tracked.commit("code", {
        "greet.py": "def greet(name):\n    return f'Hello, {name}!'\n",
        "lib/names.py": "NAMES = []\n",
        "tests/test_greet.py": "def test_x():\n    pass\n",
        "conftest.py": "",
        f"{CHANGE}/ledger.yaml": "change: add-greet\n",
        "poetry.lock": "x\n",
    })
    assert track(tracked) == []


def test_a_file_outside_the_track_fails_even_if_the_pr_widens_its_track(tracked):
    tracked.commit("code", {"greet.py": "x = 1\n", "web/app.py": "app = None\n"})
    assert track(tracked) == [OUTSIDE_G1]
    tracked.commit("widen", {f"{CHANGE}/steps.md": TRACKED.replace("lib/*.py", "lib/*.py, web/*.py")})
    assert track(tracked) == [OUTSIDE_G1]  # the track is main's, as the auditor saw it


def test_deleting_a_file_outside_the_track_is_changing_it(tracked):
    tracked.git("checkout", "-q", "main")
    tracked.commit("a web app", {"web/app.py": "app = None\n"})
    fresh_branch(tracked, "g1b")
    tracked.git("rm", "-q", "web/app.py")
    tracked.commit("delete")
    assert track(tracked) == [OUTSIDE_G1]


def test_a_file_outside_the_track_needs_a_redline_track_trailer_and_its_label(tracked):
    tracked.commit("code", {"web/app.py": "app = None\n"})
    tracked.commit("why\n\nRedline-Track: the app wires the greeting in")
    local = Approvals()
    assert track(tracked, approvals=local) == []
    assert local.pending == [f"{OUTSIDE_G1}: CI will need the `redline:track` label from a maintainer"]
    fake = FakeGitHub(tracked, roles={"maintainer": "admin"})
    assert track(tracked, approvals=Approvals(fake, 1)) == [f"{OUTSIDE_G1}: needs the `redline:track` label from a maintainer"]
    fake.applied["redline:track"] = "maintainer"
    assert track(tracked, approvals=Approvals(fake, 1)) == []


def test_at_critical_every_green_step_names_its_track_and_below_it_is_optional(tracked):
    tracked.commit("code", {"greet.py": "x = 1\n"})
    assert track(tracked, "G2") == [NO_TRACK]
    tracked.git("checkout", "-q", "main")
    tracked.commit("standard", {f"{CHANGE}/proposal.md": "# Proposal\n\nRigor: standard\n"})
    fresh_branch(tracked, "g2")
    tracked.commit("code", {"web/app.py": "app = None\n"})
    assert track(tracked, "G2") == []
    assert track(tracked) == [OUTSIDE_G1]  # a track that is there is checked at any level


def test_the_brief_of_a_green_step_prints_its_track(tracked, capsys):
    code, out = start(tracked, capsys, "add-greet/G1")
    assert code == 0, out
    assert "## Track\ngreet.py, lib/*.py\n" in out


def test_changing_the_default_rigor_needs_a_redline_rigor_trailer_and_its_label(change, capsys, github):
    outside(change, {"redline/config.yaml": "rigor: lite\n"})
    code, out = ci(change, capsys, "pr", "--base", "main", "--pr", "1")
    assert code == 1
    assert f"{RIGOR}, with no Redline-Rigor trailer" in out
    change.commit("why\n\nRedline-Rigor: this repository holds no auth or payments code")
    code, out = ci(change, capsys, "pr", "--base", "main", "--pr", "1")
    assert code == 1
    assert f"{RIGOR}: needs the `redline:rigor` label from a maintainer" in out
    github.applied["redline:rigor"] = "maintainer"
    code, out = ci(change, capsys, "pr", "--base", "main", "--pr", "1")
    assert code == 0, out
    assert OUTSIDE in out


def test_a_step_that_changes_the_default_rigor_needs_the_claim_too(tracked):
    tracked.commit("lower", {"redline/config.yaml": "rigor: lite\n"})
    assert f"{RIGOR}, with no Redline-Rigor trailer" in gates(tracked.path, "add-greet", "G1")
