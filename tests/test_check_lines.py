import pytest

from redline.cli import main
from redline.config import load_config
from redline.lines import LIMIT, check_lines

CONFIG = 'generated:\n  - "*.lock"\n  - "package-lock.json"\n  - "build/*"\n'


def lines(n: int, word: str = "line") -> str:
    return "".join(f"{word} {i}\n" for i in range(n))


@pytest.fixture
def branch(repo):
    repo.commit("base", {"README": "toy\n", "redline/config.yaml": CONFIG})
    repo.git("checkout", "-q", "-b", "work")
    return repo


def test_counts_insertions_plus_deletions_since_merge_base_with_main(branch):
    branch.commit("edit", {"README": "changed\n", "app.py": lines(10)})
    branch.git("checkout", "-q", "main")
    branch.commit("main moves on", {"other.py": lines(50)})
    branch.git("checkout", "-q", "work")
    assert check_lines(branch.path).total == 1 + 1 + 10


def test_specs_and_tests_count(branch):
    branch.commit("spec and test", {"redline/specs/toy/spec.md": lines(5), "tests/test_toy.py": lines(7)})
    assert check_lines(branch.path).total == 12


def test_generated_files_from_config_do_not_count(branch):
    branch.commit("generated", {
        "poetry.lock": lines(900),
        "web/yarn.lock": lines(900),
        "web/package-lock.json": lines(900),
        "build/out.js": lines(900),
        "app.py": lines(3),
    })
    result = check_lines(branch.path)
    assert result.total == 3
    assert sorted(result.excluded) == ["build/out.js", "poetry.lock", "web/package-lock.json", "web/yarn.lock"]


def test_a_rename_counts_only_its_edits(branch):
    branch.git("checkout", "-q", "main")
    branch.commit("big file", {"old.py": lines(500)})
    branch.git("checkout", "-q", "work")
    branch.git("merge", "-q", "main")
    branch.git("mv", "old.py", "new.py")
    branch.commit("rename", {"new.py": lines(499) + "edited\n"})
    assert check_lines(branch.path).total == 2


def test_base_ref_overrides_merge_base(branch):
    first = branch.commit("first", {"a.py": lines(10)})
    branch.commit("second", {"b.py": lines(4)})
    assert check_lines(branch.path, base=first).total == 4


def test_config_loader(branch, tmp_path):
    assert load_config(branch.path).generated == ["*.lock", "package-lock.json", "build/*"]
    assert load_config(tmp_path).generated == []
    (tmp_path / "redline").mkdir()
    (tmp_path / "redline" / "config.yaml").write_text("")
    assert load_config(tmp_path).generated == []


def test_cli_passes_at_the_limit_and_fails_above(branch, capsys):
    branch.commit("at the limit", {"app.py": lines(LIMIT), "poetry.lock": lines(900)})
    assert main(["check-lines", "--repo", str(branch.path)]) == 0
    out = capsys.readouterr().out
    assert f"ok: {LIMIT} changed lines" in out
    assert "excluded poetry.lock" in out
    branch.commit("one more", {"more.py": "x\n"})
    assert main(["check-lines", "--repo", str(branch.path)]) == 1
    assert f"FAIL: {LIMIT + 1} changed lines" in capsys.readouterr().out


def test_a_pr_that_widens_generated_still_counts_its_own_lines(branch):
    branch.commit("widen", {"big.py": lines(900), "redline/config.yaml": 'generated:\n  - "*"\n'})
    result = check_lines(branch.path)
    assert result.total > LIMIT
    assert "big.py" not in result.excluded


@pytest.mark.parametrize("text", [
    'generated: "*.lock"\n', 'support: "tests/*.py"\n', "generated:\n  - 1\n",
    "rules:\n  - Cite the store\n", "rules:\n  premise: Cite the store\n",
])
def test_a_value_that_isnt_a_list_of_strings_is_an_error(tmp_path, text):
    (tmp_path / "redline").mkdir()
    (tmp_path / "redline" / "config.yaml").write_text(text)
    with pytest.raises(RuntimeError, match="redline/config.yaml"):
        load_config(tmp_path)


def test_cli_reports_a_bad_base(branch, capsys):
    assert main(["check-lines", "--repo", str(branch.path), "--base", "no-such-ref"]) == 2
    assert "redline:" in capsys.readouterr().out
