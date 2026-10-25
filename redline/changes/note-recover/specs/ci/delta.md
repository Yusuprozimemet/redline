## ADDED Requirements
### Requirement: A maintainer can recover only an absent first-parent note

#### Scenario NOTE.RECOVER.S1 [new]: authorize a main-only exact target before target execution
- GIVEN main's redline.yml receives workflow_dispatch with required string target T
- WHEN a separate read-only controller validates the request
- THEN it accepts only refs/heads/main, workflow_sha == sha == W, attempt 1, both actors admin/maintain, lowercase full 40-hex T on W's and main's first-parent line, W on main's first-parent line, and no redline-ci note object on T
- AND it freshly fetches main/notes; any fetch/API failure, absent permission, other ref/role/attempt, malformed/noncommit/side-parent target or existing note refuses before target code runs
- AND its target output alone supplies execution/writing targets; a note or producer output cannot change them

#### Scenario NOTE.RECOVER.S2 [new]: execute the target's own push program
- GIVEN S1 authorized W and T
- WHEN a separate fresh read-only hosted producer executes recovery
- THEN its detached HEAD and local main are T; it installs T's pinned requirements/package and invokes T's own redline ci push --run-url this-run --note file
- AND its workflow sets up real Jest/REDLINE_REAL_RUNNERS as required for G3, without patching T or importing W's Redline
- AND failing tests/breaks retain their failing exit and generated file; setup/unsupported-target/no-file failures produce no evidence
- AND it uploads the file even after test failure, as this run/attempt's unique immutable artifact, never note bytes in argv/env/job outputs

#### Scenario NOTE.RECOVER.S3 [new]: publish unchanged bytes without replacing evidence
- GIVEN S1 succeeded, the producer completed success/failure and supplied its note artifact
- WHEN a separate isolated writer downloads this run/attempt's exact artifact
- THEN git attaches its unchanged bytes to authorized T, never workflow head W or an artifact-supplied target
- AND before every non-force add/push it freshly fetches main/notes, rechecks first-parent eligibility and refuses any existing note including empty/malformed notes
- AND a same-target racing note stays unchanged; unrelated notes survive refreshed retries, which stop with failure after five rejected pushes
- AND skipped/cancelled/setup/no-file producers never publish, and >128 KiB, Unicode or shell-looking note bytes remain data

#### Scenario NOTE.RECOVER.S6 [new]: workflow binding and permission isolation are structural
- GIVEN Redline's own and installed workflows
- WHEN their recovery jobs are inspected
- THEN the required API job names recovery-authorize/T, redline-recover/T and note-recover/T use the same dispatch target expression, as design.md defines
- AND authorization runs W's controller; producer runs T; only push/recovery writers hold contents write and neither runs repository code
- AND other jobs are contents read with credentials disabled, no job holds actions write, and actions/toolchains stay pinned
- AND dispatch uses a unique uncancelled concurrency group; ordinary PR/push jobs cannot execute on dispatch and their existing gates and note transport remain intact

#### Scenario NOTE.RECOVER.H1 [hold]: ordinary push file production stays read-only
- GIVEN ordinary ci push --note file with a passing or failing suite, and an R merge with breaks/claims
- WHEN it finishes
- THEN the file retains result/run/break/claims/outcomes and its exit verdict, while no git note is added or pushed

### Premises
- P1: Current workflow enables push/PR only and has separate read-only producer and file writer: `.github/workflows/redline.yml:4-8`, `.github/workflows/redline.yml:129-181`.
- P2: The current producer supports --note, records suite/break/claims/outcomes, and returns without git writes: `src/redline/ci.py:168-206` (`ci_push`, `push_note`).
- P3: Writer tests execute its actual git script, including races and large note files: `tests/test_ci.py:408-466`; installer compares own/template core: `tests/test_install_workflow.py:91-106`, `tests/test_install_workflow.py:149`.
- P4: Maintainer roles are exactly admin/maintain and role lookup uses the collaborator API: `src/redline/approval.py:26`, `src/redline/pr.py:149-150` (`role`).
