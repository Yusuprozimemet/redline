## ADDED Requirements

### Requirement: A PR's code runs in a job of its own, and the gate's job runs none of it
`redline ci suite --base main` runs a PR's code and no gate: check-break at an R step, its step
worked out from the trailers as `ci pr` does, then the suite. `redline ci pr --suite-result
<result>` runs every gate and check-ledger, as `ci pr` does, but not the suite or the part of
check-break that runs tests, and fails on a result other than `success`; check-break's refusals
that run no test, a `hold` scenario no test links without `new=True` and premises that cite no file
to mutate, stay in it at an R step. Without the option, `ci pr` runs everything as before. On a
pull request Redline's own workflow runs the PR's install and `ci suite` in a `suite` job, and its
`redline` job, which needs that job and runs whatever it or the run concluded, installs only the
merge-base's Redline and passes the suite job's result, and nothing else of it, to
`ci pr --suite-result`.

#### Scenario CI.APART.S1 [new]: `ci pr --suite-result success` runs every gate and none of the PR's code
- GIVEN a change at its R step whose PR passes every gate but check-break, its `hold` scenario's test failing unmutated and its premises citing a file that test's runner mutates, and holds a test file that fails and a `conftest.py` that writes a file outside the repository when pytest loads it
- AND a PR outside any step that passes every gate and holds that test file and `conftest.py`
- WHEN `redline ci pr --base main --suite-result success` runs on each
- THEN each exits 0 and prints a line starting `ok:`, with no line starting `suite:` or `check-break:`
- AND the `conftest.py`'s file isn't written
- AND on each, `redline ci pr --base main` without the option writes that file and exits 1

#### Scenario CI.APART.S2 [new]: a suite job's result other than `success` fails the gate, beside the gates' failures
- GIVEN a PR outside any step that passes every gate, and the same PR with more than 400 changed lines and no `Oversized` trailer
- AND a change at its G1 step whose PR has more than 400 changed lines and no `Oversized` trailer
- WHEN `redline ci pr --base main --suite-result <result>` runs on each with `failure`, `cancelled` and `skipped`
- THEN it exits 1 and prints `suite: the suite job's result is <result>`, in each case
- AND on each PR over 400 lines it prints check-lines' failure too, and with `success` that failure alone, exiting 1
- AND `--suite-result` given to `ci push` or `ci suite` exits 2 and prints `redline: --suite-result is for ci pr only`, and `--pr`, `--run-url` or `--note` given to `ci suite` exits 2 and prints `redline: ci suite takes --base and --python alone`, each running no gate and no test
- AND a `--suite-result` outside the four exits 2
- AND `--python` given to `ci push` exits 2 and prints `redline: --python is for ci pr and ci suite only: a push run's suite is the merged code's own`

#### Scenario CI.APART.S3 [new]: `ci suite` runs check-break at an R step, then the suite, and no gate
- GIVEN a change at its R step whose PR has more than 400 changed lines and no `Oversized` trailer, a `hold` scenario whose test fails unmutated, and a test file that fails
- WHEN `redline ci suite --base main` runs
- THEN it exits 1 and prints a line starting `check-break: <the hold scenario's ID>:` and one starting `suite: the test suite failed`, and no line starting `check-lines:`
- AND with `--python <path>`, the suite and check-break's unmutated run use that interpreter
- AND at the same change's G1 step, with the same `hold` test, it prints no line starting `check-break:`
- AND on a PR outside any step with more than 400 changed lines, no `Oversized` trailer and tests that pass, it exits 0 and prints a line starting `ok:`
- AND on a branch whose trailers name two steps, it prints `refused:` and exits 1

#### Scenario CI.APART.S4 [new]: Redline's workflow runs the PR's code in its `suite` job alone, and the gate reads only its result
- GIVEN `.github/workflows/redline.yml`
- WHEN its jobs are read
- THEN a `suite` job has `if: github.event_name == 'pull_request'`, `permissions` of `contents: read` alone, no `outputs`, and as its steps the `redline` job's checkout, fetch of `main` and the notes, and setup-python, each equal to the `redline` job's, then the merge-base's install, the editable install, and a step whose `run` is `"$RUNNER_TEMP/gate/bin/redline" ci suite --base main --python "$(command -v python)"`
- AND the `redline` job has `needs: suite` and `if: always()`, and its editable install `if: github.event_name == 'push'`
- AND the `redline` job's steps whose `if` lets them run on a pull request are the checkout, the fetch, setup-python, the merge-base's install and one gate, whose `run` is `"$RUNNER_TEMP/gate/bin/redline" ci pr --base main --pr ${{ github.event.pull_request.number }} --suite-result "$SUITE"` and whose `env` is `SUITE: ${{ needs.suite.result }}` and `GH_TOKEN: ${{ github.token }}` alone
- AND the merge-base's install, in each job, runs `git worktree add`, then `cd "$RUNNER_TEMP/base"`, then `python -m venv "$RUNNER_TEMP/gate"`, so no `python` of the `redline` job's steps that run on a pull request starts with the PR's checkout as its directory
- AND the workflow has five jobs, `suite` and today's four, with a `python-version` in `suite`'s setup-python equal to the `redline` job's, and pip lines in `redline`, `suite`, `runners` and `windows` alone
- AND `needs.suite.result` is the one read of `needs.suite` in the workflow
- AND no other step of either job runs `pip install -e .` or `redline`, but the `redline` job's push step, `if: github.event_name == 'push'`, which runs `redline ci push`

#### Scenario CI.APART.S5 [new]: at an R step `ci pr --suite-result` keeps check-break's refusals that run no test
- GIVEN a change at its R step whose PR passes every gate but check-break, with a `hold` scenario that only a `new=True` test links, and another change at its R step whose premises cite no file its `hold` test's runner mutates, that test failing unmutated
- WHEN `redline ci pr --base main --suite-result success` runs on each
- THEN it exits 1 and prints `check-break: <the hold scenario's ID>: no test links it without new=True` on the first and `check-break: <the hold scenario's ID>: nothing to mutate: the change's premises cite no file its tests' runners mutate` on the second
- AND no test runs: a `conftest.py` that writes a file when pytest loads it writes none, so the second refusal is decided from the premises' files alone
- AND `ci suite` on the second change, its check-break in today's order, prints a line starting `check-break: <the hold scenario's ID>: its` and ending `tests fail on unmutated code`

#### Scenario CI.APART.H1 [hold]: `ci pr` without `--suite-result` still runs check-break and the suite in its own process
- GIVEN a PR outside any step that passes every gate and holds a test file that fails
- AND a change at its R step whose PR passes every gate but check-break, its `hold` scenario's test failing unmutated
- WHEN `redline ci pr --base main` runs on each
- THEN each exits 1 and prints a line starting `suite: the test suite failed`
- AND on the R step's PR a line starting `check-break: <the hold scenario's ID>:`

### Premises
- P1: At a step `ci pr` runs the gates, then the suite, then check-ledger, in one process — `src/redline/ci.py:128-129` (`suite(repo)`)
- P2: Outside any step `ci pr` runs the gates for any PR, then the suite — `src/redline/ci.py:111` (`suite(repo)`)
- P3: At an R step the gates run check-break — `src/redline/pr.py:229-230` (`check_break`)
- P4: check-break runs mutmut in a throwaway copy of the repository, and Stryker in the repository — `src/redline/breaks.py:106` (`TemporaryDirectory`), `src/redline/breaks.py:118` (`subprocess.run`), `src/redline/breaks.py:146` (`subprocess.run`)
- P5: A runner's tests run with the repository as their directory and the job's environment, from the suite and from check-break's unmutated run — `src/redline/runner.py:216` (`os.environ`), `src/redline/ci.py:81` (`run(repo, runner)`), `src/redline/breaks.py:206` (`run(repo, runner, sid)`)
- P6: Every other process a gate starts is git or `gh`, and `merged` is no gate — `src/redline/order.py:36` (`subprocess`), `src/redline/order.py:50` (`subprocess`), `src/redline/pr.py:63` (`subprocess.run`), `src/redline/merged.py:31` (`subprocess.run`)
- P7: The gates read the PR's files as data: YAML by `safe_load`, tests by `ast` — `src/redline/config.py:37` (`safe_load`), `src/redline/lock.py:45` (`safe_load`), `src/redline/reach.py:5` (`ast`)
- P8: check-break refuses a `hold` scenario no test links without `new=True` before any test runs; it refuses premises that cite no file to mutate only in `mutate`, after the scenario's tests ran unmutated and passed, though it finds those files from the premises alone — `src/redline/breaks.py:245-246` (`no test links it without new=True`), `src/redline/breaks.py:247` (`unmutated`), `src/redline/breaks.py:249-250` (`mutate`), `src/redline/breaks.py:236-237` (`nothing to mutate`), `src/redline/breaks.py:199-202` (`premise_lines`)
- P9: The step comes from the trailers of `main..HEAD`, two steps are refused, and `ci` prints a refusal as `refused:` with exit 1 — `src/redline/ci.py:87-99` (`def pr_step`), `src/redline/cli.py:459-461` (`refused:`)
- P10: `--python` reaches the suite and check-break's unmutated run through `interpreter` and `pytest_command` — `src/redline/runner.py:183-198` (`PYTHON`)
- P11: `redline ci` takes `pr` and `push` alone, and `--python` is for `pr` alone — `src/redline/cli.py:104` (`choices`), `src/redline/cli.py:446` (`--python is for ci pr only`)
- P12: On a PR Redline's workflow installs the merge-base's Redline, then the PR's own editable, then gates with `--python`, in the one `redline` job, which has no `needs` or `if` — `.github/workflows/redline.yml:20-29` (`redline:`), `.github/workflows/redline.yml:44` (`pull_request`), `.github/workflows/redline.yml:55` (`-e .`), `.github/workflows/redline.yml:59` (`--python`)
- P13: The `note` job needs `redline` and runs on a push with a note unless the run was cancelled, reading `redline`'s output — `.github/workflows/redline.yml:73-74` (`!cancelled() && github.event_name == 'push' && needs.redline.outputs.note != ''`), `.github/workflows/redline.yml:92` (`needs.redline.outputs.note`)
- P14: Today the merge-base's install runs `python -m venv` before its `cd`, with the PR's checkout as its directory, which `python -m` puts first on `sys.path`, and a test pins that order — `.github/workflows/redline.yml:46-48` (`python -m venv`), `tests/test_ci.py:235-239` (`python -m venv`)
