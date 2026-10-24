"""O-AUDIT3: independent critical initiative rounds, using toy audit fixtures only."""
from pathlib import Path

import pytest
import yaml

from redline.cli import main
from redline.plan import read_plan
from redline.planaudit import unresolved_at
from test_plan import PLAN
from test_plan_audit import AUDITS, NONE, critical, stamped  # noqa: F401
from test_start import change  # noqa: F401

TARGETS = ("phase-1-start", "phase-1-end", "security", "architecture", "process")


def path(target):
    return f"{AUDITS}/{target if target.startswith('phase-') else 'initiative-' + target}.md"


def reply(repo, n=1, read=None):
    return stamped(repo, NONE) + f"Round: {n}\nAudited: {read or repo.git('rev-parse', 'HEAD')}\n"


def brief(repo, capsys, target="security"):
    code = main(["plan-audit-brief", "greetings", target, "--repo", str(repo.path)])
    return code, capsys.readouterr().out


@pytest.mark.parametrize("target", TARGETS)
def test_first_and_incremental_rounds_are_independent(critical, capsys, target):
    read = critical.git("rev-parse", "HEAD")
    code, out = brief(critical, capsys, target)
    assert code == 0 and f"Round: 1 of 3\nAudited: {read}\nSince: none" in out
    assert f"with plan {critical.git('hash-object', PLAN)}" in out
    critical.commit("reply and fix", {path(target): reply(critical, read=read),
                                     path("process" if target != "process" else "security"): reply(critical, 3),
                                     "implementation.py": "fixed = True\n"})
    code, out = brief(critical, capsys, target)
    assert code == 0 and f"Round: 2 of 3" in out and f"Since: {read}" in out
    assert "+fixed = True" in out and "diff --git" in out
    assert "diff --git a/redline/initiatives/greetings/audits" not in out
    critical.commit("last reply", {path(target): reply(critical, 3), PLAN: (critical.path / PLAN).read_text() + "\n"})
    code, out = brief(critical, capsys, target)
    assert code == 2 and "round 3 of 3 has run" in out


@pytest.mark.parametrize("target", TARGETS)
@pytest.mark.parametrize("metadata", ["Round: 4\nAudited: " + "a" * 40 + "\n", "Round: 1\n", "Audited: " + "a" * 40 + "\n", "Round: zero\n"])
def test_gates_refuse_invalid_or_excess_metadata(critical, target, metadata):
    critical.commit("toy reply", {path(target): stamped(critical, NONE) + metadata})
    plan = read_plan(critical.path, "greetings")
    for rev in (None, "main"):
        bad = unresolved_at(critical.path, plan, path(target), "test", rev, current=True)
        assert any("Round:" in why or "Audited:" in why or "limit of 3" in why for why in bad), bad


def test_legacy_final_round_and_missing_ancestor(critical, capsys):
    read = critical.git("rev-parse", "HEAD")
    critical.commit("legacy reply", {path("security"): stamped(critical, NONE)})
    code, out = brief(critical, capsys)
    assert code == 0 and "Round: 3 of 3" in out and f"Since: {read}" in out
    critical.commit("rebased reply", {path("security"): reply(critical, 1, "a" * 40)})
    assert "Round: 2 of 3" in brief(critical, capsys)[1]
    assert "Since: none" in brief(critical, capsys)[1]


def test_bad_targets_dirty_tree_and_bad_metadata_refuse(critical, capsys):
    assert brief(critical, capsys, "phase-99-start")[0] == 2
    assert brief(critical, capsys, "../security")[0] == 2
    critical.commit("bad reply", {path("security"): stamped(critical, NONE) + "Round: nope\n"})
    assert brief(critical, capsys)[0] == 2
    (critical.path / PLAN).write_text("dirty", encoding="utf-8")
    assert "uncommitted" in brief(critical, capsys)[1]


@pytest.mark.parametrize("agent", ("plan", "security", "architecture", "process"))
def test_agents_require_metadata_and_incremental_scope(agent):
    text = (Path(__file__).parents[1] / f".claude/agents/redline-{agent}-auditor.md").read_text(encoding="utf-8")
    description = yaml.safe_load(text.split("---\n", 2)[1])["description"]
    assert "Give it only the text `redline plan-audit-brief <initiative> <target>` prints" in description
    assert "with plan" not in description
    if agent == "process":
        assert "`redline claims <initiative>` prints" in description
    assert "plan-audit-brief" in text and "REFUSED: missing Round: or Audited:" in text
    assert "Since: none" in text and "Deferred-to:" in text
