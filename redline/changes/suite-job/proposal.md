# Proposal: suite-job

Rigor: critical

## Why

On a pull request the `redline` job installs the merge-base's Redline into a venv of its own and
gates with it (O-SELF3), but the PR's code still runs in that job, as the same user: its
`pip install -e .`, its suite, and at an R step check-break's unmutated and mutated runs (O-CI10).
Any of them can rewrite a file the gate imports or reads after it: a module of the standard library
the gate imports lazily, a file in the gate's venv, or the history `check-ledger` reads once the
suite is done. In an adopting repository the gate shares its site-packages with the project's
dependencies and code, so the PR's code can rewrite the gate itself. Every gate that isn't the
suite's own outcome, the trailers and the step's order, the lock, the ledger and the approvals, is
then the PR's to decide.

## Scope

- `redline ci suite --base main [--python <path>]` runs the PR's code and no gate: the step from
  the trailers of `main..HEAD`, as `ci pr` works it out, check-break at an R step, then the suite,
  each failure printed as `ci pr` prints it; exit 1 on a failure, `ok: …` and 0 otherwise. Outside
  any step it runs the suite alone.
- `redline ci pr --suite-result <result>`, `<result>` one of `success`, `failure`, `cancelled` and
  `skipped`, the results a GitHub job can have: every gate and check-ledger, as `ci pr` runs them,
  but not the suite or the part of check-break that runs tests, so no process of the PR's code
  runs; check-break's two refusals that run no test, a `hold` scenario no test links without
  `new=True` and premises that cite no file to mutate, stay. A result other than `success` is the
  failure `suite: the suite job's result is <result>`. Without the option, `ci pr` runs everything
  as before. `--suite-result` is for `ci pr` alone, and `ci suite` takes `--base` and `--python`
  alone; elsewhere each exits 2, saying so.
- Redline's own workflow gets a `suite` job, `if: github.event_name == 'pull_request'`, holding
  `contents: read` alone: the `redline` job's checkout, fetch and setup-python, the merge-base's
  install, the PR's editable install and `"$RUNNER_TEMP/gate/bin/redline" ci suite --base main
  --python "$(command -v python)"`, and no `outputs`. The `redline` job `needs: suite` with
  `if: always()`, its editable install runs on a push alone, and its PR gate runs `ci pr` with
  `--suite-result "$SUITE"`, `SUITE` set in the step's `env` to `${{ needs.suite.result }}`, the one
  thing of `suite` the workflow reads.
- The template `redline install workflow` writes follows: a `suite` job with the clone install, a
  comment after it marking the project's install, and `redline ci suite --base main`; the
  `redline` job's install as before, its comment saying the project's install goes there on a
  push alone, and its PR gate `redline ci pr --base main --pr <n> --suite-result "$SUITE"`.
- The README's command table names `ci suite`, and its setup step 3 the `suite` job.

Moving the suite and check-break's test runs out of the gate's job loses nothing: their verdicts
were the PR's code's already, since a `conftest.py` can turn any test's outcome, a mutant's run
included. check-break's refusals that run no test aren't the PR's code's, so they stay in the gate.
A skipped required check reads as passed, so the `redline` job runs whatever `suite` concluded, and
in a cancelled run too, through `always()`, where it fails on the result `cancelled`; it fails on
anything but `success`.

It is critical (§8): it decides which code runs in the job that gates every PR, in Redline's own
workflow and in each adopting repository's, and it widens a public command.

## Non-goals

- **A push run.** Its code is `main`'s, which gates itself; `suite` is skipped there and
  `ci push` is unchanged, so every note and its run check out as before (§4).
- **An adopter's push-only install.** On a push the `redline` job's suite needs the project's
  dependencies, which an adopter adds by hand with `if: github.event_name == 'push'`; nothing
  checks the `if`, and on a push they share the gate's site-packages (O-CI11, part 37).
- **The suite job's verdict.** It is the PR's code's, as it was; the gate reads only the result.
- **A self-hosted runner reused across jobs**, which lets one job leave files for the next:
  Redline's jobs name GitHub's hosted images (§12, Judgments).

## Steps

S (this spec), R (the red tests), G1 (`ci suite` and `--suite-result`, which the merge-base's
Redline needs before a workflow calls them), G2 (the two workflows' `suite` job and the README's
setup step), C (the deltas into `redline/specs/ci/spec.md` and `redline/specs/install/spec.md`,
O-CI10 closed).
