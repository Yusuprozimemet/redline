# Steps: note-run

## S: A CI note is checked against its run

## R: Red tests for a note checked against its run
Owns: LEDGER.RUN.S1, LEDGER.RUN.S2, LEDGER.RUN.S3, LEDGER.RUN.S4, LEDGER.RUN.S5, LEDGER.RUN.S6

## G1: Check each CI note against its push run on GitHub
Owns: LEDGER.RUN.S1, LEDGER.RUN.S2, LEDGER.RUN.S3, LEDGER.RUN.S4, LEDGER.RUN.S5, LEDGER.RUN.S6
Track: src/redline/ledger.py, src/redline/pr.py, src/redline/close.py, .github/workflows/redline.yml, docs/design.md

## C: Close note-run

## Open items
- O1 [R]: `FakeActions` in tests/conftest.py, autouse, answering only the runs a test registers and a 404 for any other
- O2 [G1]: `actions: read` for the redline and runners jobs, a registered run for each note the existing tests write, and run 39848744114 read for real in tests/test_github.py
- O3 [G1]: close O-NOTE1 in docs/design.md §12
- O4 [C]: close O-SELF1 in docs/design.md §12, and say in the README's "How Redline is built" that its build steps now run as changes
