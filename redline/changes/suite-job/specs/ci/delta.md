## ADDED Requirements

### Requirement: A PR's code runs in a job of its own, and the gate's job runs none of it
`redline ci suite --base main` runs a PR's code and no gate: check-break at an R step, its step
worked out from the trailers as `ci pr` does, then the suite. `redline ci pr --suite-result
<result>` runs every gate and check-ledger, as `ci pr` does, but neither check-break nor the
suite, and fails on a result other than `success`; without the option, `ci pr` runs everything as
before. On a pull request Redline's own workflow runs the PR's install and `ci suite` in a `suite`
job, and its `redline` job, which needs that job and runs whatever it concluded, installs only the
merge-base's Redline and passes the suite job's result to `ci pr --suite-result`.

#### Scenario CI.APART.S1 [new]: `ci pr --suite-result success` runs every gate and none of the PR's code
- GIVEN a change at its R step whose PR passes every gate but holds a `hold` scenario whose test fails unmutated, a test file that fails, and a `conftest.py` that writes a file outside the repository when pytest loads it
- AND a PR outside any step that passes every gate and holds that test file and `conftest.py`
- WHEN `redline ci pr --base main --suite-result success` runs on each
- THEN each exits 0 and prints a line starting `ok:`, with no line starting `suite:` or `check-break:`
- AND the `conftest.py`'s file isn't written

#### Scenario CI.APART.S2 [new]: a suite job's result other than `success` fails the gate
- GIVEN a PR outside any step that passes every gate, and the same PR with more than 400 changed lines and no `Oversized` trailer
- WHEN `redline ci pr --base main --suite-result <result>` runs with `failure`, `cancelled` and `skipped`
- THEN it exits 1 and prints `suite: the suite job's result is <result>`, in each case
- AND on the PR over 400 lines it prints check-lines' failure too
- AND `--suite-result` given to `ci push` or `ci suite`, or with a value outside the four, exits 2 and runs no gate

#### Scenario CI.APART.S3 [new]: `ci suite` runs check-break at an R step, then the suite, and no gate
- GIVEN a change at its R step whose PR has more than 400 changed lines and no `Oversized` trailer, a `hold` scenario whose test fails unmutated, and a test file that fails
- WHEN `redline ci suite --base main` runs
- THEN it exits 1 and prints a line starting `check-break: <the hold scenario's ID>:` and one starting `suite: the test suite failed`, and no line starting `check-lines:`
- AND with `--python <path>`, the suite and check-break's unmutated run use that interpreter
- AND on a PR outside any step whose tests pass, it runs the suite alone, exits 0 and prints a line starting `ok:`
- AND on a branch whose trailers name two steps, it prints `refused:` and exits 1

#### Scenario CI.APART.S4 [new]: Redline's workflow runs the PR's code in its `suite` job alone
- GIVEN `.github/workflows/redline.yml`
- WHEN its jobs are read
- THEN a `suite` job has `if: github.event_name == 'pull_request'`, `permissions` of `contents: read` alone, and as its steps the `redline` job's checkout, fetch of `main` and the notes, and setup-python, each equal to the `redline` job's, then the merge-base's install, the editable install, and a step whose `run` is `"$RUNNER_TEMP/gate/bin/redline" ci suite --base main --python "$(command -v python)"`
- AND the `redline` job has `needs: suite` and `if: ${{ !cancelled() }}`, and its editable install `if: github.event_name == 'push'`
- AND the `redline` job's steps whose `if` lets them run on a pull request are the checkout, the fetch, setup-python, the merge-base's install and one gate, whose `run` is `"$RUNNER_TEMP/gate/bin/redline" ci pr --base main --pr ${{ github.event.pull_request.number }} --suite-result "$SUITE"`, with `SUITE: ${{ needs.suite.result }}` and `GH_TOKEN: ${{ github.token }}` in its `env`
- AND no step of either job runs `pip install -e .` or `redline` outside those named here

#### Scenario CI.APART.H1 [hold]: `ci pr` without `--suite-result` still runs the suite in its own process
- GIVEN a PR outside any step that passes every gate and holds a test file that fails
- WHEN `redline ci pr --base main` runs
- THEN it exits 1 and prints a line starting `suite: the test suite failed`

### Premises
- P1: At a step `ci pr` runs the gates, then the suite, then check-ledger, in one process — `src/redline/ci.py:128-129` (`suite(repo)`)
- P2: Outside any step `ci pr` runs the gates for any PR, then the suite — `src/redline/ci.py:111` (`suite(repo)`)
- P3: At an R step the gates run check-break — `src/redline/pr.py:229-230` (`check_break`)
- P4: check-break runs mutmut in a throwaway copy of the repository — `src/redline/breaks.py:106` (`TemporaryDirectory`), `src/redline/breaks.py:117` (`mutmut`)
- P5: A runner's tests run with the repository as their directory and the job's environment — `src/redline/runner.py:216` (`os.environ`)
- P6: `redline ci` takes `pr` and `push` alone, and `--python` is for `pr` alone — `src/redline/cli.py:104` (`choices`), `src/redline/cli.py:446` (`--python is for ci pr only`)
- P7: On a PR Redline's workflow installs the merge-base's Redline, then the PR's own editable, then gates with `--python`, in the one `redline` job — `.github/workflows/redline.yml:44` (`pull_request`), `.github/workflows/redline.yml:55` (`-e .`), `.github/workflows/redline.yml:59` (`--python`)
- P8: The `note` job needs `redline` and runs unless the run was cancelled — `.github/workflows/redline.yml:73-74` (`needs: redline`)
