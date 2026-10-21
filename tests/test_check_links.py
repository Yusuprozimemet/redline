import pytest

from redline.cli import main
from redline.links import check_links

SPEC = "redline/specs/toy/spec.md"
DELTA = "redline/changes/add-bye/specs/toy/delta.md"


def scenarios(*ids: str, tag: str = "new") -> str:
    return "# Toy\n\n" + "".join(f"#### Scenario {i} [{tag}]: does a thing\n- GIVEN x\n\n" for i in ids)


def marked(*ids: str) -> str:
    return "import pytest\n\n" + "".join(
        f'@pytest.mark.spec("{i}")\ndef test_{n}():\n    pass\n\n' for n, i in enumerate(ids)
    )


def run(repo, capsys) -> tuple[int, list[str]]:
    code = main(["check-links", "--repo", str(repo.path)])
    return code, capsys.readouterr().out.splitlines()


def test_every_scenario_linked_both_ways_passes(repo, capsys):
    repo.commit("linked", {
        SPEC: scenarios("TOY.S1", "TOY.S2", tag="hold"),
        DELTA: scenarios("TOY.S3"),
        "tests/test_toy.py": marked("TOY.S1", "TOY.S2") + 'import pytest\n\n@pytest.mark.spec("TOY.S3", new=True)\ndef test_x():\n    pass\n',
    })
    assert check_links(repo.path).gaps == []
    code, out = run(repo, capsys)
    assert code == 0
    assert out == ["ok: 3 scenarios, each linked to a test"]


def test_scenario_without_a_test_is_a_gap(repo, capsys):
    repo.commit("unlinked", {SPEC: scenarios("TOY.S1", "TOY.S2"), "tests/test_toy.py": marked("TOY.S1")})
    code, out = run(repo, capsys)
    assert code == 1
    assert out == [f"unlinked scenario TOY.S2 ({SPEC}:6): no test has a spec marker for it"]


def test_scenario_in_a_change_delta_without_a_test_is_a_gap(repo, capsys):
    repo.commit("unlinked delta", {DELTA: scenarios("TOY.S9")})
    code, out = run(repo, capsys)
    assert code == 1
    assert out == [f"unlinked scenario TOY.S9 ({DELTA}:3): no test has a spec marker for it"]


def test_marker_naming_an_undeclared_scenario_is_a_gap(repo, capsys):
    repo.commit("unknown", {SPEC: scenarios("TOY.S1"), "tests/test_toy.py": marked("TOY.S1", "TOY.TYPO")})
    code, out = run(repo, capsys)
    assert code == 1
    assert out == ["unknown scenario TOY.TYPO (tests/test_toy.py:7): no spec declares it"]


def test_each_gap_is_reported_on_its_own_line(repo, capsys):
    repo.commit("gaps", {SPEC: scenarios("TOY.S1", "TOY.S2"), "tests/test_toy.py": marked("TOY.X", "TOY.Y")})
    code, out = run(repo, capsys)
    assert code == 1
    assert len(out) == 4
    assert sorted(line.split()[0] for line in out) == ["unknown", "unknown", "unlinked", "unlinked"]


def test_duplicate_id_in_the_living_specs_is_an_error(repo, capsys):
    other = "redline/specs/other/spec.md"
    repo.commit("dup", {SPEC: scenarios("TOY.S1"), other: scenarios("TOY.S1"), "tests/test_toy.py": marked("TOY.S1")})
    code, out = run(repo, capsys)
    assert code == 1
    assert out == [f"duplicate scenario TOY.S1: {other}:3, {SPEC}:3"]


def test_duplicate_id_within_one_spec_file_is_an_error(repo, capsys):
    repo.commit("dup", {SPEC: scenarios("TOY.S1", "TOY.S1"), "tests/test_toy.py": marked("TOY.S1")})
    code, out = run(repo, capsys)
    assert code == 1
    assert out == [f"duplicate scenario TOY.S1: {SPEC}:3, {SPEC}:6"]


def test_duplicate_id_across_two_changes_is_an_error(repo, capsys):
    other = "redline/changes/add-hi/specs/toy/delta.md"
    repo.commit("dup", {DELTA: scenarios("TOY.S5"), other: scenarios("TOY.S5"), "tests/test_toy.py": marked("TOY.S5")})
    code, out = run(repo, capsys)
    assert code == 1
    assert out == [f"duplicate scenario TOY.S5: {DELTA}:3, {other}:3"]


def test_a_change_may_restate_a_living_scenario(repo, capsys):
    # A MODIFIED scenario in a delta carries the ID it already has in specs/.
    repo.commit("modified", {SPEC: scenarios("TOY.S1"), DELTA: scenarios("TOY.S1", tag="hold"), "tests/test_toy.py": marked("TOY.S1")})
    assert run(repo, capsys) == (0, ["ok: 1 scenarios, each linked to a test"])


@pytest.mark.parametrize("line", [
    "### Scenario TOY.S2 [new]: wrong level",
    "  #### Scenario TOY.S2 [new]: indented",
])
def test_only_well_formed_headings_declare_scenarios(repo, capsys, line):
    repo.commit("headings", {SPEC: scenarios("TOY.S1") + line + "\n", "tests/test_toy.py": marked("TOY.S1")})
    assert run(repo, capsys)[0] == 0


FORM = "not a scenario heading `#### Scenario <ID> [new|hold]: <title>`"


@pytest.mark.parametrize("line", [
    "#### Scenario TOY.S2: no tag",
    "#### Scenario TOY.S2 [manual]: unknown tag",
    "#### Scenario TOY.S2 [New]: capital",
    "#### Scenario TOY.S2 [new] no colon",
    "#### Scenario: TOY.S2",
])
@pytest.mark.parametrize("path", [SPEC, DELTA])
def test_a_malformed_scenario_heading_is_a_gap(repo, capsys, line, path):
    repo.commit("headings", {path: scenarios("TOY.S1") + line + "\n", "tests/test_toy.py": marked("TOY.S1")})
    code, out = run(repo, capsys)
    assert code == 1
    assert out == [f"{FORM} ({path}:6): {line}"]  # TOY.S1 still counts and is linked


def test_a_closed_changes_malformed_heading_isnt_read(repo, capsys):
    repo.commit("closed\n\nRedline-Step: add-bye/C", {
        SPEC: scenarios("TOY.S1"), DELTA: "#### Scenario TOY.S2 [manual]: looks right\n",
        "tests/test_toy.py": marked("TOY.S1")})
    assert run(repo, capsys)[0] == 0


def test_specs_outside_the_spec_paths_are_ignored(repo, capsys):
    repo.commit("elsewhere", {
        "docs/spec.md": scenarios("DOC.S1"),
        "redline/changes/add-bye/proposal.md": scenarios("DOC.S2"),
        "redline/specs/toy/notes.md": scenarios("DOC.S3"),
    })
    assert run(repo, capsys) == (0, ["ok: 0 scenarios, each linked to a test"])


def test_untracked_files_count_and_markers_with_options_link(repo, capsys):
    repo.commit("empty")
    (repo.path / "redline/specs/toy").mkdir(parents=True)
    (repo.path / SPEC).write_text(scenarios("TOY.S1", "TOY.S2"))
    (repo.path / "test_toy.py").write_text(
        "import pytest\n\n@pytest.mark.spec( 'TOY.S1' )\ndef test_a():\n    pass\n\n"
        '@pytest.mark.spec("TOY.S2", new=False)\ndef test_b():\n    pass\n'
    )
    assert run(repo, capsys) == (0, ["ok: 2 scenarios, each linked to a test"])


@pytest.mark.parametrize("text", [
    'import pytest\n\n# @pytest.mark.spec("TOY.S1")\ndef test_it():\n    pass\n',
    'TOY = """\n@pytest.mark.spec("TOY.S1")\ndef test_it():\n    pass\n"""\n',
], ids=["commented", "quoted"])
def test_a_marker_in_a_comment_or_a_string_links_nothing(repo, capsys, text):
    repo.commit("unlinked", {SPEC: scenarios("TOY.S1"), "tests/test_toy.py": text})
    code, out = run(repo, capsys)
    assert code == 1
    assert out == [f"unlinked scenario TOY.S1 ({SPEC}:3): no test has a spec marker for it"]


def test_a_test_file_that_doesnt_parse_is_a_gap(repo, capsys):
    repo.commit("broken", {SPEC: scenarios("TOY.S1"), "tests/test_toy.py": marked("TOY.S1") + "def (:\n"})
    code, out = run(repo, capsys)
    assert code == 1
    assert out[0].startswith("unreadable test file tests/test_toy.py: invalid syntax")
    assert f"unlinked scenario TOY.S1 ({SPEC}:3): no test has a spec marker for it" in out
