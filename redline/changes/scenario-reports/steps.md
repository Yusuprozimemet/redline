# Steps: scenario-reports

## S: Specify report production and its trust boundary

## R: Add the complete report test matrix and held regressions
Owns: REPORT.PY.S1, REPORT.PY.S2, REPORT.PY.S3, REPORT.JS.S1, REPORT.JS.S2, REPORT.ALL.S1, REPORT.CI.S1, REPORT.CI.H1, REPORT.CI.H2

## G1: Produce pytest reports
Owns: REPORT.PY.S1, REPORT.PY.S2, REPORT.PY.S3
Track: src/redline/plugin.py, src/redline/runner.py, src/redline/reports.py, README.md

## G2: Produce Jest reports
Owns: REPORT.JS.S1, REPORT.JS.S2, REPORT.ALL.S1
Track: src/redline/helpers/jest.js, src/redline/helpers/jest-reporter.js, src/redline/runner.py, src/redline/reports.py, pyproject.toml, README.md

## G3: Carry reports in push CI notes
Owns: REPORT.CI.S1
Track: src/redline/ci.py, src/redline/runner.py, src/redline/reports.py, README.md

## C: Publish the report contract and stop before its consumer

## Open items
- O1 [R]: add every case in design.md's R matrix, ledger and two critical holds within 400 lines
- O2 [G1]: prove real pytest phase, parameter and xdist reports; missing workers stay incomplete
- O3 [G2]: prove real Jest helper/test.failing behavior and package/install the reporter
- O4 [G3]: prove complete and partial reports survive the existing isolated note handoff
- O5 [C]: apply the delta, rebuild merged evidence and record defects; leave O-CLOSE6 open
- O6 [C]: use only the maintainer-approved relabel-waiver trailer and matching fresh personal label
- O7 [C]: stop for inspection of report production and actual CI; scenario-outcomes needs approval
- O8 [R]: maintainer must resolve O-REPORT1 before crediting Jest evidence; it owns real-Jest evidence-job integration (F2)
- O9 [C]: defer to maintainer at scenario-outcomes/S; O-REPORT2 owns bounded transport and its scenario (F10)
- O10 [C]: defer to maintainer at ci-apart-python/S; O-REPORT3 owns stale CI.APART.S2 and its red/green (F12)
