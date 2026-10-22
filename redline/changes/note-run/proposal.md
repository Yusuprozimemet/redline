# Proposal: note-run

Rigor: standard

## Why

A CI note is the evidence check-close reads (§7): `result: pass` on a merged commit is what makes
a red or a green count. A note is trusted because CI writes it, but anyone with the `write` role,
the agent's own account among them, can push `refs/notes/redline-ci`, which no ruleset covers, and
write `result: pass` or a `break:` map on any commit (O-NOTE1). The ledger reads such a note as if
CI had written it.

Redline's own PRs also run outside any step, so its red before green is a commit convention, not
evidence (O-SELF1). This change is the first of Redline's build steps run as a change, through
`start`, `pr` and `merged`, so it closes that too, at its C step.

## Scope

- The rebuild checks each note it reads: `ci_result` in `src/redline/ledger.py`, through a new
  `GitHub.push_run(url)` in `src/redline/pr.py`, which reads the run and its jobs from GitHub's
  Actions API. A note checks out when its `run:` is a run's URL, `…/actions/runs/<id>`, and the
  run gives that URL as its `html_url`, a `push` event, the noted commit as `head_sha`, `main` as
  `head_branch` and `.github/workflows/redline.yml` as `path`, and its `redline` job concluded
  `success` exactly when the note records no failure: `result: pass` and no failing `break:`
  entry. On 2026-10-22 run 39848744114, the push run of b41ea41, gave exactly those fields, and
  its `redline` job concluded `success`.
- A note that doesn't check out reads as a fourth result, `unconfirmed`: a run GitHub doesn't have
  (a 404, answered at once, with no retry), a `run:` that isn't a run's URL or is missing, and any
  field that differs. `fail` notes are checked too. Any other failure to read GitHub is an error
  naming the run.
- check-close refuses `unconfirmed`, saying the note doesn't match its run on GitHub, not that it
  is waiting.
- The workflow's `redline` and `runners` jobs get `actions: read`.
- Tests read GitHub through `FakeActions` in `tests/conftest.py`, autouse, which answers only the
  runs a test registers and a 404 for any other; `tests/test_github.py` reads run 39848744114 for
  real, under `REDLINE_REAL_GITHUB`, in the `runners` job.

A push run whose job failed only because the claims record couldn't read GitHub (§7) notes
`result: pass` beside a failed job, so it reads `unconfirmed` until the job is re-run. That is on
purpose: the note and its run disagree.

## Non-goals

- **The rest of a note's text.** A run that checks out confirms the note's outcome, not its
  `claims:` record, which whoever can push the ref can still rewrite, nor which `break:` entry
  failed when one did (O-NOTE2, build 11).
- **Notes older than this change.** A window starts at its change's S step (§4), and no change of
  Redline's own had one before this, so no ledger reads an older note: the check reads note-run's
  own R and G1 merges first. Its first CI run is the C PR's check-ledger and check-close, gated by
  G1's code at its merge-base.
- **Who can push the ref.** That is a repository setting (§7), and stays one.
- **Per-scenario outcomes** (O-CLOSE6, build 11).

## Steps

S (this spec), R (the tests and `FakeActions`), G1 (the code, the workflow's permission and the
real read), C (the delta into `redline/specs/ledger/spec.md`, O-SELF1 closed).
