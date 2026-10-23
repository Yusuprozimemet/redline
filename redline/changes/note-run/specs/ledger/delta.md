## ADDED Requirements

### Requirement: A CI note is checked against its run
The ledger reads a result or a break from a CI note only when the note's `run:` is a push run of
`.github/workflows/redline.yml` on `main`, in this repository, on the noted commit, whose `redline`
job concluded `success` exactly when the note records no failure. A failure is `result: fail`, or
a `break:` entry `fail` that names a `hold` scenario whose break the ledger reads from that note;
an entry for any other scenario counts for nothing. A break is read as its entry only from a
note that says `result: pass`, and as `fail` from one that says `result: fail`.
The ledger asks GitHub for the run in the checkout's own repository, by the run's id alone, once
it has read that repository. Any other note reads as `unconfirmed`. A note that isn't YAML, or
whose `result:` is neither `pass` nor `fail`, is an error before GitHub is asked; so is a
repository GitHub doesn't show, and any other failure to read a run than a 404.

#### Scenario LEDGER.RUN.S1 [new]: a note on its own run keeps its result
- GIVEN a change whose red merged on a commit, noted `result: pass` with the URL of a run
- AND GitHub has that run: a `push` on `main` of `.github/workflows/redline.yml`, its `head_sha` the noted commit, its `redline` job concluded `success`
- WHEN the ledger is rebuilt
- THEN the red's result is `pass`
- AND when that note is on another merged commit, whose run it isn't, that commit's result is `unconfirmed`

#### Scenario LEDGER.RUN.S2 [new]: a run of another event, branch, workflow file or repository confirms nothing
- GIVEN a note whose run is on the noted commit and whose `redline` job concluded `success`
- WHEN the run's event is `pull_request`, or its `head_branch` isn't `main`, or its `path` is another workflow file, or its `html_url` isn't the note's `run:`
- OR the note's `run:` names another repository's run, which GitHub has there with every field as in LEDGER.RUN.S1 and the note's `run:` as its `html_url`, and this repository has no run of that id
- THEN the result is `unconfirmed`, in each case
- AND with every field as in LEDGER.RUN.S1, the result is `pass`

#### Scenario LEDGER.RUN.S3 [new]: the redline job's outcome must agree with the note
- GIVEN a note on its own run, as in LEDGER.RUN.S1, on the R merge of a change with a `hold` scenario H
- WHEN the note says `result: pass`, with H's entry `pass` or none, and the `redline` job concluded `failure`, or `result: fail` and `success`, or `result: pass` with H's `break:` entry `fail` and `success`, or the run's jobs have no `redline` job
- OR the job concluded `failure` and the note says `result: pass` with H's entry `pass` and an entry `fail` for a scenario the ledger reads no break of from that note
- THEN the result, and H's break, is `unconfirmed`, in each case, H's too when the note has no entry for it
- AND `result: fail` with the job's `failure` reads `fail`, and H's break `fail` whatever its entry says
- AND `result: pass` with H's entry `fail` and the job's `failure` reads `pass`, H's break `fail`
- AND `result: pass` with H's entry `pass` and the job's `success` reads `pass`, H's break `pass`
- AND `result: pass` with H's entry `pass`, an entry `fail` for a scenario the change no longer holds, and the job's `success` reads `pass`, H's break `pass`
- AND with the R merge's note on its own run and H's entry `pass`, a note on the merge of a green of the change, which the ledger reads no break from, that says `result: pass` with H's entry `fail` beside the job's `failure` makes that green's result `unconfirmed`, and H's break still reads `pass`

#### Scenario LEDGER.RUN.S4 [new]: a missing run, a URL that isn't a run or no run line reads unconfirmed at once
- GIVEN a note whose `run:` GitHub answers with a 404, a note whose `run:` isn't `…/actions/runs/<id>`, and a note with no `run:` line
- WHEN the ledger is rebuilt
- THEN each result is `unconfirmed`
- AND GitHub is asked about each run once in a rebuild, however many entries read its note, with no wait
- AND a note on its own run, as in LEDGER.RUN.S1, still reads `pass`

#### Scenario LEDGER.RUN.S5 [new]: a failure to read GitHub, or a note that can't be read, is an error
- GIVEN a note whose run GitHub answers with an error other than a 404, on every try
- WHEN `redline ledger <change>` runs
- THEN it exits 2, with an error naming the note's `run:`, and writes no ledger
- AND when GitHub answers the checkout's own repository with a 404, it exits 2, saying GitHub doesn't show the checkout's repository to the token, and no run is asked for
- AND without `gh` on the path it exits 2, saying `gh` is needed to check the CI notes, with no traceback
- AND a note that isn't YAML, or whose `result:` is neither `pass` nor `fail`, exits 2 naming its commit, with no traceback, and GitHub isn't asked
- AND once GitHub answers with the run, it exits 0

#### Scenario LEDGER.RUN.S6 [new]: check-close refuses an unconfirmed result as a note that doesn't match its run
- GIVEN a change whose every red and green is noted `result: pass`, one of those notes on a run that doesn't check out
- WHEN check-close runs
- THEN it fails, naming the scenario, the red or green and the merged commit, and saying the CI note there doesn't match its run on GitHub
- AND it doesn't say it is waiting for CI
- AND once that note's run checks out, it passes

### Requirement: The workflow runs the push run a note can check out against, and nothing can change it
The push run's `redline` job, in `.github/workflows/redline.yml`, notes its own run's URL as
`run:`. The `redline` and `runners` jobs hold `actions: read`, so the ledger and the real reads can
ask for runs, and no job holds `actions: write`, so no code a PR runs can re-run, cancel or delete
the runs the ledger trusts.

#### Scenario LEDGER.RUN.S7 [new]: the workflow notes its own run and grants actions read to the jobs that read runs, and write to none
- GIVEN `.github/workflows/redline.yml`
- WHEN its jobs are read
- THEN the step of the `redline` job that runs `redline ci push` passes `--run-url` as `${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}`
- AND the `redline` and `runners` jobs each hold `actions: read`
- AND no job, nor the workflow's default, holds `actions: write`

### Premises
- P1: The rebuild takes a note's `result:` as it stands and never reads its `run:` line; a missing note is `unverified` — `src/redline/ledger.py:43-56` (`ci_result`)
- P2: Every red, green and break in a rebuilt ledger gets its result from that one function, on the commit its evidence merged on — `src/redline/ledger.py:84-88` (`ci_result`)
- P3: A break's result is its entry in the same note's `break:` map — `src/redline/ledger.py:54-56` (`breaks`)
- P4: check-close takes every result from the rebuilt ledger — `src/redline/close.py:39` (`rebuild`)
- P5: check-close says only `unverified` is waiting; any other result that isn't `pass` reads as failed, "the CI note says" it — `src/redline/close.py:59-66` (`unverified`)
- P6: Every `gh api` read of the `GitHub` seam is tried up to eight times, waiting between tries, whatever the error — `src/redline/pr.py:62-69` (`TRIES`)
- P7: The `GitHub` seam has no read of a workflow run; it reads labels, pushes, PRs and roles — `src/redline/pr.py:50-112` (`class GitHub`)
- P8: The push run writes its own URL as the note's `run:`, `<server>/<owner>/<repo>/actions/runs/<run id>` — `.github/workflows/redline.yml:63` (`actions/runs`)
- P9: The `note` job runs after the `redline` job, in the same run, so the run a note names has its `redline` job's conclusion — `.github/workflows/redline.yml:71-73` (`needs: redline`)
- P10: The note says `result: fail` only when the suite failed; a failed break or claims read fails the run and leaves `result: pass` — `src/redline/ci.py:136-148` (`result:`)
- P11: The `redline` and `runners` jobs hold `contents`, `issues` and `pull-requests` read, and nothing reads the Actions API — `.github/workflows/redline.yml:22-25` (`pull-requests: read`)
- P12: The existing tests' notes name runs no GitHub has, such as `https://ci/1` — `tests/test_ledger.py:24` (`https://ci/1`)
- P13: A failed `gh` call raises with its stderr alone; for a run GitHub doesn't have, `gh api repos/<owner>/<repo>/actions/runs/<id>` exits 1 with stderr `gh: Not Found (HTTP 404)` (run 1 of this repository, 2026-10-22), and so does `gh api repos/<owner>/<repo>` for a repository GitHub doesn't show the token, which it doesn't tell from one that doesn't exist (2026-10-23) — `src/redline/pr.py:58-59` (`done.stderr`)
- P14: A machine without `gh` makes the seam raise `FileNotFoundError`, which neither `read` nor `run_ledger` catches — `src/redline/pr.py:57` (`subprocess.run`)
- P15: A note whose `result:` is neither `pass` nor `fail` is an error today, which `redline ledger` prints and exits 2; a note that isn't YAML raises `yaml.YAMLError`, which nothing catches — `src/redline/ledger.py:48-51` (`safe_load`)
- P16: The workflow's tests compare the default permissions and the `note` job's as a whole, every other job's `contents`, the `redline` job's `pull-requests` and the `runners` job's as equal to the `redline` job's, and of the push step's options only `--note`; none reads `--run-url` or `actions` — `tests/test_ci.py:278-306` (`permissions`), `tests/test_approval.py:206-216` (`permissions`)
- P17: CI writes a `break:` map only on an R merge, keyed by exactly the change's `hold` scenarios — `src/redline/ci.py:138-143` (`check_break`)
- P18: Run 39848744114, the push run of b41ea41, which notes it as its `run:`, gives that URL as its `html_url`, `push`, b41ea41, `main` and `.github/workflows/redline.yml`, and its jobs list a job named `redline`, concluded `success`, after the job's key, which has no `name:` (2026-10-23) — `.github/workflows/redline.yml:20` (`redline:`), `.github/workflows/redline.yml:63` (`--run-url`)
