## ADDED Requirements

### Requirement: A CI note is checked against its run
The ledger reads a result or a break from a CI note only when the note's `run:` is a push run of
`.github/workflows/redline.yml` on `main`, in this repository, on the noted commit, whose `redline`
job concluded `success` exactly when the note records no failure. Any other note reads as
`unconfirmed`.

#### Scenario LEDGER.RUN.S1 [new]: a note on its own run keeps its result
- GIVEN a change whose red merged on a commit, noted `result: pass` with the URL of a run
- AND GitHub has that run: a `push` on `main` of `.github/workflows/redline.yml`, its `head_sha` the noted commit, its `redline` job concluded `success`
- WHEN the ledger is rebuilt
- THEN the red's result is `pass`
- AND when that note is on another merged commit, whose run it isn't, that commit's result is `unconfirmed`

#### Scenario LEDGER.RUN.S2 [new]: a run of another event, branch, workflow file or repository confirms nothing
- GIVEN a note whose run is on the noted commit and whose `redline` job concluded `success`
- WHEN the run's event is `pull_request`, or its `head_branch` isn't `main`, or its `path` is another workflow file, or its `html_url` isn't the note's `run:`, as when the note names another repository's run
- THEN the result is `unconfirmed`, in each case
- AND with every field as in LEDGER.RUN.S1, the result is `pass`

#### Scenario LEDGER.RUN.S3 [new]: the redline job's outcome must agree with the note
- GIVEN a note on its own run, as in LEDGER.RUN.S1
- WHEN the note says `result: pass` and the `redline` job concluded `failure`, or `result: fail` and `success`, or `result: pass` with a `break:` entry `fail` and `success`
- THEN the result, and each break the note holds, is `unconfirmed`, in each case
- AND `result: fail` with the job's `failure` reads `fail`, and `result: pass` with every `break:` entry `pass` and the job's `success` reads `pass`, its breaks `pass`

#### Scenario LEDGER.RUN.S4 [new]: a missing run, a URL that isn't a run or no run line reads unconfirmed at once
- GIVEN a note whose `run:` GitHub answers with a 404, a note whose `run:` isn't `…/actions/runs/<id>`, and a note with no `run:` line
- WHEN the ledger is rebuilt
- THEN each result is `unconfirmed`
- AND GitHub is asked at most once for each, with no wait between tries
- AND a note on its own run, as in LEDGER.RUN.S1, still reads `pass`

#### Scenario LEDGER.RUN.S5 [new]: a failure to read GitHub is an error naming the run
- GIVEN a note whose run GitHub answers with an error other than a 404, on every try
- WHEN `redline ledger <change>` runs
- THEN it exits 2, with an error naming the note's `run:`, and writes no ledger
- AND once GitHub answers with the run, it exits 0

#### Scenario LEDGER.RUN.S6 [new]: check-close refuses an unconfirmed result as a note that doesn't match its run
- GIVEN a change whose every red and green is noted `result: pass`, one of those notes on a run that doesn't check out
- WHEN check-close runs
- THEN it fails, naming the scenario, the red or green and the merged commit, and saying the CI note there doesn't match its run on GitHub
- AND it doesn't say it is waiting for CI
- AND once that note's run checks out, it passes

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
