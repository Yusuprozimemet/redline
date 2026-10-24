# Audit: suite-job
Model: claude-opus-5-5
Round: 2
Audited: bcdc05c1b3ba7e6b36cfd6e0a40213571d783cc6

## F1 [closed]: no scenario gives `ci pr --suite-result` a failing result or a failing gate at a step, so at a step the option could pass anything
Resolution: S2 now gives a G1 step's PR over 400 lines, which prints both failures with `failure`, `cancelled` and `skipped`, and check-lines' failure alone with `success` (`redline/changes/suite-job/specs/ci/delta.md:25-28`). H1 now holds check-break and the suite at an R step without the option (`redline/changes/suite-job/specs/ci/delta.md:58-61`).

## F2 [closed]: a run cancelled while `suite` runs leaves the required `redline` job unrun, and nothing says its check can't then read as passed
Resolution: S4 now gives the `redline` job `if: always()` (`redline/changes/suite-job/specs/ci/delta.md:45`). §7 says this runs the job in a cancelled run, where it fails on `cancelled` (`specs/07-trust-model.md:59-62`), and §12 lists that GitHub behaviour as trusted (`specs/12-open-problems.md:37-39`). S2 fails on `cancelled` (`redline/changes/suite-job/specs/ci/delta.md:26-27`), and P13 gives the `note` job's whole condition (`redline/changes/suite-job/specs/ci/delta.md:76`).

## F3 [closed]: S4's last clause forbids the `redline ci push` step the change keeps
Resolution: S4's last clause now names the push step, with its `if`, as the one other step that runs `redline` (`redline/changes/suite-job/specs/ci/delta.md:48`).

## F4 [closed]: no premise states the claim S1's "none of the PR's code" rests on: only check-break and the suite run the repository's code
Resolution: P4 to P7 state which processes the gates start and that they read the PR's files as data (`redline/changes/suite-job/specs/ci/delta.md:67-70`). P9 and P10 state the two claims S3 rests on (`redline/changes/suite-job/specs/ci/delta.md:72-73`). Each holds at its citation.

## F5 [closed]: nothing holds the proposal's "the gate reads only the result": the suite job's outputs, which the PR's code can write, could reach the gate
Resolution: S4 now says the `suite` job has no `outputs` (`redline/changes/suite-job/specs/ci/delta.md:44`), that the gate's `env` is `SUITE` and `GH_TOKEN` alone (`redline/changes/suite-job/specs/ci/delta.md:46`), and that `needs.suite.result` is the one read of `needs.suite` (`redline/changes/suite-job/specs/ci/delta.md:47`).

## F6 [closed]: four clauses pass without the behaviour they name, either on today's code or with a test that can't see it
Resolution: S1 has its control without the option (`redline/changes/suite-job/specs/ci/delta.md:21`), and S2 names the text of both refusals (`redline/changes/suite-job/specs/ci/delta.md:29`). S3 has a G1 step with no `check-break:` line, and a PR outside any step, over 400 lines, that exits 0 (`redline/changes/suite-job/specs/ci/delta.md:37-38`).

## F7 [closed]: "loses nothing" is false for two of check-break's refusals, which run no test
Resolution: S5 keeps both refusals in `ci pr --suite-result` at R (`redline/changes/suite-job/specs/ci/delta.md:50-54`). The proposal and §7 say they stay (`redline/changes/suite-job/proposal.md:25-27`, `specs/07-trust-model.md:74-77`), and G1's Track has `src/redline/breaks.py` (`redline/changes/suite-job/steps.md:10`). F11 covers how one of the two is reached today.

## F8 [closed]: §5 and §7 still put the PR's install and suite in the `redline` job, against S4
Resolution: §7 now has `suite` run the PR's pip lines on a PR (`specs/07-trust-model.md:345-347`), the pin test expect the gate's lines in both `redline` and `suite` (`specs/07-trust-model.md:361-362`), and the installed-pins test run in `suite` on a PR (`specs/07-trust-model.md:369-370`). §5 has `suite` run check-order on a PR (`specs/05-steps.md:180-181`).

## F9 [closed]: three wordings say less than meant, or something else
Resolution: S1's GIVEN says "every gate but check-break" (`redline/changes/suite-job/specs/ci/delta.md:16`), INSTALL.WF.S1 says "in the same job" (`redline/changes/suite-job/specs/install/delta.md:21`), and the install delta's P3 cites `tests/test_install_workflow.py:87-97` (`redline/changes/suite-job/specs/install/delta.md:36`).

## F10 [waived]: the merge-base's install runs `python -m venv` in the PR's checkout, so the PR's code still runs in the `redline` job
Waived-by: @Yusuprozimemet: fixed in the spec without a re-audit (d3c4f4c, fcf63d3)
- **Where it runs.** The step runs `python -m venv "$RUNNER_TEMP/gate"` (`.github/workflows/redline.yml:47`) before its `cd "$RUNNER_TEMP/base"` (`.github/workflows/redline.yml:48`). It sets no `working-directory`, so its directory is the checkout of the PR's head (`.github/workflows/redline.yml:30-34`).
- **What that lets a PR do.** `python -m` puts the working directory first on `sys.path`. A PR that adds a `venv.py` at its root therefore runs its own module in place of the standard library's. That happens in the gate's job, before the gate is installed. The module can build the venv and leave a `.pth` file in its site-packages. The three pip lines after it don't remove that file (`.github/workflows/redline.yml:49-51`), so every Python process the venv starts runs it, the gate step's `"$RUNNER_TEMP/gate/bin/redline"` included.
- **Nothing else stops it.** The PR needs to touch nothing CODEOWNERS guards, which is only `.github/` and `redline/config.yaml` (`specs/07-trust-model.md:557-560`). `tests/test_ci.py:235-239` pins `python -m venv` before the `cd`.
- **What S4 holds.** S4 keeps this step among the `redline` job's PR steps (`redline/changes/suite-job/specs/ci/delta.md:46`), and none of S4's THENs fails on it.
- **Claims this makes false,** today and after G2:
  - the requirement's "the gate's job runs none of it" (`redline/changes/suite-job/specs/ci/delta.md:3`);
  - the proposal's "no process of the PR's code runs" (`redline/changes/suite-job/proposal.md:25-26`);
  - §7's "no code of the PR's has run yet" (`specs/07-trust-model.md:38-39`);
  - the step's own name (`.github/workflows/redline.yml:43`);
  - O-SELF3's closure (`specs/12-open-problems.md:165-166`).
- **What to add.**
  - No premise says where this step's Python runs; add one that cites `.github/workflows/redline.yml:46-48`.
  - Give S4 a THEN that the merge-base's install runs Python only after its `cd` out of the checkout, or only with `-I`, so that no `python -m` or `python -c` in the `redline` job's PR steps runs in the PR's checkout.
  - Say which step changes `tests/test_ci.py:235-239`.

## F11 [waived]: P8 is wrong about "nothing to mutate": today that refusal comes only after the scenario's tests ran unmutated and passed
Waived-by: @Yusuprozimemet: fixed in the spec without a re-audit (d3c4f4c, fcf63d3)
- **The order today.**
  - `check_break` reaches `mutate`, which holds the refusal (`src/redline/breaks.py:236-237`), only in its `else` (`src/redline/breaks.py:249-250`).
  - That `else` runs only after `unmutated` has run each runner's tests for the scenario (`src/redline/breaks.py:247`, `src/redline/breaks.py:209-213`, `src/redline/breaks.py:205-206`).
  - So a scenario whose tests fail unmutated never gets this refusal, and one that gets it ran its tests first.
  - Only "no test links it" (`src/redline/breaks.py:245-246`) is decided before any test runs.
- **What G1 must do.** S5 asks for the refusal in `ci pr --suite-result` with no test run (`redline/changes/suite-job/specs/ci/delta.md:53-54`). G1 must therefore decide it from the premises' files alone (`src/redline/breaks.py:199-202`, `src/redline/breaks.py:221-223`), before the unmutated run or without it. P8 (`redline/changes/suite-job/specs/ci/delta.md:71`) and the proposal's "stay" (`redline/changes/suite-job/proposal.md:25-27`) read as though the code already worked that way.
- **What to add.**
  - Restate P8 with the order as it is.
  - Say what each command prints for a scenario whose tests fail unmutated and whose premises cite nothing to mutate. `ci pr --suite-result` would print "nothing to mutate". `ci suite`, if its check-break keeps today's order, would print that the tests fail on unmutated code.

## F12 [waived]: four of today's tests pin the workflow S4 replaces, and no step says which one changes them
Waived-by: @Yusuprozimemet: fixed in the spec without a re-audit (d3c4f4c, fcf63d3)
None of these tests has a spec marker or a lock entry (`redline/contracts/lock.yaml:1-5`), and each fails on the workflow G2 must write:
- `tests/test_pins.py:68` counts four `python-version` and `node-version` values; `suite`'s setup-python makes five.
- `tests/test_pins.py:73` counts four jobs.
- `tests/test_pins.py:80-81` expects pip lines in `redline`, `runners` and `windows` alone, but `suite` runs the gate's three lines and the editable install's three. §7 already says the test expects `suite` (`specs/07-trust-model.md:361-362`).
- `tests/test_ci.py:242-243` expects the gate's `run` to end in `--python "$(command -v python)"`.

check-track exempts every test file (`src/redline/track.py:20`, `src/redline/track.py:32-35`). G2 could therefore rewrite these tests, the pin test among them, with no scenario behind the edit. Either link them to S4 at R, or give G2 an open item that names each test and what it will expect.

## F13 [waived]: G1's and G2's Track lines, and O3, name `docs/design.md`, which the split removed
Waived-by: @Yusuprozimemet: fixed in the spec without a re-audit (d3c4f4c, fcf63d3)
- **The stale entries.** `redline/changes/suite-job/steps.md:10` and `redline/changes/suite-job/steps.md:14` list `docs/design.md`. O3 closes O-CI10 "in docs/design.md §12" (`redline/changes/suite-job/steps.md:21`).
- **No such file.** There is no `docs/` now: §7 is `specs/07-trust-model.md` and §12 is `specs/12-open-problems.md` (`specs/README.md:7-9`).
- **What check-track does.**
  - check-track reads each track at the merge-base (`src/redline/track.py:24-27`).
  - A glob with a slash matches only that path (`src/redline/lines.py:25-27`).
  - `redline/config.yaml:5-8` exempts no `.md` file.
  - So a design-text edit at G1 or G2 is outside its track, and needs a `Redline-Track` claim and its label (`src/redline/track.py:38-43`).
- **What to change.** Name the `specs/` files each step may edit, or drop the entry, and point O3 at `specs/12-open-problems.md`.

## F14 [waived]: two wordings say less than meant
Waived-by: @Yusuprozimemet: fixed in the spec without a re-audit (d3c4f4c, fcf63d3)
- **`ci push --python`.** The refusal says `--python is for ci pr only` (`src/redline/cli.py:446`), and P11 cites it (`redline/changes/suite-job/specs/ci/delta.md:74`). Once `ci suite` takes `--python` (`redline/changes/suite-job/proposal.md:19`), that text is wrong, and `tests/test_ci.py:97` asserts it whole. Say what `ci push --python` prints after G1, as S2 does for `--suite-result`.
- **S1's R-step change.** S1's GIVEN doesn't say that the change's premises cite a file its `hold` test's runner mutates (`redline/changes/suite-job/specs/ci/delta.md:16`). Without such a file, S5's refusal fails that PR (`redline/changes/suite-job/specs/ci/delta.md:53`), and S1's exit 0 can't hold (`redline/changes/suite-job/specs/ci/delta.md:19`). Say so in the GIVEN.
