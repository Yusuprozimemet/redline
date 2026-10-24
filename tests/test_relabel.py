import re
from pathlib import Path

import pytest
import yaml

from redline import approval, claims
from redline.approval import Approvals
from redline.defects import CAUSES
from redline.pr import gates
from test_defects import LOG, VALID, run
from test_pr import FakeGitHub
from test_start import CHANGE, change  # noqa: F401 (change is a fixture)

RELABEL = f"{CHANGE}/relabel.yaml"
AGENT = Path(__file__).parent.parent / ".claude/agents/redline-relabeller.md"
FIRST = {"D1": "premise", "D2": "test", "D3": "premise"}


def labels(**causes: str) -> str:
    entries = {d: {"cause": c, "note": f"the text of {d} says so."} for d, c in {**FIRST, **causes}.items() if c}
    return "# Relabel: add-greet\n# Model: claude-fable-5-1\n" + yaml.safe_dump(entries)


@pytest.fixture
def logged(change):
    change.commit("log", {LOG: VALID})
    return change


def check(repo, capsys) -> tuple[int, str]:
    return run(repo, capsys, "check-relabel", "add-greet")


def test_blind_prints_the_log_without_its_causes_or_decisions(logged, capsys):
    logged.commit("decided", {LOG: VALID.replace("Cause: test\n", "Cause: test\nDecided: kept\n")})
    code, out = run(logged, capsys, "blind", "add-greet")
    assert code == 0, out
    assert out == "".join(line + "\n" for line in VALID.splitlines() if not line.startswith("Cause:"))
    logged.commit("broken", {LOG: VALID.replace("Cause: test\n", "")})
    code, out = run(logged, capsys, "blind", "add-greet")
    assert code == 1
    assert out.startswith("refused: the defect log is not well formed")


def test_labels_that_agree_pass(logged, capsys):
    logged.commit("relabel", {RELABEL: labels()})
    assert check(logged, capsys) == (0, "ok: 3 defects relabelled blind, 0 disagreements\n")


def test_a_disagreement_is_printed_and_needs_a_decided_line(logged, capsys):
    logged.commit("relabel", {RELABEL: labels(D2="spec", D3="unclear")})
    code, out = check(logged, capsys)
    assert code == 1
    assert out.splitlines() == [
        "disagree D2: Cause: test, relabelled spec: the text of D2 says so.",
        "disagree D3: Cause: premise, relabelled unclear: the text of D3 says so.",
        "D2: Cause: test and the relabel's spec disagree, with no Decided: line",
        "D3: Cause: premise and the relabel's unclear disagree, with no Decided: line",
    ]
    logged.commit("decide", {LOG: VALID.replace("Cause: test\n", "Cause: test\nDecided: the test passed before code\n")
                             .replace("Found-by: add-greet/G2\n", "Found-by: add-greet/G2\nDecided: P2 was the claim\n")})
    code, out = check(logged, capsys)
    assert code == 0, out
    assert "ok: 3 defects relabelled blind, 2 disagreements" in out


@pytest.mark.parametrize("causes, why", [
    ({"D3": None}, "D3: no label in relabel.yaml; run the relabeller again"),
    ({"D9": "code"}, "D9: labelled, but the log has no D9"),
    ({"D1": "typo"}, "D1: `typo` is not a cause or unclear"),
])
def test_every_defect_has_exactly_one_known_label(logged, capsys, causes, why):
    logged.commit("relabel", {RELABEL: labels(**causes)})
    code, out = check(logged, capsys)
    assert code == 1
    assert why in out.splitlines()


def test_a_label_needs_a_note(logged, capsys):
    logged.commit("relabel", {RELABEL: labels().replace("  note: the text of D1 says so.\n", "")})
    assert "D1: no note" in check(logged, capsys)[1].splitlines()


@pytest.mark.parametrize("together", [False, True])
def test_a_cause_changed_after_the_relabel_needs_a_decided_line(logged, capsys, together):
    changed = VALID.replace("Cause: test", "Cause: spec")
    if together:  # in the same commit as the relabel, the first label is still the parent's
        logged.commit("relabel", {RELABEL: labels(D2="spec"), LOG: changed})
    else:
        logged.commit("relabel", {RELABEL: labels()})
        logged.commit("relabel", {LOG: changed})
    code, out = check(logged, capsys)
    assert code == 1
    assert "D2: Cause: changed from test to spec after the relabel, with no Decided: line" in out.splitlines()
    logged.commit("decide", {LOG: changed.replace("Cause: spec\n", "Cause: spec\nDecided: GREET.S2 said too little\n")})
    assert check(logged, capsys)[0] == 0


def test_the_relabel_is_required_at_the_close_of_a_critical_change(logged):
    def relabel(step: str) -> list[str]:
        return [f for f in gates(logged.path, "add-greet", step) if f.startswith("check-relabel")]
    assert relabel("C") == []  # standard
    logged.commit("critical", {f"{CHANGE}/proposal.md": "# Proposal\n\nRigor: critical\n"})
    assert relabel("C") == [f"check-relabel: {RELABEL}: missing; at C a critical change has its defects relabelled blind"]
    assert relabel("G1") == []
    logged.commit("relabel", {RELABEL: labels(D2="spec")})
    assert relabel("G1") == ["check-relabel: D2: Cause: test and the relabel's spec disagree, with no Decided: line"]


def test_the_relabeller_is_read_only_on_the_strongest_model_and_returns_a_relabel_file():
    _, front, body = AGENT.read_text(encoding="utf-8").split("---\n", 2)
    front = yaml.safe_load(front)
    assert front["name"] == "redline-relabeller"
    assert {t.strip() for t in front["tools"].split(",")} == {"Read"}
    assert (front["model"], front["effort"]) == ("fable", "max")
    assert "REFUSED: the relabeller runs only on a Claude Fable or Opus model" in body
    shown = re.search(r"```yaml\n(# Relabel: .+?)```", body, re.S)[1]
    assert shown.splitlines()[1].startswith("# Model: "), "the example names its model before the first entry"
    example = yaml.safe_load(shown)
    assert all(e["cause"] in (*CAUSES, "unclear") and e["note"] for e in example.values())


@pytest.mark.parametrize(("model", "why"), [
    (None, f"{RELABEL}: no `# Model:` line; the relabeller names the model it ran on in a `# Model:` line before the first entry"),
    ("claude-sonnet-5-5", f"{RELABEL}:2: # Model: claude-sonnet-5-5 is neither a Fable nor an Opus model; "
                          "run the relabeller on Fable, or on Opus at max effort"),
    ("claude-opus-5-5", None),
], ids=["none", "sonnet", "opus"])
def test_a_relabel_names_a_fable_or_opus_model(logged, capsys, model, why):
    named = labels().replace("# Model: claude-fable-5-1\n", f"# Model: {model}\n" if model else "")
    logged.commit("relabel", {RELABEL: named})
    assert check(logged, capsys) == ((1, why + "\n") if why else (0, "ok: 3 defects relabelled blind, 0 disagreements\n"))


def test_a_model_line_after_the_first_entry_names_nothing(logged, capsys):
    late = labels().replace("# Model: claude-fable-5-1\n", "") + "# Model: claude-fable-5-1\n"
    logged.commit("relabel", {RELABEL: late})
    assert check(logged, capsys)[1].startswith(f"{RELABEL}: no `# Model:` line;")


WAIVER = "Redline-Relabel: waived-by @alice: the maintainer chose to skip the relabel"
WAIVED = f"{RELABEL}: waived by @alice"


def critical(logged, *trailers: str):
    logged.commit("critical", {f"{CHANGE}/proposal.md": "# Proposal\n\nRigor: critical\n"})
    if trailers:
        logged.git("checkout", "-q", "-b", "close")  # the C step's branch: its own commits are main..HEAD
        logged.commit("waived\n\n" + "\n".join(trailers))


def relabelling(logged, step: str = "C", approvals=None) -> list[str]:
    return [f for f in gates(logged.path, "add-greet", step, approvals) if f.startswith("check-relabel")]


def test_a_maintainers_waiver_stands_in_for_a_missing_relabel_at_c(logged, capsys):
    critical(logged, WAIVER)
    local = Approvals()
    assert relabelling(logged, approvals=local) == []
    assert local.pending == [f"{WAIVED}: CI will need the `redline:relabel` label applied by @alice, a maintainer"]
    assert check(logged, capsys) == (0, f"note: {WAIVED}: CI will need the `redline:relabel` label applied by "
                                             f"@alice, a maintainer\nok: {WAIVED}, no defect relabelled blind\n")

    def closing(applied: dict) -> list[str]:
        github = FakeGitHub(logged, applied=applied, roles={"maintainer": "admin", "alice": "admin"})
        return relabelling(logged, approvals=Approvals(github, 1))

    assert closing({}) == [f"check-relabel: {WAIVED}: needs the `redline:relabel` label from a maintainer"]
    assert closing({"redline:relabel": "bob"}) == [
        f"check-relabel: {WAIVED}: `redline:relabel` was applied by @bob, who isn't a maintainer"]
    assert closing({"redline:relabel": "maintainer"}) == [
        f"check-relabel: {WAIVED}: `redline:relabel` was applied by @maintainer, but the trailer names @alice: "
        "only @alice's label approves it"]
    assert closing({"redline:relabel": "alice"}) == []


@pytest.mark.parametrize("trailer, why", [
    ("Redline-Relabel: skipped", "allows nothing: it needs `waived-by @person: <reason>`"),
    ("Redline-Relabel: waived-by alice: skipped", "allows nothing: it needs `waived-by @person: <reason>`"),
    ("Redline-Relabel: waived-by @alice:", "allows nothing: it needs `waived-by @person: <reason>`"),
])
def test_a_waiver_that_allows_nothing_fails(logged, trailer, why):
    critical(logged, trailer)
    assert relabelling(logged) == [
        f"check-relabel: {trailer}: {why}",
        f"check-relabel: {RELABEL}: missing; at C a critical change has its defects relabelled blind"]


def test_a_waiver_waives_nothing_beside_a_relabel_below_critical_or_before_c(logged):
    logged.git("checkout", "-q", "-b", "close")
    logged.commit("waived\n\n" + WAIVER)
    assert relabelling(logged) == [f"check-relabel: {WAIVER}: waives nothing: add-greet isn't critical"]
    critical(logged)
    assert relabelling(logged, "G1") == [f"check-relabel: {WAIVER}: a relabel waiver counts at the C step only"]
    logged.commit("relabel", {RELABEL: labels()})
    assert relabelling(logged) == [f"check-relabel: {WAIVER}: waives nothing: {RELABEL} is there"]


def test_the_claims_record_reads_a_waiver_and_the_person_it_names():
    assert claims.LABELS["Redline-Relabel"] == approval.RELABEL == "redline:relabel"
    assert approval.named("Redline-Relabel", WAIVER.split(": ", 1)[1]) == "alice"
