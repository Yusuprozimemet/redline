## ADDED Requirements

### Requirement: Complete execution reports accompany suite results

Produce report v1 as defined in `redline/changes/scenario-reports/design.md`: expected identities and concrete
instances, observed phases/outcomes and marker provenance, scenario aggregates and diagnostics.
Every required instance must qualify; no any-one-pass aggregation. Skipped, deselected,
uncollected, aborted, missing, conflicting and unexpected-pass results never prove red/green.
Unknown/absent report versions remain legacy/unavailable; never backfill from suite success.
This change produces reports only. Ledger, check-close and PR execution enforcement belong to
scenario-outcomes; O-CLOSE6 remains open. Positive evidence there must require today's
run-confirmed passing suite AND complete qualifying per-scenario outcomes in the change window,
preserving ancestry, owning steps and R-only hold/break provenance and suite/break consistency.

Per-test outcomes, like the suite result, come from a job running the PR's code. The PR-gate
execution check catches accidental skips caused by deselection, configuration or conftest hooks;
it does not protect against a hostile PR, whose code can forge reports or change test outcomes.
That execution check is future consumer behavior. Retain job isolation: the gate must not import
or execute PR code to obtain reports. Writable notes can forge detail; O-NOTE2/O-NOTE3 remain
deferred. No authentication, signing keys or recovery guarantee is introduced.

#### Scenario REPORT.PY.S1 [new]: pytest distinguishes strict body assertion failure from other outcomes
- GIVEN real linked pytest tests with strict-new, ordinary, skip and unrelated xfail states
- WHEN their setup, call and teardown phases execute with pass, assertion failure, xpass or error
- THEN only strict-new body assertion failure with successful setup/teardown qualifies as red
- AND only normal execution/pass without new or unrelated xfail qualifies as green
- AND setup/teardown failure or xfail, unrelated xfail and unexpected pass have distinct nonqualifying records

#### Scenario REPORT.PY.S2 [new]: pytest reports every expected test and parameter instance
- GIVEN snapshot links, Unicode paths and class/parameter identities, including files outside collection
- WHEN collection or selection omits a file/test/parameter, or tests skip or collection fails
- THEN expected and observed identities remain distinct and stable with runner and full relative node ID
- AND missing, skip, deselection and collection-error diagnostics keep affected scenarios incomplete
- AND executing all instances qualifies only if every instance qualifies

#### Scenario REPORT.PY.S3 [new]: parallel pytest aggregation requires every worker's execution
- GIVEN real xdist workers with collected parameter inventories and linked tests
- WHEN all workers complete, or one worker/result/parameter is missing or inventories disagree
- THEN complete execution merges deterministically without duplicating expected instances
- AND missing workers/parameters, conflicting inventories and duplicate execution are diagnosed, never credited

#### Scenario REPORT.JS.S1 [new]: real Jest strict-new provenance distinguishes red from generic success
- GIVEN the shipped helper/reporter and real Jest test.failing with linked new and ordinary tests
- WHEN a body assertion fails, unexpectedly passes, passes normally, or a hook fails
- THEN explicit helper new state and body outcome distinguish strict red, green, unexpected-pass and error
- AND a generic passed count, unrelated failing test or hook error never establishes red

#### Scenario REPORT.JS.S2 [new]: Jest inventory detects skipped, omitted and ambiguous identities
- GIVEN linked files, nested titles and parameterized tests, including duplicate identities
- WHEN Jest skips/pends a test, omits a file or cannot resolve one concrete instance uniquely
- THEN expected/observed runner, relative file, full title and parameter identities expose the omission
- AND missing, skip/pending and duplicate/ambiguous diagnostics keep affected scenarios nonqualifying

#### Scenario REPORT.ALL.S1 [new]: scenario completeness spans every linked test and runner
- GIVEN several linked tests/parameters in pytest and Jest for one scenario, including mixed marker states
- WHEN reports are complete, partial, aborted, malformed, conflicting, duplicated or contain extra identities
- THEN red/green requires every expected instance with consistent marker state to qualify and none missing
- AND empty sets and mixed new/hold links never qualify; each other invalid case has its own diagnostic
- AND deterministic versioned aggregates retain the offending identities rather than overwriting them

#### Scenario REPORT.CI.S1 [new]: push notes carry the current report, including failed and partial runs
- GIVEN ci push, configured runners and a project interpreter, with successful, failed or partial execution
- WHEN it writes --note or adds the note directly, including after a prior report exists
- THEN outcomes v1 names this merged SHA and preserves expected/observed detail and diagnostics
- AND result, run, break and claims retain their existing meanings; passing detail never upgrades failure
- AND missing/malformed reports produce incomplete diagnostics and production failure, never stale evidence
- AND legitimate skip-only suite success has incomplete/nonqualifying detail, not per-scenario success
- AND the existing failed-note handoff preserves the full report and interpreter selection is restored on error

#### Scenario REPORT.CI.H1 [hold]: the existing suite and run-confirmation requirements still hold
- GIVEN suite failure or a note with an unavailable, wrong or unconfirmed run, and optional passing detail
- WHEN the current suite and ledger CI-result checks run
- THEN failure remains failure and unavailable/wrong run confirmation cannot become passing evidence
- AND report production does not replace today's ledger, close, window or R-only break rules

#### Scenario REPORT.CI.H2 [hold]: only the isolated note writer writes notes and runs no project code
- GIVEN the current workflow and its failed-note handoff
- WHEN its jobs, permissions and note-writer commands are checked
- THEN the read-only producer hands note bytes to the sole writer, which runs git alone
- AND PR code stays outside the gate job; workflow triggers and PR job-result handoff remain unchanged

### Premises
- P1: pytest currently adds strict xfail during collection and filters by scenario; it records no phases - `src/redline/plugin.py:25-42` (`pytest_collection_modifyitems`)
- P2: Jest helper uses test.failing and can skip by REDLINE_SPEC - `src/redline/helpers/jest.js:7-23` (`test.failing`)
- P3: runner source scanning supplies links, while run launches the framework - `src/redline/runner.py:51-55` (`markers`), `src/redline/runner.py:213-216` (`run`)
- P4: suite currently uses only runner exit results - `src/redline/ci.py:70-84` (`suite`)
- P5: push notes preserve result/run, R breaks and claims, with a file-only route - `src/redline/ci.py:162-188` (`message`)
- P6: ledger retains run checks and owning-change windows - `src/redline/ledger.py:44-68` (`ci_result`), `src/redline/ledger.py:78-126` (`rebuild`)
- P7: the note handoff carries failed runs and its writer runs git alone - `.github/workflows/redline.yml:106-131` (`note`)
