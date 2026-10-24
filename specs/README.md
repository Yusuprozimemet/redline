# Specs

Redline's design, in detail, one file per section. [plan.md](../plan.md) is the big picture: what
Redline is and the order it is built in. These files are how each part works. Read the one a step
needs, not all of them.

Until 2026-10-24 this was one file, `docs/design.md`. Its text moved here unchanged, so a
citation of `docs/design.md, §N` (in the code, the tests, the workflows, a change's files and git
history) means the file numbered `NN` below, and §11, the build order, is in plan.md.

| § | File |
|---|---|
| 1 | [01-what-goes-wrong.md](01-what-goes-wrong.md) |
| 2 | [02-invariants.md](02-invariants.md) |
| 3 | [03-units.md](03-units.md) |
| 4 | [04-files.md](04-files.md) |
| 5 | [05-steps.md](05-steps.md) |
| 6 | [06-session-protocol.md](06-session-protocol.md) |
| 7 | [07-trust-model.md](07-trust-model.md) |
| 8 | [08-rigor-levels.md](08-rigor-levels.md) |
| 9 | [09-roles.md](09-roles.md) |
| 10 | [10-learning-loop.md](10-learning-loop.md) |
| 11 | [plan.md](../plan.md), Build order |
| 12 | [12-open-problems.md](12-open-problems.md) |

Beside them:

- [review-2026-10-20.md](review-2026-10-20.md): the whole-repository review, once fix.md, with
  where each item stands.
- [jev.md](jev.md): build 12's design, once jev-plan.md.

A new design section is a new numbered file here and a row above; a new build is a line in
plan.md's build order and its O-IDs in 12-open-problems.md, as before.
