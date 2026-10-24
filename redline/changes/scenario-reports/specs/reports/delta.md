## ADDED Requirements

### Requirement: Complete execution reports accompany suite results

Produce report v1 in the push note's `outcomes:` mapping. Its fields are `version: 1`, `commit`
(full merged SHA), `complete` (boolean), `expected`, `observed`, `scenarios` and `diagnostics`.
Lists are sorted; serialization is UTF-8/LF. Identities preserve Unicode and case and normalize
only path separators. Each includes runner and repository-relative path: pytest's full node ID
(class and parameter ID included), or Jest's full describe/test title and parameter instance.
`expected` records snapshot logical source identities, scenario links, new/hold marker states,
declaration kinds from specs/deltas, and independently discovered concrete instances before selection.
Source links are a floor for uncollected files; unavailable expansion is incomplete, never empty success.
`observed` records concrete identity, links, marker states, runner phases, strict-new provenance and
one terminal outcome: `pass`, `expected-failure`, `unexpected-pass`, `skip`, `deselected`, `error`, `missing`.
`scenarios` maps IDs to expected/observed identities, `complete`, and `red`, `green` or `nonqualifying`.
`diagnostics` entries have `code`, `identity` (or `runner`) and `reason`; distinct codes are `missing`,
`extra`, `duplicate`, `conflicting`, `malformed`, `unsupported`, `skip`, `deselected`, `collection-error`,
`abort`, `missing-worker`, `inventory-conflict`, `ambiguous`, `empty`, `mixed-markers`, `missing-phase`.
Global completeness requires finished discovery and execution of all expected instances without
identity/protocol errors; skips, deselection and missing phases are incomplete. A complete failure
can be nonqualifying. Never silently deduplicate or overwrite conflicting records.
Every required instance must qualify; no any-one-pass aggregation. Skipped, deselected,
uncollected, aborted, missing, conflicting and unexpected-pass results never prove red/green.
For either runner red requires every instance's strict-new body failure with passing setup/teardown;
green requires every instance to execute and pass with new removed and no unrelated expected failure.
Empty sets and mixed new/hold links never qualify. Each scenario linked by a test must qualify separately.
This change produces reports only; report reading and the PR execution check belong to scenario-outcomes.

Per-test outcomes come from a job running project code, which can forge reports or test outcomes.
Writable notes can forge `outcomes:` (O-NOTE2); O-NOTE3 remains deferred. No authentication,
signing keys or recovery guarantee is introduced. Preserve existing job isolation.

#### Scenario REPORT.PY.S1 [new]: pytest distinguishes strict body failure from other outcomes
- GIVEN real linked pytest tests with strict-new, ordinary, skip and unrelated xfail states
- WHEN their setup, call and teardown phases execute with pass, body failure, xpass or error
- THEN any call-phase failure qualifies as red only when Redline's strict-new xfail caused expected failure and setup/teardown passed
- AND this includes AssertionError, ImportError, AttributeError, NameError, TypeError and pytest's Failed (fail or raises with nothing raised), so an R body testing absent code can be red
- AND only normal execution/pass without new or unrelated xfail qualifies as green
- AND setup/teardown failure or xfail, unrelated xfail and unexpected pass have distinct nonqualifying records

#### Scenario REPORT.PY.S2 [new]: pytest reports every expected test and parameter instance
- GIVEN snapshot links, Unicode paths and class/parameter identities, including files outside collection
- WHEN collection or selection omits a file/test/parameter, or tests skip or collection fails
- THEN expected and observed identities remain distinct and stable with runner and full relative node ID
- AND missing, skip, deselection and collection-error diagnostics keep affected scenarios incomplete
- AND executing all instances qualifies only if every instance qualifies
- AND nested Pytester in-process runs and subprocesses inheriting the environment neither append to nor truncate the outer report; their outcomes never enter it

#### Scenario REPORT.PY.S3 [new]: parallel pytest aggregation requires every worker's execution
- GIVEN real xdist workers with collected parameter inventories and linked tests
- WHEN all workers complete, or one worker/result/parameter is missing or inventories disagree
- THEN complete execution merges deterministically without duplicating expected instances
- AND missing workers/parameters, conflicting inventories and duplicate execution are diagnosed, never credited

#### Scenario REPORT.JS.S1 [new]: real Jest strict-new provenance distinguishes red from generic success
- GIVEN the shipped helper/reporter and real Jest test.failing with linked new and ordinary tests
- WHEN a body throws/rejects, unexpectedly passes, passes normally, or a hook fails
- THEN explicit helper new state and body outcome distinguish strict red, green, unexpected-pass and error
- AND any body throw/rejection (including TypeError for absent code at R) is red only with Redline new provenance, test.failing expected failure and successful setup/teardown hooks
- AND a generic passed count, unrelated failing test or hook error never establishes red

#### Scenario REPORT.JS.S2 [new]: Jest inventory detects skipped, omitted and ambiguous identities
- GIVEN linked files, escaped/Unicode source names, nested titles and parameterized tests, including runtime duplicate identities
- WHEN Jest skips/pends a test, omits a file or cannot resolve one concrete instance uniquely
- THEN expected/observed runner, relative file, full title and parameter identities expose the omission
- AND missing, skip/pending and duplicate/ambiguous diagnostics keep affected scenarios nonqualifying
- AND the source-to-runtime join below preserves escaped names and describe ancestry; a refused source file produces collection-error and an unavailable file inventory, never an empty floor
- AND nested Jest runs inheriting the environment cannot write or truncate the outer report or contribute outcomes to it

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
- AND missing reports produce missing diagnostics, malformed reports produce malformed diagnostics, each in a fresh valid v1 envelope with complete false; incomplete valid reports retain their diagnostics and complete false
- AND for each of those three cases with an otherwise passing suite, passing breaks and successful claims/note transport: result is pass, ci push exits 0, and a matching successful push run makes the ledger read pass (including passing R breaks)
- AND for each case with a failing suite and otherwise successful transport: result is fail, ci push exits 1, and a matching failed push run makes the ledger read fail (including R breaks)
- AND report defects alone add diagnostics, not CI failure; existing break/claims errors still exit 1 and existing run-confirmation rules still apply
- AND legitimate skip-only suite success has incomplete/nonqualifying detail, not per-scenario success
- AND both note routes preserve the current report, including after suite failure; no prior invocation's report is reused

#### Scenario REPORT.CI.H1 [hold]: the existing suite and run-confirmation requirements still hold
- GIVEN suite failure or a note with an unavailable, wrong or unconfirmed run, and optional outcomes detail
- WHEN the current suite and ledger CI-result checks run
- THEN failure remains failure and unavailable/wrong run confirmation cannot become passing evidence
- AND rebuilding the ledger and running check-close give identical results with and without outcomes, including missing, malformed and incomplete detail, owning-change windows and R-only breaks
- AND result, run, break and claims keep their meanings: result comes from suite exit status before break/claims failures are added; passing detail never upgrades failure
- AND after interpreter-selected success or error, the next invocation uses the original interpreter

#### Scenario REPORT.CI.H2 [hold]: the producer file and direct note routes preserve the isolated handoff
- GIVEN the isolated workflow note writer, successful/failed suites and a stubbed git/remote seam
- WHEN ci push writes --note, and those bytes pass through the writer's base64 handoff into git notes
- THEN the note read back equals the producer file byte for byte, including result/run/break/claims, for either suite result
- AND the direct ci push route adds the same note bytes and pushes refs/notes/redline-ci; the file route calls neither notes add nor push

### Premises
- P1: pytest currently adds strict xfail during collection and filters by scenario; it records no phases - `src/redline/plugin.py:25-42` (`pytest_collection_modifyitems`)
- P2: Jest helper uses test.failing and can skip by REDLINE_SPEC - `src/redline/helpers/jest.js:7-23` (`test.failing`)
- P3: runner source scanning supplies links, while run launches the framework - `src/redline/runner.py:51-55` (`markers`), `src/redline/runner.py:213-216` (`run`)
- P3a: Jest scanning keeps raw quoted names without describe ancestry and refuses duplicate source names - `src/redline/runner.py:164-180` (`jest_tests`).
  The report producer must join by repository-relative file and source registration location
  (line/column), rather than title equality: helper registration binds the location to its decoded
  runtime title/describe ancestry and parameter instances. Preserve raw source identity alongside
  runtime identity; unresolved/ambiguous joins are incomplete. Scanner refusal retains a file-level
  unavailable-inventory floor and collection-error, globally incomplete even if links cannot be recovered.
- P4: suite currently uses only runner exit results - `src/redline/ci.py:74-88` (`suite`)
- P5: push notes preserve result/run, R breaks and claims, with a file-only route - `src/redline/ci.py:162-188` (`push_note`)
- P6: ledger retains run checks and owning-change windows - `src/redline/ledger.py:44-68` (`ci_result`), `src/redline/ledger.py:78-126` (`rebuild`)
- P7: the note handoff carries failed runs and its writer runs git alone - `.github/workflows/redline.yml:106-131` (`note`)
