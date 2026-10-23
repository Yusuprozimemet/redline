# Ledger

### Requirement: A CI note is checked against its run
The ledger reads a result or a break from a CI note only when the note's `run:` is a push run of
`.github/workflows/redline.yml` on `main`, in this repository, on the noted commit, whose `redline`
job concluded `success` exactly when the note records no failure. A failure is `result: fail`, or
a `break:` entry `fail` that names a `hold` scenario whose break the ledger reads from that note;
an entry for any other scenario counts for nothing. A break is read as its entry only from a
note that says `result: pass`, and as `fail` from one that says `result: fail`, entry or none.
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
- AND `result: fail` with the job's `failure` reads `fail`, and H's break `fail` whatever its entry says, or with none
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
