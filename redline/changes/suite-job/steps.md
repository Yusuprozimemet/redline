# Steps: suite-job

## S: A PR's code run in a job of its own, apart from the gate

## R: Red tests for `ci suite`, `ci pr --suite-result` and the two workflows' `suite` job
Owns: CI.APART.S1, CI.APART.S2, CI.APART.S3, CI.APART.S4, CI.APART.S5, CI.APART.H1, INSTALL.WF.S1, INSTALL.WF.S2

## G1: `redline ci suite` runs the PR's code, and `redline ci pr --suite-result` runs the rest
Owns: CI.APART.S1, CI.APART.S2, CI.APART.S3, CI.APART.S5
Track: src/redline/ci.py, src/redline/pr.py, src/redline/breaks.py, src/redline/cli.py, README.md, specs/07-trust-model.md

## G2: A `suite` job in Redline's own workflow and in the template, and a `redline` job that runs no PR code
Owns: CI.APART.S4, INSTALL.WF.S1, INSTALL.WF.S2
Track: .github/workflows/redline.yml, src/redline/helpers/redline.yml, README.md, specs/07-trust-model.md

## C: Close suite-job

## Open items
- O1 [G1]: the README's command table names `redline ci pr|suite|push`
- O2 [G2]: the README's setup step 3 names the `suite` job and the two comments that mark the project's install
- O3 [C]: close O-CI10 in specs/12-open-problems.md (§12)
- O4 [C]: relabel.yaml from the redline-relabeller, since suite-job is critical
- O5 [R]: CI.APART.S4's tests take over the four that pin today's workflow: `tests/test_pins.py:68` expects five `python-version` and `node-version` values, `:73` five jobs, `:80-81` pip lines in `redline`, `suite`, `runners` and `windows`; `tests/test_ci.py:235-243` keeps the `cd` before `python -m venv` (PR #81), in both jobs, and expects the gate's `run` ending `--suite-result "$SUITE"`
