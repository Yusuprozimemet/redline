# Proposal: note-recover
Rigor: critical

Own O-NOTE4: recover an absent CI note by a maintainer dispatch of main's workflow,
running the target commit's own `redline ci push`. This changes LEDGER.RUN explicitly;
a dispatch's workflow head is not the commit being tested. No inferred or handwritten result.

PR #100 (4e4e8ad) repaired future artifact transport only. G3 merged as
5e7c4ab4e767fb1f267cdcc01132b3eadb9b0b22; run 40218119783's redline job passed,
but its note job failed. Re-running it selects its old workflow and cannot repair transport.

Scope: an opt-in, main-only dispatch, missing-note eligibility, exact-target execution,
GitHub-backed run confirmation, isolated artifact writer, and real CI acceptance.
S specifies only; R supplies tests before implementation. No dispatch in S.
O-NOTE3 remains build 11's separately owned lost/deleted/renamed-run problem;
existing notes, even malformed/unconfirmed ones, cannot be replaced here.
O-NOTE2's note-content authenticity and O-REPORT1's held historical Jest evidence remain open.
No scenario-reports close, outcome consumer, automatic backfill, or relaxed push verification.
Design and matrix: design.md; normative changes: specs/ledger/delta.md and specs/ci/delta.md.
