# Design: scenario-reports

## Production boundary

S -> R -> G1 pytest -> G2 Jest -> G3 CI note -> C. Critical, no initiative. All R tests land
together; G steps remove their owned new markers after separate red and implementation commits.
Each complete PR, including audit, ledger and lock, stays at most 400 changed lines.

Reports describe execution; existing ledger/close rules and PR job-result gating stay in force
through this C. O-CLOSE6/review item 19 stays open for scenario-outcomes. That change must require
both today's run-confirmed passing suite AND qualifying complete per-scenario outcomes, retain
repository/commit/workflow/event/job checks, ancestry, owning step, change window and R-only
hold-break provenance, and never let detailed passes override suite/break inconsistency.

No legacy note is rewritten or given inferred outcomes. Reports begin with the producer's
deployment, including active changes' subsequent runs. Missing/unknown-version detail is legacy
or unavailable, never a fabricated pass. Consumer activation is the merged scenario-outcomes S:
changes already closed before that boundary retain historical closure; new or still-active
changes must obtain fresh qualifying proof inside their own evidence windows. That consumer
selects the first qualifying merged red and later qualifying green, with ancestry, rather than
crediting the first marker transition. This boundary grants no close enforcement in A.

## Report v1

Add `outcomes` to the push note: `version: 1`, `commit` (full merged SHA), `complete` (boolean),
`expected`, `observed`, `scenarios`, and `diagnostics`. Lists are sorted, serialization is UTF-8
with LF, and identities retain Unicode and case; normalize path separators only, never basename
or test-name matching. Every identity includes runner and repository-relative path. Pytest uses
full node ID including class and parameter ID; Jest uses file, full describe/test title and
parameter instance. Duplicate titles/parameter IDs that cannot be distinguished are diagnosed.

`expected` records each linked logical test at the snapshot, scenario IDs and new/hold state,
plus its independently collected concrete instances. Declaration kind comes from that snapshot's
specs/deltas; `new` is the execution marker, not the declaration tag. Source links provide a
floor even when a file is never collected. Full discovery before selection supplies parameter
instances; an unavailable expansion is incomplete, never an empty passing set.

`observed` records concrete identity, links and marker states, runner phases, terminal outcome
and strict-new provenance. Outcomes are `pass`, `expected-failure`, `unexpected-pass`, `skip`,
`deselected`, `error`, or `missing`; aborted runs also carry an abort diagnostic. `diagnostics`
contains code, identity (or runner) and reason. Missing, extra, duplicate, conflicting, malformed
and unsupported records have distinct diagnostics. No last-writer-wins or silent deduplication.

`scenarios` maps each ID to expected/observed identities, `complete`, and `red`, `green` or
`nonqualifying`. Red needs every required instance to be a strict-new assertion failure in the
test body, with successful setup/teardown; green needs every instance to execute and pass with
new removed and without unrelated xfail. An empty set, mixed new/hold execution links, or any
nonqualifying instance cannot yield red/green. A test linked to several scenarios must satisfy
each; mixed marker states on that test produce a diagnostic. Global complete requires completed
discovery and execution of every expected instance with no identity/protocol errors. A complete
failed execution can be nonqualifying; skips, deselection and missing phases are incomplete.

## Collector and transport seams

Use per-invocation temporary report paths passed by runner.py to pytest's plugin and the shipped
Jest helper/reporter. Normal test commands and scenario filtering keep their current meaning;
mutation and filtered check-break runs cannot overwrite the full suite report. No stale report
from a previous invocation is reused. ci push combines all configured runners against the same
snapshot. Missing runner/report, collection failure or partial output stays visible and incomplete.

Pytest joins setup/call/teardown and verifies the added strict-new mark caused an assertion xfail.
Setup/teardown xfail, arbitrary exceptions, unrelated or overridden xfail and collection errors
are never red. Collect expected instances before filters; compare them with source links and
post-filter execution. xdist uses the controller's expected worker set and collection manifests;
agreeing duplicate worker inventories are allowed, duplicate execution records are not. A lost
worker, divergent inventory or missing parameter is incomplete regardless of other passes.

Jest reports the helper's explicit link/new state and body assertion outcome alongside the real
test.failing result. Generic Jest `passed` cannot establish red. Unexpected test.failing success,
hook failure, pending/skip, omitted file or unresolved parameter identity is nonqualifying.
The installed helper/reporter remains package data checked by check-helpers, not user-editable
configuration trusted by the gate. Tests exercise real frameworks, not just synthetic payloads.

ci push appends the report for successful and failed/partial suites without replacing result,
run, break or claims. Existing suite failures remain failures; collection/protocol errors fail
report production and CI. Legitimate skips can retain today's suite success while outcomes stay
incomplete/nonqualifying. Report detail alone is never run confirmation. Preserve --python and
restore interpreter state on errors. The existing read-only producer writes --note; the existing
writer transports those bytes with git alone, including failed-run notes. No workflow trigger,
permission or PR handoff change is needed here; cancellation may leave no note, never proof.

## R sizing checkpoint (A only, before delta)

Rechecked against pytester in tests/test_plugin.py, real Jest toy/jest in tests/test_runners.py,
Repo/FakeActions, ci/remote and r_step/logging_python in the CI fixtures. Reuse setup, parameterize
shared assertions and keep distinct diagnostics observable. No production helper is added in R.

| Group / scenarios | Required distinct cases | Changed lines |
|---|---|---|
| Pytest S1-S3 | assertion strict-xfail, pass, xpass, skip, deselect, uncollected/missing, setup/teardown error/xfail, unrelated xfail, parameters, xdist/lost worker, Unicode/path | 90-105 |
| Jest S1-S2 | real test.failing red/xpass, normal green, hook error, pending/skip, omitted file, duplicate/parameter identity, explicit new provenance | 65-75 |
| ALL.S1 | all tests/parameters, mixed runners and markers, duplicate/conflict/extra, aborted/partial/malformed reports | 35-40 |
| CI.S1, H1-H2 | complete/partial notes, version/old fields, no failure upgrade, project Python/path, separate writer and unchanged suite/run acceptance | 40-45 |
| Imports/setup/links | reuse fixtures, decorators, compact report builders and held assertions | 30-35 |
| Ledger | nine rows with red/green/break null slots and header/change/map | 36-44 |
| Critical hold lock | two held invariants with test/reach hashes, including mapping keys | 9-11 |
| Total | complete R diff, additions plus deletions | 305-355 |

Reserve: 45 lines at upper estimate. Estimates are not measured test evidence. Do not remove
cases, move tests into G, rewrite frozen tests or widen generated/support globs to fit. Stop for
a revised split if the concrete R exceeds 400. Size S/C too; audit counts against S's reserve.
Deliberate breaks in isolated toys: credit setup-xfail, drop worker/parameter, accept Jest xpass,
omit a linked test with suite exit zero, strip report at note handoff. Each targeted test must
fail, then restore. S uses an invalid-ownership structural negative, with no production mutation.

## Audit and closure ownership

At audit preparation, stop. The maintainer runs a fresh Claude session on unchanged
`redline audit-brief scenario-reports`; that session writes its reply unedited to this branch's
audit.md and commits it. Pull that commit before continuing. Codex never writes/edits audit.md
or relabel.yaml and launches no auditor/relabeller. Keep the critical round limit; resolution
requires the maintainer's recorded audit, never Codex's declaration. Open the S PR only after it
is resolved, verify remote head equals local HEAD, then stop.

C uses `Redline-Relabel: waived-by @Yusuprozimemet: <maintainer-approved reason>` only after the
maintainer approves the reason and personally applies the matching fresh label after final push.
No waiver is granted now. O-NOTE2/O-NOTE3 and attestation research remain later work; no signing
keys or recovery. C records report production only and stops for maintainer inspection/approval.
