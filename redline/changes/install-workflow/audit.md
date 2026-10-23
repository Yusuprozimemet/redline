# Audit: install-workflow
Model: claude-opus-5-5
Round: 3
Audited: 9df4e98edc9d72000485b21bde90e1c8129f0dcb

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

## F6 [closed]: S2 compares four of the `redline` job's keys, not the whole job: a `name:` on the job, or a job-level `if` that skips it on a push, passes S1 and S2, and the adopting repository's notes then read `unconfirmed` or are never written
Resolution: S2 now takes the `runners` and `windows` jobs, the merge-base's install, the install step and the PR gate's `run` out of both files, then requires the two documents to be equal whole, every key at every level, including the `redline` job's `name` and `if` (`redline/changes/install-workflow/specs/install/delta.md:25-26`). Redline's own `redline` job has neither key (`.github/workflows/redline.yml:20-29`). So a `name:` or an `if:` on the template's job fails S2, and so does any key either file gains at any level, such as an `env` or `defaults` on a job or on the workflow. S2 still checks where the install step sits and what the PR gate's `run` is (`redline/changes/install-workflow/specs/install/delta.md:27`). The proposal and §7 say the same (`redline/changes/install-workflow/proposal.md:27-30`, `docs/design.md:1349-1352`).
