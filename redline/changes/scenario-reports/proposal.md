# Proposal: scenario-reports

Rigor: critical

## Why

Suite success does not say which linked tests executed. Produce explicit execution reports
before scenario-outcomes consumes them in ledger, close and PR gates.

## Scope

Versioned reports from pytest and Jest, expected and observed identities, strict-red semantics,
completeness, and report transport in push CI notes. No initiative.
Critical because these reports supply the execution claims later consumed by evidence gates.

## Non-goals

Ledger/close enforcement, PR execution checks and O-CLOSE6 closure belong to scenario-outcomes,
which starts only after this C is merged and the maintainer approves it. O-NOTE2/O-NOTE3 remain
deferred; no signing keys, attestation integration, recovery or legacy backfill.
