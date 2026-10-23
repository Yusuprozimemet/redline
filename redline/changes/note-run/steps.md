# Steps: note-run

## S: A CI note is checked against its run

## R: Red tests for a note checked against its run
Owns: LEDGER.RUN.S1, LEDGER.RUN.S2, LEDGER.RUN.S3, LEDGER.RUN.S4, LEDGER.RUN.S5, LEDGER.RUN.S6, LEDGER.RUN.S7

## G1: Check each CI note against its push run on GitHub
Owns: LEDGER.RUN.S1, LEDGER.RUN.S2, LEDGER.RUN.S3, LEDGER.RUN.S4, LEDGER.RUN.S5, LEDGER.RUN.S6, LEDGER.RUN.S7
Track: src/redline/ledger.py, src/redline/pr.py, src/redline/close.py, .github/workflows/redline.yml, docs/design.md, README.md

## C: Close note-run

## Open items
- O1 [R]: `FakeActions` in tests/conftest.py, autouse, answering only the runs a test registers and a 404 for any other, and leaves the real reads of tests/test_github.py to GitHub
- O2 [G1]: `actions: read` for the redline and runners jobs, a registered run for each note the existing tests write, and run 39848744114 and a run GitHub doesn't have read for real in tests/test_github.py
- O3 [G1]: close O-NOTE1 in docs/design.md §12
- O5 [G1]: the README's Install and CI sections say a ledger is now rebuilt with `gh` and a token that can read the Actions API, and that a note checks out only from a push run of `.github/workflows/redline.yml` whose `redline` job runs `redline ci push` with `--run-url` its own run's URL
- O4 [C]: close O-SELF1 in docs/design.md §12, and say in the README's "How Redline is built" that its build steps now run as changes
- O6 [C]: relabel.yaml from the redline-relabeller, now that note-run is critical
