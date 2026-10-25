# Design: scenario-reports

## Production boundary

S -> R -> G1 pytest -> G2 Jest -> G3 CI note -> C. Critical, no initiative. All R tests land
together; G steps remove their owned new markers after separate red and implementation commits.
Each complete PR, including audit, ledger and lock, stays at most 400 changed lines.

Reports describe execution; existing ledger/close rules and PR job-result gating stay in force
through this C. O-CLOSE6 stays open for scenario-outcomes; report consumers and their activation
rules are outside this change. No legacy note is rewritten or given inferred outcomes.
The normative v1 schema, qualification and diagnostics live in specs/reports/delta.md.

## Collector and transport seams

Use per-invocation temporary report paths passed by runner.py to pytest's plugin and the shipped
Jest helper/reporter. Normal test commands and scenario filtering keep their current meaning;
mutation and filtered check-break runs cannot overwrite the full suite report.
Bind the sink to the owning invocation/process and pytest session, not inherited environment or
module-global state alone. Nested in-process/subprocess runs get no access to the outer sink.
No stale report from a previous invocation is reused. ci push combines all configured runners against the same
snapshot. Missing runner/report, collection failure or partial output stays visible and incomplete.

Pytest joins setup/call/teardown and verifies Redline's strict-new mark caused a body xfail.
Any body failure qualifies with passing setup/teardown, including absent-code exceptions and
pytest's Failed; setup/teardown xfail, unrelated/overridden xfail and collection errors never do.
Collect expected instances before filters; compare them with source links and
post-filter execution. xdist uses the controller's expected worker set and collection manifests;
agreeing duplicate worker inventories are allowed, duplicate execution records are not. A lost
worker, divergent inventory or missing parameter is incomplete regardless of other passes.

Jest reports the helper's explicit link/new state and body outcome alongside the real
test.failing result; any body throw/rejection qualifies with passing hooks and new provenance.
Generic Jest `passed` cannot establish red. Unexpected test.failing success,
hook failure, pending/skip, omitted file or unresolved parameter identity is nonqualifying.
The installed helper/reporter remains package data checked by check-helpers, not user-editable
configuration trusted by the gate. Tests exercise real frameworks, not just synthetic payloads.

ci push appends the report for successful and failed/partial suites without replacing result,
run, break or claims. Existing suite failures remain failures. Report defects produce incomplete
diagnostics only; they do not add CI failures or alter ledger/check-close acceptance.
Legitimate skips can retain today's suite success while outcomes stay
incomplete/nonqualifying. Report detail alone is never run confirmation. Preserve --python and
restore interpreter state on errors. The existing read-only producer writes --note; the existing
writer transports those bytes with git alone, including failed-run notes. Transport sizing remains
deferred as O-REPORT2; no trigger,
permission or PR handoff change is specified here; cancellation may leave no note, never proof.

## R sizing checkpoint (A only, before delta)

Rechecked against pytester in tests/test_plugin.py, real Jest toy/jest in tests/test_runners.py,
Repo/FakeActions, ci/remote and r_step/logging_python in the CI fixtures. Reuse setup, parameterize
shared assertions and keep distinct diagnostics observable. No production helper is added in R.

| Group / scenarios | Required distinct cases | Changed lines |
|---|---|---|
| Pytest S1-S3 | body-failure strict-xfail (including absent code), pass, xpass, skip, deselect, uncollected/missing, setup/teardown error/xfail, unrelated xfail, parameters, xdist/lost worker, Unicode/path, nested runs | 90-105 |
| Jest S1-S2 | real test.failing red/xpass, normal green, hook error, pending/skip, omitted file, duplicate/parameter identity, source/runtime joins, nested runs, explicit new provenance | 65-75 |
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
requires the maintainer's recorded audit, never Codex's declaration. Do not open an S PR in this
fix pass; round 2 is the maintainer's call. Push the spec fixes and stop.

C uses `Redline-Relabel: waived-by @Yusuprozimemet: <maintainer-approved reason>` only after the
maintainer approves the reason and personally applies the matching fresh label after final push.
No waiver is granted now. O-NOTE2/O-NOTE3 and attestation research remain later work; no signing
keys or recovery. C records report production only and stops for maintainer inspection/approval.
