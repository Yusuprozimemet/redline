# Steps: install-workflow

## S: An adopting repository's workflow, written by `redline install workflow`

## R: Red tests for the workflow `redline install workflow` writes
Owns: INSTALL.WF.S1, INSTALL.WF.S2, INSTALL.WF.S3, INSTALL.WF.S4, INSTALL.WF.S5, INSTALL.WF.H1

## G1: Write an adopting repository's workflow from the commit Redline was installed from
Owns: INSTALL.WF.S1, INSTALL.WF.S2, INSTALL.WF.S3, INSTALL.WF.S4, INSTALL.WF.S5, INSTALL.WF.H1
Track: src/redline/runner.py, src/redline/cli.py, src/redline/helpers/redline.yml, pyproject.toml, README.md, docs/design.md

## C: Close install-workflow

## Open items
- O1 [R]: a fake distribution in the tests, giving `direct_url.json` as each test sets it
- O2 [G1]: `helpers/*.yml` in pyproject.toml's package data, and the README's setup step 3 naming `redline install workflow`
- O3 [C]: close O-SELF4 in docs/design.md §12
- O4 [C]: relabel.yaml from the redline-relabeller, since install-workflow is critical
