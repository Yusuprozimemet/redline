# Design: note-recover

## Boundary and binding

Two revisions: W is the immutable workflow head selected by dispatch on refs/heads/main;
T is the supplied, exact lowercase 40-hex target. Both must be on main's first-parent line,
and T must be on W's first-parent line. A side-parent ancestor is insufficient.
Main may advance after dispatch; W need not remain its tip. Protected main and CODEOWNERS
on workflow/controller code remain the trust root (§7); this is not a signature over notes.

Use workflow_dispatch with one required string input target. Only that event enables recovery.
GitHub records job names `recovery-authorize/<T>`, `redline-recover/<T>` and `note-recover/<T>`
from the same inputs.target expression in main's reviewed workflow. The API's names, event,
workflow path and head SHA bind the run to T without trusting note text or an uploaded manifest.
An ordinary run title, outcome.commit, log line or note's claimed target cannot supply binding.
Validate exact full names, not prefixes. Require run_attempt == 1; a retry is a new dispatch,
not a rerun whose jobs/artifacts could belong to another attempt.

A read-only authorization job checks github.ref == refs/heads/main, W == github.workflow_sha
== github.sha, attempt 1, T's syntax and ancestry, and freshly fetched redline-ci note absence.
Any note object, even empty or malformed, means present. It checks both github.actor and
github.triggering_actor via the repository collaborator permission API: admin or maintain only.
A write role alone, bot, unknown actor, missing API data or API error refuses before target code.
The successful authorization job records that decision; ledger verification never re-judges
historical permission using a person's later role. Custom roles are not implicitly maintainers.
Its trusted T output is the only target used by checkout and writer; target code cannot edit it.
The job runs W's installed controller, never T's code; checkout has no persisted credentials.

The producer is a separate fresh hosted job after authorization, contents: read only (plus
actions/issues/pull-requests: read as needed), credentials disabled. Checkout detached T with
full history; set local main to T and fetch notes, so target code never reads W's future steps.
Verify HEAD == T before installation. Install T's hashed requirements and package, with pinned
workflow toolchains and the real Jest toy setup/REDLINE_REAL_RUNNERS=1 required for G3.
Run T's own `redline ci push --run-url <this-run> --note <file>` from T, no cherry-picks,
patches, main's Redline, changed new markers or --rev substitution. Unsupported old targets
fail explicitly without a note; a setup failure cannot be converted into test evidence.
The existing target program generates result/run/break/claims/outcomes as it does on push.
Upload its file even on a test/break failure; no continue-on-error hides that exit status.
Use artifact redline-recovery-note-<run-id>-1, overwrite false, one note file, missing-file error.
Only scalar readiness/target outputs cross jobs; note bytes never enter argv/env/job outputs.

The writer runs on another fresh hosted runner, only contents: write, using pinned checkout
and download actions and inline git/shell only. No repository script, Python import, package
install, local action or downloaded file executes there. Download this run's exact artifact;
attach its unchanged bytes to authorized T, never GITHUB_SHA (= W) or a target parsed from it.
Allow completed producer success/failure with a file; refuse skipped/cancelled/setup/no-file.
Re-fetch main and notes before every add/push, recheck T and W on main's first-parent line
and T on W's, then refuse any existing note. Use git notes add WITHOUT -f and non-force push.
Retry unrelated notes-ref races at most five times, refreshing/resetting local notes to remote
before retry; a same-target winner causes refusal, preserving both its bytes and other notes.
No notes ref is an empty namespace only after a successful remote fetch/list, never on error.
Recovery concurrency uses run id, cancel-in-progress false; it cannot cancel push/PR runs.
Guard ordinary redline/runners/windows/push-note paths off dispatch; PR and push gates stay intact.

## Ledger contract and residual limits

Keep push confirmation unchanged. For recovery require repository-local canonical URL/id,
event workflow_dispatch, head_branch main, exact .github/workflows/redline.yml path,
W/T ancestry above, attempt 1, successful completed authorization and writer jobs, and exactly
one completed producer job named for T. Its success/failure must agree with the existing
result/counted-break failure predicate; cancelled/skipped/timed_out/null never confirm.
Read all job pages for attempt 1, reject duplicate expected names and contradictory/missing
fields; do not collapse duplicates into today's name-to-conclusion map. Cache per run/rebuild.
Missing/404 metadata is unconfirmed; transient/non-404 errors use bounded existing retries,
then exit 2 without writing a ledger. A missing note remains unverified. Malformed note/result
keeps its existing error behavior. check-close continues to reject unconfirmed/unverified.
No artifact download is needed for future ledger confirmation; artifact expiry alone is harmless.

This proves a trusted workflow ran T and how its job ended, not the truth of every note field
(O-NOTE2). Recovery is a new execution at T, not a claim to recreate the original environment,
label timing, skipped test execution or original run. Claims are target ci push's current reads,
never described as merge-time observations; O-REPORT1 stays held pending its own review.
No recovery can overwrite an existing note or confirm missing/deleted GitHub runs (O-NOTE3).

## R matrix and implementation sequence

All distinct cases below land in R with strict-new markers; H1 passes and is mutation-proved.
Reuse Repo/FakeActions, note-run's ledger fixtures and the actual writer script harness.

| Scenario | Cases and observable checks |
|---|---|
| S1 authorize | admin/maintain accepted; write/read/bot/unknown/custom rejected; both actors; role 403/404/500; main ref/sha mismatch; missing attempt; rerun; hex length/case/metacharacters/ref/option; side-parent/unmerged/noncommit; existing valid/malformed/empty note; fetch failure; no target execution on refusal |
| S2 execute | W != T; T's interpreter/module and requirements, HEAD/main=T; exact ci push args; real Jest setup; target code has read token only; failed test/break retains exit/file; missing CLI/requirements/setup creates no evidence |
| S3 publish | correct T not W; unchanged >128 KiB/Unicode/shell-looking bytes; own artifact/name/attempt; file absence; cancelled/skipped producer; existing note on initial/retry check; same-target and unrelated races; five failures; no executable repository code in writer |
| S4 bind | valid W != T confirms; copy onto U fails; forged note target/outcome/title fails; wrong repository/URL/event/branch/path/head/job name; side-parent W/T; missing/duplicate/paginated jobs; attempt !=1; unsuccessful authorize/writer; producer cancelled/skipped/null/timeout; no recovery jobs on PR/push |
| S5 verdict | pass/success; fail/failure; counted failed break/failure; disagreement; uncounted break cannot explain failure; break fallback/missing; 404 vs exhausted 403/500; one read/run/rebuild; no ledger written on error; check-close rejects copied/unconfirmed note |
| S6 workflow | own/template parity, immutable actions/toolchains, no actions:write; only push/recovery writers write contents; no target execution in controller/writer; no persisted producer credentials; same-input API job names; dispatch concurrency and existing push/PR guards |
| H1 push | ordinary ci push --note still emits result/run/break/claims/outcomes without adding/pushing a git note, failed suites included |
| LEDGER.RUN.S2 | original rejection matrix stays, dispatch lacking full recovery proof rejects, valid recovery accepted |

The S ledger is a generated pre-window cache; LEDGER.RUN.S2's old history is not this change's
proof. Once S merges, its own window replaces that history; R must establish a fresh red.
G1 adds metadata reader and confirmation predicate, with no dispatch enabled. G2 adds the
trusted validator/CLI and read-only producer to own/template workflows; writer absent so no
recovery note can publish yet. G3 adds isolated writer and enables complete handoff. Each
removes only its owned new markers. R estimated 330-390 counted lines including ledger/lock;
G1/G2/G3 each <=400. Stop and revise split before any over-limit PR; never trim matrix cases.
S structural negative: replace an Owns ID temporarily, see check-steps refuse, restore.

## Real CI acceptance before C

After G3 merges, the maintainer separately authorizes dispatches; none is authorized by S.
First capture a real dispatch's raw run and attempt-jobs API responses with the read-only
Actions token: exact full target job names, W versus T, status/conclusions and role endpoint.
No production acceptance until the proposed binding is observed in GitHub, not just fakes.
Record refusal runs for side-parent/invalid target, existing note and rerun; no note may change.
Use disposable first-parent fixture commits for fail/break and contention cases; never destroy
real notes to make fixtures. Run the actual writer race harness and >128 KiB payload in CI.
Then, only if still absent and separately authorized, dispatch T=5e7c4ab4e767fb1f267cdcc01132b3eadb9b0b22.
Save URL/id/W/T/attempt, authorization role evidence, target checkout/install/ci-push logs,
actual Jest per-case execution, producer exit, artifact digest/download comparison and writer
success. Fetch remote notes afresh, compare note bytes, and rebuild scenario-reports' ledger
with implemented main verifier: its G3 green must name that merged T and become confirmed pass.
Also prove a copy onto a different commit fails using an isolated clone/fixture, never live notes.
A failed/partial run is recorded honestly and blocks acceptance; do not infer missing outcomes.
C requires this record plus note-recover's own merged red/green/break evidence, defect log and
independent relabel. It publishes deltas and documentation (§4/§7/run recovery limitations),
updates O-NOTE4's status and stops before scenario-reports/C or scenario-outcomes.

Sources: [dispatch SHA/ref](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_dispatch),
[job names and inputs](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax).
