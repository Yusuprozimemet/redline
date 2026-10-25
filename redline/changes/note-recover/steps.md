# Steps: note-recover

## S: Specify maintainer recovery and its evidence boundary

## R: Add the complete recovery matrix and freeze push regressions
Owns: LEDGER.RUN.S2, NOTE.RECOVER.S1, NOTE.RECOVER.S2, NOTE.RECOVER.S3, NOTE.RECOVER.S4, NOTE.RECOVER.S5, NOTE.RECOVER.S6, NOTE.RECOVER.H1

## G1: Confirm recovery runs against GitHub target binding
Owns: LEDGER.RUN.S2, NOTE.RECOVER.S4, NOTE.RECOVER.S5
Track: src/redline/ledger.py, src/redline/pr.py, src/redline/recovery.py

## G2: Validate and execute the target through main's workflow
Owns: NOTE.RECOVER.S1, NOTE.RECOVER.S2
Track: src/redline/recovery.py, src/redline/cli.py, .github/workflows/redline.yml, src/redline/helpers/redline.yml, src/redline/runner.py

## G3: Publish absent notes with a race-safe isolated writer
Owns: NOTE.RECOVER.S3, NOTE.RECOVER.S6
Track: .github/workflows/redline.yml, src/redline/helpers/redline.yml, README.md

## C: Publish the contract after real recovery acceptance

## Open items
- O-NOTE4 [C]: finish the missing-note recovery contract and real CI acceptance before scenario-reports/C
- O1 [R]: implement every design matrix case within 400 lines, including ledger/critical hold lock; revise the split if it cannot fit
- O2 [G2]: keep installer parity; separate controller code from target code and prove actor-role reads with the Actions token
- O3 [G3]: retain large-file transport and ordinary push races; demonstrate real workflow job-name binding before relying on it
- O4 [C]: record the authorized G3 recovery URL, raw GitHub metadata, note and fresh ledger; no acceptance from local/fake runs
- O5 [C]: apply deltas, rebuild this change's ledger, record defects and independent blind relabel; leave O-NOTE3 with build 11
