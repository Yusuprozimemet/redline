# Audit: suite-job
Model: claude-opus-5-5
Round: 1
Audited: e9f0f47895f986f62306e33d4bb74bd29308a87c

## F1 [open]: no scenario gives `ci pr --suite-result` a failing result or a failing gate at a step, so at a step the option could pass anything
At a step, S1 is the only scenario that gives `--suite-result`. It gives only `success`, to a PR that passes every gate (`redline/changes/suite-job/specs/ci/delta.md:13-16`), so its THEN (exit 0 and a line starting `ok:`) can't show that any gate ran. S2's THEN can show it (check-lines' failure beside `suite: the suite job's result is <result>`, `redline/changes/suite-job/specs/ci/delta.md:22-23`), but S2 runs only on a PR outside any step (`redline/changes/suite-job/specs/ci/delta.md:20`). Today these are two separate code paths, `step_pr` (`src/redline/ci.py:120-130`) and `outside` (`src/redline/ci.py:102-111`), and the option has to reach both. Suppose G1's `ci pr --suite-result` runs no gate at a step, or reads `failure`, `cancelled` or `skipped` as `success`. That G1 passes S1 to S4 and H1. Once G2 passes the suite job's result to the gate (`redline/changes/suite-job/specs/ci/delta.md:39`), every step PR, Redline's own included, would then pass the gate on a failed suite job.
Give S2 the step case: an R-step or G-step PR that fails a gate. With each of the three results it should print both failures and exit 1. With `success` it should fail on the gate alone.
H1 has the same gap (`redline/changes/suite-job/specs/ci/delta.md:42-45`): it holds `ci pr` without the option outside any step only. At an R step, check-break and the suite without the option (`src/redline/pr.py:229-230`, `src/redline/ci.py:128`) are in no scenario, though the proposal says `ci pr` without the option still "runs everything as before" (`redline/changes/suite-job/proposal.md:26-27`).

## F2 [open]: a run cancelled while `suite` runs leaves the required `redline` job unrun, and nothing says its check can't then read as passed
S4 gives the `redline` job `needs: suite` and `if: ${{ !cancelled() }}` (`redline/changes/suite-job/specs/ci/delta.md:38`). The reason given is that a skipped required check reads as passed, "so the `redline` job runs whatever `suite` concluded" (`redline/changes/suite-job/proposal.md:42-44`, `docs/design.md:1335-1337`).
That doesn't hold when the run itself is cancelled: `!cancelled()` is then false and the job never starts.
- Anyone with `write` can cancel a run at any point while the suite job runs, the agent's own account included (`docs/design.md:1813-1821`).
- `redline` is the one required check (`docs/design.md:1804-1809`).
- GitHub reports a job whose `if` is false as skipped, the result the proposal says branch protection reads as passed. What a cancelled run leaves for a job still waiting on `needs` is GitHub's behaviour; no premise states it and no scenario reaches it.
- Today's `redline` job has no `needs` and no `if` (`.github/workflows/redline.yml:20-29`), so a cancel leaves it cancelled, which is a failed check.
- S2's `cancelled` result (`redline/changes/suite-job/specs/ci/delta.md:21`) covers only a `suite` job that ends cancelled in a run that isn't.
- P8 is the precedent the delta cites (`redline/changes/suite-job/specs/ci/delta.md:55`). It says the `note` job "runs unless the run was cancelled", but its `if` also needs a push and a note (`.github/workflows/redline.yml:74`). So on a PR it never runs, and it isn't a required check.
The spec needs one of two things. It can state what the `redline` check reads after a cancelled run, and why that can't pass, as a premise or as a limit with an O-ID. Or it can make a passing check impossible, with a THEN for it: either a job condition under which the job runs and fails after a cancel, or `suite` required beside `redline` (`docs/design.md:1804-1809`). Either way, give P8 the `note` job's whole condition.

## F3 [open]: S4's last clause forbids the `redline ci push` step the change keeps
S4 ends with "no step of either job runs `pip install -e .` or `redline` outside those named here" (`redline/changes/suite-job/specs/ci/delta.md:40`). The steps S4 names are:
- the `suite` job's six (`redline/changes/suite-job/specs/ci/delta.md:37`);
- the `redline` job's editable install (`redline/changes/suite-job/specs/ci/delta.md:38`);
- the `redline` job's five steps that run on a pull request (`redline/changes/suite-job/specs/ci/delta.md:39`).
The `redline` job's push step runs `redline ci push` (`.github/workflows/redline.yml:62-66`). The proposal keeps that step unchanged (`redline/changes/suite-job/proposal.md:51-52`), but S4 doesn't name it. A test that reads the clause as written would fail on the workflow G2 must write. Name the push step, with its `if: github.event_name == 'push'`, among the steps that may run `redline`, or say which steps the clause covers.

## F4 [open]: no premise states the claim S1's "none of the PR's code" rests on: only check-break and the suite run the repository's code
S1 has `ci pr --suite-result success` load no `conftest.py` (`redline/changes/suite-job/specs/ci/delta.md:12-17`). The proposal's case is that, without check-break and the suite, `ci pr` runs none of the PR's code (`redline/changes/suite-job/proposal.md:23-26`). No premise says so. The claim holds today:
- The processes Redline starts are a runner's tests (`src/redline/runner.py:216`), called by the suite (`src/redline/ci.py:81`) and by check-break's unmutated run (`src/redline/breaks.py:206`).
- The others are mutmut and Stryker (`src/redline/breaks.py:118`, `src/redline/breaks.py:146`), git (`src/redline/order.py:36`, `src/redline/order.py:50`) and `gh` (`src/redline/pr.py:63`).
- `src/redline/merged.py:31` belongs to `merged`, not to a gate.
- Every YAML read is `safe_load` (for example `src/redline/config.py:37`, `src/redline/lock.py:45`), and `reach` reads tests with `ast` (`src/redline/reach.py:5`).
State the claim as a premise, with those citations.
S3 rests on two more claims that no premise cites:
- The step is worked out from the trailers of `main..HEAD`, and two steps are refused (`src/redline/ci.py:87-99`), which is printed as `refused:` with exit 1 (`src/redline/cli.py:459-461`).
- `--python` reaches the suite and check-break's unmutated run through `interpreter` and `pytest_command` (`src/redline/runner.py:183-198`).

## F5 [open]: nothing holds the proposal's "the gate reads only the result": the suite job's outputs, which the PR's code can write, could reach the gate
The proposal says the gate reads only the suite job's result (`redline/changes/suite-job/proposal.md:56`), and §7 says the gate "reads whether the job succeeded, not why" (`docs/design.md:1370-1371`). The PR's code runs in `suite` and can write to its steps' `$GITHUB_OUTPUT`. Suppose the job declared an output from one of those steps, and the `redline` job read it, as `note` reads `redline`'s output today (`.github/workflows/redline.yml:27-28`, `.github/workflows/redline.yml:92`). The PR's text would then reach the gate's step.
S4 doesn't check for this:
- It says the gate's `env` holds `SUITE` and `GH_TOKEN` (`redline/changes/suite-job/specs/ci/delta.md:39`), not those two alone.
- It says nothing of the `suite` job's `outputs`, of the `redline` job's own `env`, or of any other read of `needs.suite`.
Add a THEN with three parts: the `suite` job has no `outputs`; `needs.suite.result` is the only part of `needs.suite` the workflow reads; and the gate's `env` holds `SUITE` and `GH_TOKEN` alone.

## F6 [open]: four clauses pass without the behaviour they name, either on today's code or with a test that can't see it
- **S1's conftest clause.** "The `conftest.py`'s file isn't written" (`redline/changes/suite-job/specs/ci/delta.md:17`) is S1's point. It holds today, because argparse refuses the unknown option before anything runs (`src/redline/cli.py:103-111`). It also holds after G1 with a `conftest.py` that never writes. So the red proves nothing about it. Give it a control: on the same PRs, `redline ci pr --base main` without the option writes the file, since check-break's unmutated run and the suite both load it (`src/redline/breaks.py:206`, `src/redline/ci.py:81`).
- **S2's last clause.** It holds today (`redline/changes/suite-job/specs/ci/delta.md:24`): argparse exits 2 on an option `ci` doesn't have and on the event `suite` (`src/redline/cli.py:104`). Name the refusal's text, as `src/redline/cli.py:446` does for `--python`, so the clause fails today. §7 also says `ci suite` takes `--base` and `--python` alone (`docs/design.md:1350-1351`), and no clause holds that.
- **S3's "alone".** "On a PR outside any step whose tests pass, it runs the suite alone" (`redline/changes/suite-job/specs/ci/delta.md:31`) can't detect "alone" on a PR that passes every gate: a `ci suite` that ran every gate would pass it. Give that PR a failing gate, for example more than 400 changed lines, and keep exit 0.
- **S3's check-break at R.** S3 has `ci suite` run check-break at an R step (`redline/changes/suite-job/specs/ci/delta.md:27-29`) and never tests another step. A `ci suite` that ran it at every step passes S3. At an S step, where a `hold` scenario has no test yet, that would fail every such PR's suite job (`src/redline/breaks.py:243-246`). Add a step other than R, with no `check-break:` line.

## F7 [open]: "loses nothing" is false for two of check-break's refusals, which run no test
The proposal (`redline/changes/suite-job/proposal.md:41-42`) and §7 (`docs/design.md:1345-1346`) say that moving check-break out of the gate's job loses nothing, since a `conftest.py` can turn any test's outcome. Two of its refusals don't come from a test's outcome:
- a `hold` scenario that no test links without `new=True` (`src/redline/breaks.py:245-246`);
- premises that cite no file to mutate (`src/redline/breaks.py:236-237`).
No other gate of an R step refuses either one. check-links counts a `new=True` marker as a link (`src/redline/links.py:140-141`), and the lock takes only markers without it (`src/redline/breaks.py:194`, `src/redline/lock.py:90-95`). Under `--suite-result`, both refusals move into the suite job, whose result the PR's code decides, so the PR's code can get an R PR past them. After the merge, only the push run's check-break (`src/redline/ci.py:138-142`) and check-close at C still refuse them.
There are two ways to resolve this:
- Keep those two checks in `ci pr --suite-result` at R, with a THEN. Add `src/redline/breaks.py` to G1's `Track:` (`redline/changes/suite-job/steps.md:10`) if it must change.
- Or say in the proposal and §7 that they move, and that the push run's break and check-close still refuse them.

## F8 [open]: §5 and §7 still put the PR's install and suite in the `redline` job, against S4
S4 has the `redline` job, on a pull request, install only the merge-base's Redline and run `ci pr --suite-result` (`redline/changes/suite-job/specs/ci/delta.md:38-39`). The `suite` job runs both installs and the suite (`redline/changes/suite-job/specs/ci/delta.md:37`). The design text still says otherwise in four places:
- §7 says the `redline` job runs the pip lines twice, the gate's and then the PR's own (`docs/design.md:1614-1615`).
- §7 says the pin test has only `redline` run the gate's three lines first (`docs/design.md:1629-1630`).
- §7 says the installed-pins test runs with the suite in the `redline` and `windows` jobs (`docs/design.md:1637-1638`).
- §5 says the `redline` job runs check-order with the suite (`docs/design.md:992-994`).
The R and G sessions read §7 beside the delta, which is how install-workflow's D5 arose (`redline/changes/install-workflow/defects.md:37-44`). Bring these lines in line with S4, or give G2 an open item that names each one.

## F9 [open]: three wordings say less than meant, or something else
- **S1's GIVEN contradicts itself.** S1's R-step PR "passes every gate but holds a `hold` scenario whose test fails unmutated" (`redline/changes/suite-job/specs/ci/delta.md:13`). But check-break is one of an R step's gates (`src/redline/pr.py:229-230`), and it fails that scenario (`src/redline/breaks.py:247-248`). Say "every gate but check-break".
- **INSTALL.WF.S1 doesn't say which editable install.** It compares each install step's keys with "Redline's own editable install" (`redline/changes/suite-job/specs/install/delta.md:21`). After G2, Redline's own workflow has one editable install in `redline` and one in `suite` (`redline/changes/suite-job/specs/ci/delta.md:37-38`), and the test's helper takes the `redline` job's (`tests/test_install_workflow.py:70-72`). Say "the same job's".
- **The install delta's P3 cites the wrong range.** It cites `tests/test_install_workflow.py:86-95` for `core` taking out the PR gate's `run`. Line 86 is blank, and the `run` is taken out at `tests/test_install_workflow.py:96`, outside the range. Cite `tests/test_install_workflow.py:87-97`.
