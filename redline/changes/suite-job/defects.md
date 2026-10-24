# Defects: suite-job

## D1: no scenario gave `ci pr --suite-result` a failing result or a failing gate at a step
Cause: spec
Found-by: suite-job/S
At a step the option could have passed anything: no THEN gave it `failure`, `cancelled` or
`skipped`, or a gate that fails beside it (F1). S2 now gives a G1 step's PR over 400 lines, which
prints both failures, and H1 holds check-break and the suite at an R step without the option.

## D2: a run cancelled while `suite` ran left the required `redline` job unrun
Cause: spec
Found-by: suite-job/S
With `needs: suite` alone, a cancelled `suite` skips the `redline` job, and nothing said its
required check couldn't then read as passed (F2). S4 now gives the job `if: always()`, S2 fails on
`cancelled`, and §12 lists GitHub's handling of a skipped required check as trusted.

## D3: S4's last clause forbade the `redline ci push` step the change keeps
Cause: spec
Found-by: suite-job/S
"No other step runs `redline`" held for the PR's steps but also struck the push step, so a G2 that
met it would have written no note (F3). S4 now names that step, with its `if`, as the one other.

## D4: no premise stated what S1's "none of the PR's code" rests on
Cause: premise
Found-by: suite-job/S
That only check-break and the suite run the repository's code, and that every other process a
gate starts is git or `gh`, was believed, not cited (F4). P4 to P7 now state it, and P9 and P10
the two claims S3 rests on.

## D5: nothing held the proposal's "the gate reads only the result"
Cause: spec
Found-by: suite-job/S
The `suite` job runs the PR's code, which can write a job's outputs; an `outputs` key, or an `env`
that read more of `needs.suite`, would have carried them into the gate (F5). S4 now says the job
has no `outputs`, the gate's `env` is `SUITE` and `GH_TOKEN` alone, and `needs.suite.result` is the
one read of `needs.suite`.

## D6: four clauses passed without the behaviour they named
Cause: spec
Found-by: suite-job/S
S1 had no control without the option, S2 didn't name its refusals' text, and S3 had no G1 step
and no PR outside a step, so each passed on today's code or with a test that couldn't see it
(F6). Each now has the case that tells them apart.

## D7: the proposal said check-break at C loses nothing, but two of its refusals run no test
Cause: spec
Found-by: suite-job/S
A `hold` scenario no test links without `new=True`, and premises citing no file to mutate, are
refused before or apart from any test, so moving check-break to the `suite` job alone would have
lost them from the gate (F7). S5 keeps both in `ci pr --suite-result` at R.

## D8: §5 and §7 still put the PR's install and suite in the `redline` job
Cause: handoff
Found-by: suite-job/S
The design text the next steps read beside the delta disagreed with S4 (F8). §7 now has `suite`
run the PR's pip lines and the installed-pins test, and §5 has it run check-order on a PR.

## D9: three wordings said less than meant, or something else
Cause: spec
Found-by: suite-job/S
S1's GIVEN said "every gate" where check-break must fail, INSTALL.WF.S1 didn't say which job's
editable install the keys match, and the install delta's P3 cited the wrong lines (F9). Each now
says what was meant.

## D10: the merge-base's install ran `python -m venv` in the PR's checkout, so the PR's code ran in the gate's job
Cause: premise
Found-by: suite-job/S
`python -m` puts the working directory first on `sys.path`, so a PR with a `venv.py` at its root
ran its own module there, before the gate was installed, and could leave a `.pth` file every later
`redline` ran (F10). The proposal, §7 and O-SELF3's closure all believed no PR code had run yet.
PR #81 moved the `cd` before `python -m venv`, S4 pins that order in both jobs, and P14 cites it.

## D11: P8 put check-break's "nothing to mutate" before any test, where it came after the unmutated run
Cause: premise
Found-by: suite-job/S
`mutate`, which holds the refusal, is reached only once the scenario's tests ran unmutated and
passed, so S5's refusal with no test run needed G1 to decide it from the premises alone (F11). P8
now gives the order as it is, and S5 says what each command prints.

## D12: four of today's tests pinned the workflow S4 replaces, and no step owned them
Cause: handoff
Found-by: suite-job/S
`tests/test_pins.py` counted four versions and four jobs and the pip lines' jobs, and
`tests/test_ci.py` expected the gate's `--python`; check-track exempts tests, so G2 could have
rewritten them with no scenario behind it (F12). O5 gave them to R, under S4.

## D13: G1's and G2's Track lines, and O3, named `docs/design.md`, which the split removed
Cause: handoff
Found-by: suite-job/S
PR #80 split the design text into `specs/` after the steps were written, so a design-text edit at
G1 or G2 would have been outside its track (F13). The steps now name `specs/07-trust-model.md`, and
O3 `specs/12-open-problems.md`.

## D14: two wordings said less than meant
Cause: spec
Found-by: suite-job/S
`ci push --python` would still have said `--python is for ci pr only` once `ci suite` took it, and
S1's GIVEN didn't say its premises cite a file the `hold` test's runner mutates, without which S5's
refusal fails S1 (F14). S2 now names the new message, and S1's GIVEN the file.

## D15: R's two constants above `install()` moved INSTALL.WF.H1's locked reach
Cause: tooling
Found-by: suite-job/R
check-lock hashes each reached definition with its line, so `SUITE` and `JOBS`, added above
`install()` in `tests/test_install_workflow.py`, failed the lock with no change to the locked test.
The commit 740770b moved them below it.

## D16: R's S3 test asserted `--redline-spec GREET.H1` where `runner.py` passes `--redline-spec=GREET.H1`
Cause: test
Found-by: suite-job/G1
S3's fake interpreter records its arguments, and the test looked for the spec's ID as a separate
argument, a form `runner.py` has never passed, so S3 stayed red under a G1 that met it. G1 changed
that one assertion (539e746).
