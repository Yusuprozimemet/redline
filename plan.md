# Redline plan

Redline is a spec-driven, test-first development tool. Its core rule is that **a requirement isn't
real until a test has proved it can fail.**

It combines the lightweight, tool-agnostic spec layer of
[OpenSpec](https://github.com/Fission-AI/OpenSpec) (living behaviour specs that grow through
`ADDED/MODIFIED/REMOVED` deltas, written as Given/When/Then scenarios) with the discipline of the
migration engine (`../migration-engine`): `new`/`hold` criteria, checks broken on purpose, frozen
safety-net tests, independent auditors, evidence-backed closes, 400-line PRs and one session per
step. The new part is that **test-first is checked mechanically**, by CI and git history, instead
of being taken on the agent's word.

## Build order (riskiest first)

This is §11 of the design. Each build's detail is in [specs/](specs/README.md).

1. **Red/green proof**: pytest plugin with `spec` markers and strict expected failures, plus the
   git-ancestry check (red commit is an ancestor of green). If this doesn't feel natural, the
   design changes.
2. 400-line gate; scenario-to-test linking both ways; `start`/`pr`/`merged` and the brief.
3. Premise citations and the auditor agent.
4. Ledger rebuilt by CI; GitHub Action.
5. Mutation (mutmut, then Stryker); contract lock; critical level. Part 6 is the `Runner`
   seam and Jest's markers in the links, the order and the lock; part 7 proves the real Jest and
   Stryker on a toy project in CI (O-RUN5); part 8 runs Jest tests and Stryker in the gates
   (O-RUN1), and lets a departure name a Jest test with spaces (O-RUN7); part 9 runs Jest in the
   suite (O-RUN8).
6. Initiatives and plans (part 1); the defect log and `retro` (part 2). The rest of the
   critical level builds on phases: a plan-auditor at each phase's start and end,
   end-of-initiative auditors, one track per Green PR, blind relabelling. Part 6 is the
   plan-auditor; part 7 the end-of-initiative auditors (O-PLAN2); part 8 the plan's own level
   and the audited plan's version (O-PLAN1, O-PLAN3); part 9 the claims record (O-PLAN4); part
   10 a deleted plan (O-PLAN5); part 11 labels recorded at the merge (O-PLAN6); part 12 the
   claims of a change taken out of its plan (O-PLAN7).
7. **The close**: part 1 checks the C step against the ledger's evidence (O-CLOSE1); part 2
   checks that the delta reached `specs/` (O-CLOSE2); part 3 lets a closed change's delta stop
   counting as a declaration (O-CLOSE3); part 4 takes a change's evidence from its own steps only
   (O-CLOSE4); part 5 a closed change's lock entry when a later change edits its test (O-CLOSE5).
8. **More runners**, once Jest is complete and verified: JUnit 5 and PIT (O-RUN2); the critical
   `reach` of Jest and JUnit tests (O-RUN3); runner configuration that can weaken tests outside
   a step (O-RUN4); Jest tests outside the root `package.json` (O-RUN9); Jest files read with a
   JavaScript parser, regex literals included (O-MARK3).
9. **Fixes from the review of 2026-10-20**: part 1, a step's PR must be the change's next step
   (O-CI2); part 2, `start`'s phase and plan-audit refusals in CI (O-CI3); part 3, the config's
   `generated:` and `support:` read at the merge-base, a glob added to either a claim (O-CFG1);
   part 4, a change's level lowered is a claim (O-CI4); part 5, a pytest marker counts only as a
   decorator, read with Python's parser (O-MARK1); part 6, a Jest marker only in code, not in a
   comment or a string (O-MARK2); part 7, text read and printed as UTF-8 on Windows, a Windows CI
   job, and paths from git unquoted (O-ENC1, O-ENC2); part 8, mutmut with Redline's settings
   only and the scenario's tests copied, proved on the real mutmut in CI (O-MUT1, O-MUT2); part 9,
   the CI notes written by a job that runs no repository code, every other job read-only (O-CI5);
part 10, every merged commit's note, none lost to a cancelled run or a raced push (O-CI6); part
   11, the actions pinned to commits and the toolchain to versions (O-CI7, O-CI8); part 12,
   history read in a fixed number of git calls, not two a commit (O-PERF1); part 13, `steps.md`
   checked at every step, an open item without an ID or an owner a failure (O-STEPS1); part 14,
   `steps.md` compared with the merge-base, so no item or step leaves it silently (O-STEPS2); part
   15, every known limit given an O-ID and an owner or a reason it stays a judgment, and a
   scenario heading not in its form a failure (O-SPEC1); part 16, a `[manual]` scenario and its
   `Manual:` line (O-SPEC2); part 17, its check recorded at C as a claim (O-SPEC3); part 18, a
   requirement's prose and the text outside scenarios checked at C (O-CLOSE7); part 19,
   `redline/specs/` untouched before C (O-SPEC4); part 20, the toolchain pinned by hash, pip with it,
   and the runner images by version (O-CI9); part 21, a label counts only when applied after the
   PR's head was pushed, and issue events split on `"\t"` (O-APPR1, O-GH2); part 22, a departure's or
   a manual check's label applied by the person its trailer names (O-APPR2); part 23, the real
   `gh api` calls tested on this repository's own merged PR, and its reads retried (O-GH1, O-GH3);
   part 24, the README brought up to date, kept in step with the CLI by a test, and the
   repository settings Redline rests on listed in §7 (O-DOC1, O-SET1); part 25, `redline ci pr
   --python`, so the suite can test the PR's code while another Redline gates it (O-SELF2); part 26,
   each PR gated by the Redline at its merge-base (O-SELF3); part 27, Redline's own tree passing its
   gates (O-SELF5); part 28, a change's scenarios needing tests only from its R step on, in every
   change's gates (O-LINK1); part 29, the auditors on Opus at max effort when Fable isn't
   available, each audit naming its model (O-AUDIT1); part 29a, a change's audit rounds limited
   by its level, each after the first reading only what changed (O-AUDIT2); then the change `note-run`, Redline's first
   build step run as a change, S, R, G1 and C (O-NOTE1, O-SELF1); part 30, the change
   `install-workflow`, a workflow an adopting repository writes with `redline install workflow`,
   S, R, G1 and C (O-SELF4); part 31, the change `suite-job`, the PR's code run in a job of its own,
   apart from the gate, S, R, G1, G2 and C (O-CI10); part 32, the plan
   and end-of-initiative audits' rounds limited too (O-AUDIT3); part 35, a cited file in a
   package mutated in a copy of its whole package (O-MUT3), found by install-workflow/R's
   check-break and merged before that step; part 36, the URL a written workflow clones held to
   what a git URL needs (O-SELF6); part 37, an adopting repository's dependencies installed once for
   both jobs, and its gate kept apart from them on a push too (O-CI11).
   The review's other
   code items join this step, each with its own O-ID, as they are taken.
10. **Progress in `merged`** (O-PROG1), after build 9's encoding fix, since the bar prints `█`.
11. **Per-scenario outcomes from CI** (O-CLOSE6, the review's item 19): each linked test's
   outcome in the note, so red, green and a break are the scenario's own tests', not the suite's;
   and the note's text beyond its run's outcome (O-NOTE2), and evidence CI wrote whose run can no
   longer confirm it (O-NOTE3).
12. **Jev** ([specs/jev.md](specs/jev.md)), after build 11: an experiment, not a gate. Does an
   external decision service find the PRs that merit more scrutiny, at an acceptable review cost?
   An initiative, `redline/initiatives/jev/`, in two phases, shadow then advice.

## Specs

The plan says what gets built, in what order. The specs say how it works, in detail:

| Spec | What it holds |
|---|---|
| [01-what-goes-wrong.md](specs/01-what-goes-wrong.md) | §1: what goes wrong, and the mechanism against each |
| [02-invariants.md](specs/02-invariants.md) | §2: the seven invariants, at every rigor level |
| [03-units.md](specs/03-units.md) | §3: units: initiative, change, step |
| [04-files.md](specs/04-files.md) | §4: every file Redline reads and writes, and its form |
| [05-steps.md](specs/05-steps.md) | §5: a change's steps, S → R → G → C, and their gates |
| [06-session-protocol.md](specs/06-session-protocol.md) | §6: one session per step, the brief |
| [07-trust-model.md](specs/07-trust-model.md) | §7: CI as the only evidence, claims, approvals, repository settings |
| [08-rigor-levels.md](specs/08-rigor-levels.md) | §8: lite, standard, critical |
| [09-roles.md](specs/09-roles.md) | §9: main session, auditors, relabeller |
| [10-learning-loop.md](specs/10-learning-loop.md) | §10: the defect log and retro |
| [12-open-problems.md](specs/12-open-problems.md) | §12: judgments, and every O-item with its owning build |
| [review-2026-10-20.md](specs/review-2026-10-20.md) | the whole-repository review, its 20 items and where each stands |
| [jev.md](specs/jev.md) | build 12's design |

A change's own spec (proposal, deltas, steps) stays in `redline/changes/<id>/`, where the gates
read it.
