## MODIFIED Requirements
### Requirement: A CI note is checked against its run
The ledger accepts the original push proof or the complete recovery proof in NOTE.RECOVER.S4,
never a dispatch merely because its job succeeded. Push proof remains a repository-local run
of .github/workflows/redline.yml on main with head_sha equal to the noted commit and a redline
job whose outcome agrees with result and counted breaks, as in LEDGER.RUN.S1/S3.
All existing malformed-note, API-error, missing-run and break-result rules remain in force.

#### Scenario LEDGER.RUN.S2 [new]: another event, branch, workflow or repository needs complete recovery proof
- GIVEN a note and a run that otherwise satisfy LEDGER.RUN.S1
- WHEN its event is pull_request or an unsupported event, its branch/path/URL/repository differs, or it is workflow_dispatch without all NOTE.RECOVER.S4 proof
- THEN its result is unconfirmed in each case, including a dispatch whose head_sha equals the noted commit
- AND the unchanged push case still passes, and only a fully confirmed recovery dispatch can additionally pass

## ADDED Requirements
### Requirement: Recovery evidence binds a main workflow run to the tested target

#### Scenario NOTE.RECOVER.S4 [new]: GitHub records the exact target independently of the note
- GIVEN a note on T naming a canonical run URL in this repository
- AND GitHub reports workflow_dispatch on main at W, path .github/workflows/redline.yml, run_attempt 1
- AND T and W are on main's first-parent line, with T on W's first-parent line
- AND attempt 1 has exactly one completed recovery-authorize/T and note-recover/T job, both success, and exactly one completed redline-recover/T job
- WHEN the ledger checks the note
- THEN it uses that producer's success/failure only if it agrees with the existing result/counted-break predicate
- AND copying that note to U != T, changing only its claimed target/outcome/title, or missing/duplicating/changing any required identity, status or proof makes it unconfirmed
- AND skipped/cancelled/timed_out/null producer conclusions or unsuccessful authorization/writing never confirm

#### Scenario NOTE.RECOVER.S5 [new]: recovery preserves verdict and API failure semantics
- GIVEN a recovery run satisfying S4's identities
- WHEN its producer succeeds with no counted failure, or fails with result fail or a counted failed break
- THEN the suite result and break results are read exactly as LEDGER.RUN.S3 specifies
- AND a disagreement, including an uncounted break offered to explain failure, is unconfirmed
- AND GitHub reads every attempt-job page, refuses ambiguous duplicates, and caches each run per rebuild
- AND 404/missing proof is unconfirmed; exhausted non-404 errors exit 2 without writing a ledger
- AND check-close refuses unconfirmed/unverified evidence, while malformed notes keep LEDGER.RUN.S5's error

### Premises
- P1: Current confirmation requires push/head_sha identity; failure includes only counted breaks: `src/redline/ledger.py:40-72` (`ci_result`).
- P2: GitHub currently reads one jobs page into a lossy name map and caches by run id: `src/redline/pr.py:92-107` (`push_run`).
- P3: Existing negative/outcome fixtures cover event/identity/disagreement and real API calls: `tests/test_note_run.py:95-200`, `tests/test_github.py:53-58`.
