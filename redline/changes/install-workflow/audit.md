# Audit: install-workflow
Model: claude-opus-5-5
Round: 2
Audited: 4b84a11b02db031ee2b5d33021eb41b307fd609c

## F1 [closed]: rigor `standard` is too low: the change widens a public command and writes every adopting repository's CI, token handling included; raise it to `critical`
Resolution: `redline/changes/install-workflow/proposal.md:3` says `Rigor: critical`, with its reasons at `redline/changes/install-workflow/proposal.md:50-53`. `redline/changes/install-workflow/steps.md:18` gives C the blind relabel as O4, and the brief's limit is 3.

## F2 [closed]: no THEN checks that the package ships the template, and the only installs the command accepts need it shipped
Resolution: INSTALL.WF.S5 (`redline/changes/install-workflow/specs/install/delta.md:41-44`) builds the wheel from the tree and checks that it holds `redline/helpers/redline.yml`, equal to the template. It fails today: `src/redline/helpers/` holds only `jest.js`, and `pyproject.toml:22` ships only `helpers/*.js`. R and G1 own it (`redline/changes/install-workflow/steps.md:6`, `redline/changes/install-workflow/steps.md:9`).

## F3 [closed]: S1 and S2 don't say when the install step runs: a PR-only install passes both, and every push run is left without Redline or a note
Resolution: S1 says the install step has no `if`, and that its keys other than `name` and `run` are those of the editable install, which has none (`redline/changes/install-workflow/specs/install/delta.md:18`, `.github/workflows/redline.yml:52-55`). It also puts the comment on the line after the step's script, at the steps' own indentation and outside every `run` (`redline/changes/install-workflow/specs/install/delta.md:20`). The proposal and §7 say the same (`redline/changes/install-workflow/proposal.md:24-26`, `docs/design.md:1344-1345`).

## F4 [closed]: no THEN keeps check-helpers off the written workflow, or keeps `install jest` writing over an edited helper
Resolution: P8 cites `check_helpers` and both of its callers (`redline/changes/install-workflow/specs/install/delta.md:58`). S1's last THEN has check-helpers report nothing for the written workflow, both as written and with a step added (`redline/changes/install-workflow/specs/install/delta.md:21`). INSTALL.WF.H1 `[hold]` (`redline/changes/install-workflow/specs/install/delta.md:46-49`) has `redline install jest` write over an edited helper, which today's code does (`src/redline/runner.py:224-227`, `src/redline/cli.py:114-116`).

## F5 [closed]: §7 says the test compares the workflow "line for line", but S2 compares it parsed as YAML
Resolution: §7 now says the test compares both files parsed as YAML, comments aside (`docs/design.md:1349-1350`).

## F6 [open]: S2 compares four of the `redline` job's keys, not the whole job: a `name:` on the job, or a job-level `if` that skips it on a push, passes S1 and S2, and the adopting repository's notes then read `unconfirmed` or are never written
S2 compares the `redline` job's `runs-on`, `permissions`, `outputs` and steps (`redline/changes/install-workflow/specs/install/delta.md:26`). At the top level it compares only `on`, `permissions` and `concurrency` (`redline/changes/install-workflow/specs/install/delta.md:25`). Those are the keys Redline's own job and workflow have today. No THEN compares a key that only the template has, or one that Redline's own workflow gains later.

Two such keys break the adopting repository's evidence:
- A `name:` on the `redline` job. GitHub lists a job by its key only when it has no `name:` (`redline/changes/note-run/specs/ledger/delta.md:94`, `.github/workflows/redline.yml:20`). The ledger keys a run's jobs by that listed name (`src/redline/pr.py:105`) and reads `unconfirmed` when no job is named `redline` (`src/redline/ledger.py:63`). The proposal's own reason for the change is a workflow that "differs in a name" (`redline/changes/install-workflow/proposal.md:12-14`).
- `if: github.event_name == 'pull_request'` on the job. A push run then skips the job, and the `note` job, which needs it, never runs (`.github/workflows/redline.yml:73-74`). The new THEN says the install "runs on a push as on a PR" (`redline/changes/install-workflow/specs/install/delta.md:18`), but it checks only the step's `if`.

The requirement says the `redline` job is Redline's own outside the install and the PR gate (`redline/changes/install-workflow/specs/install/delta.md:7-9`). §7 says the test fails on "a change to Redline's workflow that an adopter needs" (`docs/design.md:1349-1351`). S2 checks neither claim. A job-level `env`, `defaults` or `timeout-minutes` that Redline's own job gains passes it, and so does a top-level `env` or `defaults`.

S2 should compare the two documents whole once the known differences are taken out: the `runners` and `windows` jobs, the merge-base's install, the install step and the PR gate's `run`. Then the `redline` job's `name` and `if` are compared too, along with any key either file gains.
