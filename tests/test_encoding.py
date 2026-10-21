"""Text is UTF-8 on every platform (docs/design.md §7, O-ENC1, O-ENC2). The first three fail only
where Python's own encoding isn't UTF-8, as on Windows; the `windows` CI job runs them there."""
import os
import subprocess
import sys

from test_specs import CHANGE as SPEC_CHANGE, DELTA, S0, S3, S4, S0_LOUD, S1, living, specs
from test_start import STEPS, change, fresh_branch, start  # noqa: F401

AT_MOST = "#### Scenario GREET.S5 [hold]: keeps it short\n- THEN the greeting is ≤ 20 characters\n"


def test_a_config_rule_outside_ascii_reaches_the_brief(change, capsys):
    change.commit("a rule", {"redline/config.yaml": "rules:\n  premise:\n    - Cite Łódź, not Lodz\n"})
    fresh_branch(change, "spec")
    code, out = start(change, capsys, "add-greet/S")
    assert code == 0
    assert "Cite Łódź, not Lodz" in out


def test_an_unchanged_scenario_outside_ascii_is_unchanged(repo, capsys):
    spec = "redline/specs/greet/spec.md"
    repo.commit("add-greet spec", {spec: living(S0, S3, S4, AT_MOST), f"{SPEC_CHANGE}/specs/greet/delta.md": DELTA})
    repo.git("checkout", "-q", "-b", "close")
    repo.commit("merge the delta", {spec: living(S0_LOUD, S1, S4, AT_MOST)})
    assert specs(repo, capsys) == (0, ["ok: 1 added, 1 modified, 1 removed, as the deltas say; nothing else in redline/specs changed"])


def test_a_brief_outside_ascii_prints_through_a_pipe(change):
    change.commit("a goal with a bound", {f"{SPEC_CHANGE}/steps.md": STEPS.replace(
        "## S: Spec for greeting", "## S: Spec for greeting, ≤ 400 lines")})
    fresh_branch(change, "spec")
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}
    done = subprocess.run([sys.executable, "-m", "redline", "start", "add-greet/S", "--repo", str(change.path)],
                          capture_output=True, env=env)
    assert done.returncode == 0, done.stderr.decode("utf-8", errors="replace")
    assert "Goal: Spec for greeting, ≤ 400 lines" in done.stdout.decode("utf-8")


def test_a_living_spec_under_a_path_outside_ascii_is_read_at_the_merge_base(repo, capsys):
    spec = "redline/specs/grüße/spec.md"
    repo.commit("add-greet spec", {spec: living(S0, S3, S4), f"{SPEC_CHANGE}/specs/grüße/delta.md": DELTA})
    repo.git("checkout", "-q", "-b", "close")
    repo.commit("merge the delta", {spec: living(S0_LOUD, S1, S4)})
    assert specs(repo, capsys) == (0, ["ok: 1 added, 1 modified, 1 removed, as the deltas say; nothing else in redline/specs changed"])
