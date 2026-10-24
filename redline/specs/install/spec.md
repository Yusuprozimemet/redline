# Install

### Requirement: An adopting repository's workflow installs the commit Redline was installed from
`redline install workflow` writes `.github/workflows/redline.yml` from the template the package
ships. The workflow's `redline` and `suite` jobs each clone the `url` of the running Redline's
`direct_url.json` and check out its `vcs_info.commit_id`, then install that tree with Redline's
three hashed pip lines, not editable; a comment after each install marks where the project
installs its own dependencies, in the `redline` job on a push alone. Outside those installs, the
PR gate, which runs `redline ci pr --base main --pr <n> --suite-result "$SUITE"`, and the suite
job's `redline ci suite --base main`, both without `--python`, its triggers, default permissions,
concurrency, `redline`, `suite` and `note` jobs are Redline's own workflow's, and it has no other
job. The package ships the template, and check-helpers never reads the written workflow. With no
git commit to install, or with the file already there, it writes nothing and exits 2;
`redline install jest` still writes over its helper.

#### Scenario INSTALL.WF.S1 [new]: the workflow installs the commit Redline was installed from
- GIVEN a Redline whose `direct_url.json` gives a `url`, `vcs` `git` and a 40-digit `commit_id`
- WHEN `redline install workflow --repo <repo>` runs in a repository with no `.github/workflows/redline.yml`
- THEN it exits 0, prints `ok: wrote .github/workflows/redline.yml` and writes that file
- AND the `redline` and `suite` jobs each have one install step, which clones that `url` into `$RUNNER_TEMP`, checks out that `commit_id` there, and runs the three pip lines of Redline's own workflow with `.` in place of `-e .`
- AND the `redline` job's install step has no `if`, so it runs on a push as on a PR, and each install step's keys other than `name`, `run` and `if` are those of the editable install in the same job of Redline's own workflow
- AND in each job no step before the install runs anything but the checkout, the fetch of `main` and the notes, and setup-python
- AND the line after each install step's script is a comment that marks where the project installs its own dependencies, at the steps' own indentation, outside every step's `run`, and the `redline` job's names `if: github.event_name == 'push'`
- AND check-helpers reports nothing, with the written workflow as it is and with a step added to it

#### Scenario INSTALL.WF.S2 [new]: the workflow is Redline's own outside the installs, the PR gate and the suite
- GIVEN the workflow written as in INSTALL.WF.S1, and Redline's own `.github/workflows/redline.yml`, both parsed as YAML
- WHEN the `runners` and `windows` jobs, and in the `redline` and `suite` jobs the merge-base's install, the install steps and the `run` of the steps that run `ci pr` and `ci suite`, are taken out of both
- THEN the two documents are equal whole, every key at every level, the `redline` and `suite` jobs' `name`, `if` and `needs` among them
- AND each written install step sits in its job where Redline's own editable install does, its PR gate's `run` is `redline ci pr --base main --pr ${{ github.event.pull_request.number }} --suite-result "$SUITE"`, and its suite step's `run` is `redline ci suite --base main`
- AND its jobs are `suite`, `redline` and `note` alone, in that order

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
