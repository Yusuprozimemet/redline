from redline.cli import main
from redline.pr import gates

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


def living(*scenarios: str, requirement: str = "Greeting") -> str:
    return f"# Greet\n\n### Requirement: {requirement}\n\n" + "\n".join(scenarios)


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


def test_pr_runs_it_at_the_c_step_only(repo, capsys):
    on_c_branch(repo)
    assert f"check-specs: GREET.S1: ADDED, but {SPEC} doesn't have it" in gates(repo.path, "add-greet", "C")
    assert not [f for f in gates(repo.path, "add-greet", "G1") if f.startswith("check-specs")]
