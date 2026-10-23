# Proposal: install-workflow

Rigor: critical

## Why

A repository adopting Redline has no workflow to start from (O-SELF4). The README says to write
one that checks out the full history, runs `redline ci pr` and `redline ci push`, and hands the
note to a job that runs git alone, and points at `.github/workflows/redline.yml` as the model; but
that file is Redline's own. It installs the Redline its PR contains and gates with the
merge-base's, and runs `runners` and `windows`, which an adopter has none of. A note counts only
from a push run of `.github/workflows/redline.yml` whose `redline` job notes its own run's URL
(§4), so a hand-written workflow that differs in a name or a line writes notes that read
`unconfirmed`, and nothing says so until a C step fails.

## Scope

- `redline install workflow` writes `.github/workflows/redline.yml` from a template shipped in the
  package, `src/redline/helpers/redline.yml`, and prints `ok: wrote .github/workflows/redline.yml`.
- The written workflow installs the Redline that ran the command: the `url` and
  `vcs_info.commit_id` of the distribution's `direct_url.json` (PEP 610), which pip writes for an
  install from `redline @ git+<url>@<commit>`. It clones the URL into `$RUNNER_TEMP`, checks out
  the commit, and runs Redline's three hashed pip lines there, reading that commit's
  `requirements-pip.txt` and `requirements.txt`, with `.` not editable, on a push as on a PR. A
  comment after that step, outside its script, marks where the project installs its own
  dependencies, so a line added there doesn't run in Redline's clone.
- Every other line follows Redline's own workflow, every key at every level, the `redline` job's
  `name` and `if` among them, but for the merge-base's install, the editable install and the PR
  gate, which runs `redline ci pr --base main --pr ${{ github.event.pull_request.number }}` with
  `GH_TOKEN`, without `--python`. It has no `runners` or `windows` job.
- It refuses, exit 2, writing nothing: a Redline with no `direct_url.json`, or whose
  `direct_url.json` has no `vcs_info`, a `vcs` other than `git`, or a `commit_id` that isn't 40
  hex digits (an editable or local install, an index or archive URL); and an existing
  `.github/workflows/redline.yml`, left as it was.
- The workflow isn't one of `HELPERS`: a written one never equals the template, and may hold the
  project's own steps, so check-helpers doesn't read it; `redline install jest` still writes over
  its helper, check-helpers' remedy for an edited one.
- `pyproject.toml` ships `helpers/*.yml` beside `helpers/*.js`, which a test reads from the wheel
  the tree builds, since every suite runs on an editable install; the README's setup step 3 names
  the command, in place of "There is no workflow to copy yet".
- Tests set `direct_url.json` through a fake distribution, and compare the written workflow with
  Redline's own, parsed as YAML.

On 2026-10-23, `pip install --no-deps "redline @ git+https://github.com/Yusuprozimemet/redline@dea7b69"`
wrote `{"url": "https://github.com/Yusuprozimemet/redline", "vcs_info": {"commit_id":
"dea7b6981106798b773ae799e71a404488e5b33d", "requested_revision": "dea7b69", "vcs": "git"}}`, and
this checkout's editable install has `{"dir_info": {"editable": true}, "url": "file:///…"}`.

It is critical (§8, raised by the audit's F1): in an adopting repository the file it writes runs
every job that produces evidence, holds the token's permissions and the one `contents: write`,
and chooses the Redline that gates each PR; it widens a public command; and the first write
comes before CODEOWNERS in the README's setup order.

## Non-goals

- **Updating a written workflow.** The file is the repository's own once written; to move to
  another commit, reinstall, remove it and run the command again.
- **The project's own install, Node and Jest.** Those are the project's; the comment marks where.
- **The shared environment.** Redline and the project's dependencies share site-packages, so a
  dependency can replace a pin and the PR's code runs in the gate's job (O-CI10, part 31).
- **A commit no clone can fetch**, or a URL that later serves another history: the run fails
  where it is seen.

## Steps

S (this spec), R (the red tests), G1 (the command, the template, the package data and the README),
C (the delta into `redline/specs/install/spec.md`, O-SELF4 closed).
