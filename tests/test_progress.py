"""The progress the brief ends with, and `merged` prints after C (specs/ §6, O-PROG1)."""
import os
import subprocess
import sys

from redline.progress import bar
from test_merged import merged, on_step, remote  # noqa: F401 (remote is a fixture)
from test_plan import FAREWELL, PLAN, VALID, close_greet, complete, planned  # noqa: F401 (planned is a fixture)
from test_start import change, fresh_branch, merge_step, start  # noqa: F401 (change is a fixture)

EMPTY = "[" + "░" * 20 + "]"
FULL = "[" + "█" * 20 + "]"
HALF = "[" + "█" * 10 + "░" * 10 + "]"


def test_merged_hands_off_with_the_steps_merged_and_the_open_items_left(change, capsys, remote):
    remote.landing = "add-greet/S"
    on_step(change, capsys, "S", "spec")
    code, out = merged(change, capsys, "add-greet/S")
    assert code == 0, out
    assert ("## Progress\n"
            "add-greet: [████░░░░░░░░░░░░░░░░] 1 of 5 steps merged · next: add-greet/R\n"
            "Open items later steps own:\n"
            "- O1 [G1]: decide on the punctuation\n"
            "- O2 [G2]: names with spaces\n") in out
    assert "Phase" not in out and "phases complete" not in out


def test_an_item_whose_step_is_merged_is_no_longer_listed(change, capsys, remote):
    merge_step(change, "S")
    merge_step(change, "R")
    remote.landing = "add-greet/G1"
    on_step(change, capsys, "G1", "green")
    code, out = merged(change, capsys, "add-greet/G1")
    assert code == 0, out
    assert "add-greet: [████████████░░░░░░░░] 3 of 5 steps merged · next: add-greet/G2\n" in out
    assert "Open items later steps own:\n- O2 [G2]: names with spaces\n" in out
    assert "O1" not in out.split("## Progress")[1]


def test_after_c_merged_prints_a_full_bar_alone(change, capsys, remote):
    for step in ("S", "R", "G1", "G2"):
        merge_step(change, step)
    remote.landing = "add-greet/C"
    on_step(change, capsys, "C", "close")
    code, out = merged(change, capsys, "add-greet/C")
    assert code == 0, out
    assert "Brief" not in out
    assert out.endswith(f"## Progress\nadd-greet: {FULL} 5 of 5 steps merged · the change is complete\n"
                        "Open items later steps own:\n(none)\n")


def test_in_an_initiative_it_counts_the_phase_and_the_plan(planned, capsys, remote):
    remote.landing = "add-greet/S"
    on_step(planned, capsys, "S", "spec")
    code, out = merged(planned, capsys, "add-greet/S")
    assert code == 0, out
    assert (f"Phase 1 of 2 (Greet): {EMPTY} 0 of 2 changes complete\n"
            f"greetings: {EMPTY} 0 of 2 phases complete\n") in out


def test_at_a_stopping_point_the_phase_is_full(planned, capsys, remote):
    complete(planned, "add-wave", ("S", "C"))
    code, out = close_greet(planned, capsys, remote)
    assert code == 0, out
    assert "greetings is at a stopping point" in out
    assert (f"Phase 1 of 2 (Greet): {FULL} 2 of 2 changes complete\n"
            f"greetings: {HALF} 1 of 2 phases complete\n") in out


def test_a_change_with_no_steps_yet_isnt_complete(change, capsys, remote):
    change.commit("plan, add-wave not begun", {PLAN: VALID, **FAREWELL})
    code, out = close_greet(change, capsys, remote)
    assert code == 0, out
    assert f"Phase 1 of 2 (Greet): {HALF} 1 of 2 changes complete\n" in out
    assert f"greetings: {EMPTY} 0 of 2 phases complete\n" in out


def test_start_prints_it_at_the_end_of_the_brief(change, capsys):
    fresh_branch(change, "spec")
    code, out = start(change, capsys, "add-greet/S")
    assert code == 0, out
    assert f"## Progress\nadd-greet: {EMPTY} 0 of 5 steps merged · next: add-greet/S\n" in out


def test_the_bar_is_full_only_when_everything_is_done():
    assert bar(39, 40) == "[" + "█" * 19 + "░" + "]"


def test_the_bar_prints_through_a_pipe(change):
    merge_step(change, "S")
    fresh_branch(change, "red")
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}
    done = subprocess.run([sys.executable, "-m", "redline", "start", "add-greet/R", "--repo", str(change.path)],
                          capture_output=True, env=env)
    assert done.returncode == 0, done.stderr.decode("utf-8", errors="replace")
    assert "add-greet: [████░░░░░░░░░░░░░░░░] 1 of 5 steps merged · next: add-greet/R" in done.stdout.decode("utf-8")
