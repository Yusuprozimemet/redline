from redline.cli import main
from redline.premises import check_premises

DELTA = "redline/changes/add-login/specs/auth/delta.md"
OTHER = "redline/changes/add-2fa/specs/auth/delta.md"
SESSION = """import secrets


def create_session(user):
    token = secrets.token_hex()
    return token
"""


def delta(*premises: str) -> str:
    return (
        "## ADDED Requirements\n\n"
        "#### Scenario AUTH.S1 [new]: login issues a session\n"
        "- THEN a session exists, see `auth/missing.py:1`\n\n"
        "### Premises\n" + "".join(f"- {p}\n" for p in premises)
    )


def run(repo, capsys, *args: str) -> tuple[int, list[str]]:
    code = main(["check-premises", "--repo", str(repo.path), *args])
    return code, capsys.readouterr().out.splitlines()


def test_citations_that_resolve_pass(repo, capsys):
    repo.commit("premises", {
        "auth/session.py": SESSION,
        DELTA: delta(
            "P1: Login issues a session in `auth/session.py:4` (`create_session`)",
            "P2: The token is random — `auth/session.py:4-6` (`token_hex`), returned at `auth/session.py:6`",
        ),
    })
    assert check_premises(repo.path).bad == []
    code, out = run(repo, capsys)
    assert code == 0
    assert out == ["ok: 3 premise citations resolve"]


def test_a_missing_file_is_reported_with_its_delta_line(repo, capsys):
    repo.commit("premises", {"auth/session.py": SESSION, DELTA: delta(
        "P1: Login issues a session in `auth/session.py:4` (`create_session`)",
        "P2: Logins are checked in `auth/login.py:18-35`",
    )})
    code, out = run(repo, capsys)
    assert code == 1
    assert out == [f"{DELTA}:8: auth/login.py:18-35: no such file"]


def test_a_line_or_range_past_the_end_is_reported(repo, capsys):
    repo.commit("premises", {"auth/session.py": SESSION, DELTA: delta(
        "P1: Past the end — `auth/session.py:7`",
        "P2: Runs past the end — `auth/session.py:5-9`",
    )})
    code, out = run(repo, capsys)
    assert code == 1
    assert out == [
        f"{DELTA}:7: auth/session.py:7: line 7 is past the end of the file (6 lines)",
        f"{DELTA}:8: auth/session.py:5-9: line 9 is past the end of the file (6 lines)",
    ]


def test_line_zero_and_a_backwards_range_are_reported(repo, capsys):
    repo.commit("premises", {"auth/session.py": SESSION, DELTA: delta(
        "P1: No line zero — `auth/session.py:0`",
        "P2: Backwards — `auth/session.py:6-4`",
    )})
    code, out = run(repo, capsys)
    assert code == 1
    assert out == [
        f"{DELTA}:7: auth/session.py:0: lines start at 1",
        f"{DELTA}:8: auth/session.py:6-4: the range runs backwards",
    ]


def test_a_quoted_symbol_must_be_on_the_cited_lines(repo, capsys):
    repo.commit("premises", {"auth/session.py": SESSION, DELTA: delta(
        "P1: Wrong line — `auth/session.py:1` (`create_session`)",
        "P2: Wrong range — `auth/session.py:5-6` (`create_session`)",
        "P3: Not in the file — `auth/session.py:4` (`destroy_session`)",
    )})
    code, out = run(repo, capsys)
    assert code == 1
    assert out == [
        f"{DELTA}:7: auth/session.py:1: `create_session` is not on line 1",
        f"{DELTA}:8: auth/session.py:5-6: `create_session` is not on lines 5-6",
        f"{DELTA}:9: auth/session.py:4: `destroy_session` is not on line 4",
    ]


def test_a_premise_without_a_citation_is_reported(repo, capsys):
    repo.commit("premises", {"auth/session.py": SESSION, DELTA: delta(
        "P1: Login issues a session in `auth/session.py:4`",
        "P2: Sessions never expire",
    )})
    code, out = run(repo, capsys)
    assert code == 1
    assert out == [f"{DELTA}:8: P2 cites no `file:line`"]


def test_a_path_outside_the_repository_is_not_a_file(repo, capsys):
    (repo.path.parent / "outside.py").write_text("x = 1\n", encoding="utf-8")
    repo.commit("premises", {DELTA: delta("P1: Outside — `../outside.py:1`")})
    code, out = run(repo, capsys)
    assert code == 1
    assert out == [f"{DELTA}:7: ../outside.py:1: no such file"]


def test_only_the_premises_section_is_checked(repo, capsys):
    # The scenario above the premises cites `auth/missing.py:1`; that isn't a premise.
    repo.commit("premises", {"auth/session.py": SESSION, DELTA: delta("P1: Here — `auth/session.py:1`")})
    assert run(repo, capsys)[0] == 0


def test_every_change_is_checked_unless_one_is_named(repo, capsys):
    repo.commit("two changes", {
        "auth/session.py": SESSION,
        DELTA: delta("P1: Here — `auth/session.py:1`"),
        OTHER: delta("P1: Gone — `auth/twofa.py:3`"),
    })
    code, out = run(repo, capsys)
    assert code == 1
    assert out == [f"{OTHER}:7: auth/twofa.py:3: no such file"]
    assert check_premises(repo.path, "add-login").bad == []
    code, out = run(repo, capsys, "--change", "add-login")
    assert code == 0
    assert out == ["ok: 1 premise citation resolves"]


def test_an_unknown_change_is_an_error(repo, capsys):
    repo.commit("empty")
    code, out = run(repo, capsys, "--change", "nope")
    assert code == 2
    assert out == ["redline: no change redline/changes/nope"]
