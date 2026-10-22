import pytest

from redline.cli import main
from redline.pr import gates
from test_check_break import mutator  # noqa: F401 (a fixture)

CHANGE = "redline/changes/add-greet"
SPEC = "redline/specs/greet/spec.md"
S0 = "#### Scenario GREET.S0 [hold]: says hello\n- THEN it returns \"Hello\"\n"
S0_LOUD = "#### Scenario GREET.S0 [new]: says hello loudly\n- THEN it returns \"HELLO\"\n"
S1 = "#### Scenario GREET.S1 [new]: greets by name\n- THEN it returns \"Hello, Ada!\"\n"
S3 = "#### Scenario GREET.S3 [hold]: waves\n- THEN it waves\n"
S4 = "#### Scenario GREET.S4 [hold]: bows\n- THEN it bows\n"
DELTA = (f"## ADDED Requirements\n\n### Requirement: Greeting\n\n{S1}\n"
         f"## MODIFIED Requirements\n\n### Requirement: Greeting\n\n{S0_LOUD}\n"
         "## REMOVED Requirements\n- GREET.S3: nobody waves any more\n\n"
         "### Premises\n- P1: a placeholder exists — `greet.py:1`\n")


def living(*scenarios: str, requirement: str = "Greeting", prose: str = "") -> str:
    return f"# Greet\n\n### Requirement: {requirement}\n\n{prose}" + "\n".join(scenarios)


MERGED = living(S0_LOUD, S1, S4)


def on_c_branch(repo, delta: str = DELTA) -> None:
    repo.commit("add-greet spec", {SPEC: living(S0, S3, S4), f"{CHANGE}/specs/greet/delta.md": delta})
    repo.git("checkout", "-q", "-b", "close")


def specs(repo, capsys) -> tuple[int, list[str]]:
    code = main(["check-specs", "add-greet", "--repo", str(repo.path)])
    return code, capsys.readouterr().out.splitlines()


def test_a_delta_merged_as_it_says_passes(repo, capsys):
    on_c_branch(repo)
    repo.commit("merge the delta", {SPEC: MERGED})
    assert specs(repo, capsys) == (0, ["ok: 1 added, 1 modified, 1 removed, as the deltas say; nothing else in redline/specs changed"])


M1 = "#### Scenario GREET.M1 [manual]: looks right\nManual: by eye\n- THEN it looks right\n"


def test_a_manual_scenario_reaches_the_living_spec_with_its_reason(repo, capsys):
    on_c_branch(repo, DELTA.replace(f"{S1}\n", f"{S1}\n{M1}\n"))
    repo.commit("merge the delta", {SPEC: living(S0_LOUD, S1, M1.replace("Manual: by eye\n", ""), S4)})
    assert specs(repo, capsys) == (1, [f"GREET.M1: {SPEC} has it with text other than the delta's"])
    repo.commit("with its reason", {SPEC: living(S0_LOUD, S1, M1, S4)})
    assert specs(repo, capsys) == (0, ["ok: 2 added, 1 modified, 1 removed, as the deltas say; nothing else in redline/specs changed"])


def test_a_delta_not_merged_names_each_scenario(repo, capsys):
    on_c_branch(repo)
    assert specs(repo, capsys) == (1, [
        f"GREET.S1: ADDED, but {SPEC} doesn't have it",
        f"GREET.S0: {SPEC} has it with text other than the delta's",
        f"GREET.S3: REMOVED, but {SPEC} still has it",
    ])


def test_a_scenario_merged_under_another_requirement_or_with_other_text_fails(repo, capsys):
    on_c_branch(repo)
    other = living(S0_LOUD.replace("HELLO", "HELLO!"), S4) + "\n### Requirement: Names\n\n" + S1
    repo.commit("merge the delta wrongly", {SPEC: other})
    assert specs(repo, capsys) == (1, [
        f"GREET.S1: {SPEC} has it under Requirement: Names, not Greeting",
        f"GREET.S0: {SPEC} has it with text other than the delta's",
    ])


def test_each_section_must_match_the_living_spec_at_the_merge_base(repo, capsys):
    delta = (f"## ADDED Requirements\n\n### Requirement: Greeting\n\n{S0}\n"
             f"## MODIFIED Requirements\n\n### Requirement: Greeting\n\n{S1}\n"
             "## REMOVED Requirements\n- GREET.S8: never was\n")
    on_c_branch(repo, delta)
    repo.commit("merge the delta", {SPEC: living(S0, S1, S3, S4)})
    assert specs(repo, capsys) == (1, [
        f"GREET.S0: ADDED, but {SPEC} already had it at the merge-base",
        f"GREET.S1: MODIFIED, but {SPEC} didn't have it at the merge-base",
        f"GREET.S8: REMOVED, but {SPEC} didn't have it at the merge-base",
    ])


def test_a_scenario_heading_must_sit_in_added_or_modified(repo, capsys):
    delta = f"### Requirement: Greeting\n\n{S1}\n## REMOVED Requirements\n\n{S3}"
    on_c_branch(repo, delta)
    repo.commit("merge the delta", {SPEC: living(S0, S1, S4)})
    path = f"{CHANGE}/specs/greet/delta.md"
    assert specs(repo, capsys) == (1, [
        f"{path}:3: GREET.S1 is in no ADDED or MODIFIED section",
        f"{path}:8: GREET.S3 is a heading under REMOVED; a removed scenario is an `- <ID>: <reason>` line",
    ])


def test_a_change_to_specs_the_deltas_dont_name_fails(repo, capsys):
    on_c_branch(repo)
    wave = "redline/specs/wave/spec.md"
    repo.commit("merge the delta and more", {
        SPEC: living(S0_LOUD, S1),
        wave: living("#### Scenario WAVE.S1 [new]: waves back\n- THEN it waves\n", requirement="Wave"),
    })
    assert specs(repo, capsys) == (1, [
        f"GREET.S4: removed from {SPEC} since the merge-base, but no delta of add-greet names it",
        f"WAVE.S1: added to {wave} since the merge-base, but no delta of add-greet names it",
    ])
    repo.commit("bow low", {SPEC: living(S0_LOUD, S1, S4.replace("bows", "bows low"))})
    assert specs(repo, capsys)[1] == [
        f"GREET.S4: changed in {SPEC} since the merge-base, but no delta of add-greet names it",
        f"WAVE.S1: added to {wave} since the merge-base, but no delta of add-greet names it",
    ]


UNTOUCHED = "changed since the merge-base with main; only the C step writes redline/specs/, from its delta"


def specs_gate(repo, step: str) -> list[str]:
    return [f for f in gates(repo.path, "add-greet", step) if f.startswith("check-specs")]


def test_at_c_it_compares_the_living_specs_with_the_delta(repo, capsys):
    on_c_branch(repo)
    assert f"check-specs: GREET.S1: ADDED, but {SPEC} doesn't have it" in gates(repo.path, "add-greet", "C")
    repo.commit("merge the delta", {SPEC: MERGED})
    assert specs_gate(repo, "C") == []


@pytest.mark.parametrize("step", ["S", "R", "G1", "G2"])
def test_before_c_a_step_leaves_the_living_specs_as_they_are(repo, mutator, step):
    on_c_branch(repo)
    assert specs_gate(repo, step) == []
    repo.commit("merge the delta early", {SPEC: MERGED})
    assert specs_gate(repo, step) == [f"check-specs: {SPEC} {UNTOUCHED}"]


def test_before_c_a_spec_moved_or_added_names_each_file(repo, mutator):
    on_c_branch(repo)
    (repo.path / "redline/specs/hello").mkdir()
    repo.git("mv", SPEC, "redline/specs/hello/spec.md")
    repo.commit("move it and add a note", {"redline/specs/README.md": "Living specs.\n"})
    assert specs_gate(repo, "G1") == [f"check-specs: {path} {UNTOUCHED}" for path in
                                      ("redline/specs/README.md", SPEC, "redline/specs/hello/spec.md")]


POLITE = "Greetings are polite.\n\n"
WAVE = "redline/specs/wave/spec.md"
W1 = "#### Scenario WAVE.S1 [hold]: waves back\n- THEN it waves\n"


def ok(added: int, modified: int, removed: int) -> list[str]:
    return [f"ok: {added} added, {modified} modified, {removed} removed, as the deltas say; "
            "nothing else in redline/specs changed"]


def test_prose_a_delta_gives_reaches_the_living_spec(repo, capsys):
    on_c_branch(repo, DELTA.replace(f"Greeting\n\n{S0_LOUD}", f"Greeting\n\n{POLITE}{S0_LOUD}"))
    repo.commit("merge the delta", {SPEC: MERGED})
    assert specs(repo, capsys) == (1, [f"Requirement: Greeting in {SPEC}: prose other than the delta's"])
    repo.commit("with its prose", {SPEC: living(S0_LOUD, S1, S4, prose=POLITE)})
    assert specs(repo, capsys) == (0, ok(1, 1, 1))


def test_a_modified_requirement_may_reword_its_prose_alone(repo, capsys):
    on_c_branch(repo, f"## MODIFIED Requirements\n\n### Requirement: Greeting\n\n{POLITE}")
    repo.commit("reword", {SPEC: living(S0, S3, S4, prose="Greetings were rude.\n\n")})
    assert specs(repo, capsys) == (1, [f"Requirement: Greeting in {SPEC}: prose other than the delta's"])
    repo.commit("reword as the delta says", {SPEC: living(S0, S3, S4, prose=POLITE)})
    assert specs(repo, capsys) == (0, ok(0, 0, 0))


def test_two_blocks_giving_one_requirement_different_prose_fail(repo, capsys):
    delta = DELTA.replace(S1, f"{POLITE}{S1}").replace(f"Greeting\n\n{S0_LOUD}", f"Greeting\n\nRude.\n\n{S0_LOUD}")
    second = [n for n, line in enumerate(delta.splitlines(), 1) if line == "### Requirement: Greeting"][1]
    on_c_branch(repo, delta)
    repo.commit("merge the delta", {SPEC: living(S0_LOUD, S1, S4, prose=POLITE)})
    assert specs(repo, capsys) == (1, [f"{CHANGE}/specs/greet/delta.md:{second}: Requirement: Greeting "
                                       "gives prose other than another block of add-greet gives it"])


def test_prose_no_delta_gives_fails(repo, capsys):
    on_c_branch(repo)
    repo.commit("reword it too", {SPEC: living(S0_LOUD, S1, S4, prose="Greetings are rude.\n\n")})
    changed = "prose changed since the merge-base, but no delta of add-greet gives prose under it"
    assert specs(repo, capsys) == (1, [f"Requirement: Greeting in {SPEC}: {changed}"])
    repo.commit("and a requirement", {SPEC: MERGED + "\n### Requirement: Names\n\nNames are spelled out.\n"})
    assert specs(repo, capsys) == (1, [
        f"Requirement: Names in {SPEC}: {changed}",
        f"Requirement: Names in {SPEC}: no scenario under it; remove it, heading and prose",
    ])


def test_a_requirement_left_with_no_scenario_must_go(repo, capsys):
    waving = f"### Requirement: Waving\n\nIt waves.\n\n{S3}"
    base = living(S0, S4) + f"\n{waving}\n### Requirement: Someday\n\nNot yet.\n"
    repo.commit("spec", {SPEC: base, f"{CHANGE}/specs/greet/delta.md": "## REMOVED Requirements\n- GREET.S3: gone\n"})
    repo.git("checkout", "-q", "-b", "close")
    repo.commit("remove GREET.S3", {SPEC: base.replace(S3, "")})
    assert specs(repo, capsys) == (1, [f"Requirement: Waving in {SPEC}: no scenario under it; remove it, heading and prose"])
    repo.commit("and its requirement", {SPEC: base.replace(waving, "")})
    assert specs(repo, capsys) == (0, ok(0, 0, 1))


def test_a_spec_file_left_with_no_scenario_is_deleted(repo, capsys):
    repo.commit("spec", {SPEC: living(S0), WAVE: f"# Wave\n\n### Requirement: Wave\n\n{W1}",
                         f"{CHANGE}/specs/wave/delta.md": "## REMOVED Requirements\n- WAVE.S1: gone\n"})
    repo.git("checkout", "-q", "-b", "close")
    repo.commit("remove WAVE.S1", {WAVE: "# Wave\n"})
    assert specs(repo, capsys) == (1, [f"{WAVE}: no scenario left; delete it"])
    (repo.path / WAVE).unlink()
    repo.commit("delete it")
    assert specs(repo, capsys) == (0, ok(0, 0, 1))


def test_text_under_no_requirement_changes_only_in_a_file_c_creates_or_deletes(repo, capsys):
    on_c_branch(repo)
    unnamed = f"{SPEC}: text under no requirement changed since the merge-base; only a spec file C creates or deletes may change it"
    repo.commit("merge, with a preamble", {SPEC: MERGED.replace("# Greet\n", "# Greet\n\nEvery greeting is polite.\n")})
    assert specs(repo, capsys) == (1, [unnamed])
    repo.commit("merge, with notes", {SPEC: MERGED + "\n## Notes\n\nGreet twice.\n"})
    assert specs(repo, capsys) == (1, [unnamed])
    repo.commit("merge, with a new domain", {
        SPEC: MERGED, WAVE: f"# Wave\n\nIt waves back.\n\n### Requirement: Wave\n\n{W1}",
        f"{CHANGE}/specs/wave/delta.md": f"## ADDED Requirements\n\n### Requirement: Wave\n\n{W1}",
    })
    assert specs(repo, capsys) == (0, ok(2, 1, 1))
