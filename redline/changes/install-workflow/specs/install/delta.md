## ADDED Requirements

### Requirement: An adopting repository's workflow installs the commit Redline was installed from
`redline install workflow` writes `.github/workflows/redline.yml` from the template the package
ships. The workflow clones the `url` of the running Redline's `direct_url.json` and checks out its
`vcs_info.commit_id`, then installs that tree with Redline's three hashed pip lines, not editable.
Outside that install and the PR gate, which runs `redline ci pr --base main --pr <n>` without
`--python`, its triggers, default permissions, concurrency, `redline` job and `note` job are
Redline's own workflow's, and it has no other job. The package ships the template, and
check-helpers never reads the written workflow. With no git commit to install, or with the file
already there, it writes nothing and exits 2; `redline install jest` still writes over its helper.

#### Scenario INSTALL.WF.S1 [new]: the workflow installs the commit Redline was installed from
- GIVEN a Redline whose `direct_url.json` gives a `url`, `vcs` `git` and a 40-digit `commit_id`
- WHEN `redline install workflow --repo <repo>` runs in a repository with no `.github/workflows/redline.yml`
- THEN it exits 0, prints `ok: wrote .github/workflows/redline.yml` and writes that file
- AND the `redline` job's install step clones that `url` into `$RUNNER_TEMP`, checks out that `commit_id` there, and runs the three pip lines of Redline's own workflow with `.` in place of `-e .`
- AND the install step has no `if`, so it runs on a push as on a PR, and its keys other than `name` and `run` are those of Redline's own editable install
- AND no step before it runs anything but the checkout, the fetch of `main` and the notes, and setup-python
- AND the line after the install step's script is a comment that marks where the project installs its own dependencies, at the steps' own indentation, outside every step's `run`
- AND check-helpers reports nothing, with the written workflow as it is and with a step added to it

#### Scenario INSTALL.WF.S2 [new]: the workflow is Redline's own outside the install and the PR gate
- GIVEN the workflow written as in INSTALL.WF.S1, and Redline's own `.github/workflows/redline.yml`, both parsed as YAML
- THEN `on`, `permissions`, `concurrency` and the `note` job are equal
- AND the `redline` job's `runs-on`, `permissions` and `outputs` are equal, and its steps are Redline's own in order, without the merge-base's install, with the install of INSTALL.WF.S1 in place of the editable install, and the PR gate's `run` `redline ci pr --base main --pr ${{ github.event.pull_request.number }}`, with its `if` and `env` as Redline's own
- AND its jobs are `redline` and `note` alone

#### Scenario INSTALL.WF.S3 [new]: a Redline with no git commit to install writes nothing
- GIVEN a Redline with no `direct_url.json`, or one with `dir_info` and no `vcs_info`, or `vcs` `hg`, or a `commit_id` of `dea7b69`
- WHEN `redline install workflow` runs
- THEN it exits 2 and says Redline wasn't installed from a git commit, naming `pip install "redline @ git+<url>@<commit>"`, in each case
- AND no `.github/workflows/redline.yml` is written

#### Scenario INSTALL.WF.S4 [new]: an existing workflow file is left as it was
- GIVEN a Redline installed from a git commit, as in INSTALL.WF.S1
- AND a repository whose `.github/workflows/redline.yml` exists
- WHEN `redline install workflow` runs
- THEN it exits 2, naming the file, and the file's bytes are unchanged

#### Scenario INSTALL.WF.S5 [new]: the wheel built from the tree ships the template
- GIVEN Redline's own tree
- WHEN `pip wheel --no-deps --no-build-isolation --no-index` builds it
- THEN the wheel holds `redline/helpers/redline.yml`, equal to `src/redline/helpers/redline.yml`

#### Scenario INSTALL.WF.H1 [hold]: `redline install jest` writes over an edited helper
- GIVEN a repository whose `redline/runners/jest.js` differs from the helper Redline ships
- WHEN `redline install jest` runs
- THEN it exits 0 and the file is the shipped helper, and check-helpers reports nothing

### Premises
- P1: `redline install` takes only a runner named in `HELPERS` and writes its helper, over an existing file — `src/redline/runner.py:224-227` (`write_bytes`), `src/redline/cli.py:91-92` (`HELPERS`)
- P2: The package ships only `helpers/*.js` as data — `pyproject.toml:22` (`helpers/*.js`)
- P3: A note checks out only from a push run whose `path` is `.github/workflows/redline.yml`, with a job named `redline` — `src/redline/ledger.py:61-64` (`.github/workflows/redline.yml`)
- P4: Redline's own workflow installs the merge-base's Redline before the PR's, then its own editable, and gates the PR with `--python` — `.github/workflows/redline.yml:43-59` (`--python`)
- P5: Redline's own workflow runs a `runners` and a `windows` job beside `redline` and `note` — `.github/workflows/redline.yml:94` (`runners:`), `.github/workflows/redline.yml:127` (`windows:`)
- P6: The README installs Redline from a git commit, and says there is no workflow to copy yet — `README.md:23` (`git+https`), `README.md:57` (`O-SELF4`)
- P8: check-helpers compares each of `HELPERS`' files that exists with the shipped copy, and says to run `redline install <name>`, on every step's PR and every PR outside one — `src/redline/runner.py:230-234` (`check_helpers`), `src/redline/pr.py:216` (`check_helpers`), `src/redline/ci.py:108` (`check_helpers`)
- P9: Redline's own editable install step has no `if`, and the push step after it runs `redline` — `.github/workflows/redline.yml:52-55` (`-e .`), `.github/workflows/redline.yml:64` (`redline ci push`)
- P7: The workflow tests read Redline's own workflow file alone — `tests/test_ci.py:17` (`WORKFLOW`)
