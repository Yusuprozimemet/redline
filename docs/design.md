# Redline design

Redline is a spec-driven, test-first development tool. Its core rule is that **a requirement isn't
real until a test has proved it can fail.**

It combines the lightweight, tool-agnostic spec layer of
[OpenSpec](https://github.com/Fission-AI/OpenSpec) (living behaviour specs that grow through
`ADDED/MODIFIED/REMOVED` deltas, written as Given/When/Then scenarios) with the discipline of the
migration engine (`../migration-engine`): `new`/`hold` criteria, checks broken on purpose, frozen
safety-net tests, independent auditors, evidence-backed closes, 400-line PRs and one session per
step. The new part is that **test-first is checked mechanically**, by CI and git history, instead
of being taken on the agent's word.

## 1. What goes wrong, and the mechanism against each

| What goes wrong | Source | Mechanism |
|---|---|---|
| The spec rests on a wrong premise | Most common defect cause in the engine (455 of its 475 defects were the agent's own) | Premises with `file:line` citations, checked by the auditor and CI |
| A check that can't fail | Engine | CI proves red (a strict expected failure on `main`); mutation proves `hold` |
| The agent claims test-first without doing it | OpenSpec trusts the agent | Evidence comes from CI, never from the agent |
| The agent reviews its own work and misses its own errors | Engine | Independent read-only auditor, always |
| PRs too big to review | Engine (the gate forced splits 46 times) | 400-line gate, always |
| Context bloat and drift | Engine (64% of tokens were read after a session passed 300k) | One session per step, always, with a generated brief |
| Gaps where work is handed between steps | Engine | Every deferred item gets an ID and an owning step; CI fails on any item without one |
| Safety-net tests weakened quietly | Engine | Frozen tests locked by hash; an edit needs a departure a person approves |
| Specs drift away from the code | OpenSpec | Every scenario is linked to a test, checked both ways |
| Verify can be ignored | OpenSpec | Verify blocks archiving and merging |

## 2. Seven invariants (always on, at every rigor level)

1. **The spec comes before the code.** No code PR exists without a merged spec for it.
2. **Red before green, proved on `main`.** A test for a `new` scenario lands as a *strict expected
   failure*, and CI confirms it really fails.
3. **Every PR is ≤ 400 changed lines.** Specs and tests count; lockfiles and generated files
   (declared in config) don't. An `Oversized: <reason>` line needs a person's approval label.
4. **One session per step.** A step is one PR. A merge ends the session.
5. **An independent audit before code.** A read-only agent in a fresh context, on the strongest
   model. If that model isn't available, the work stops; it never falls back to a weaker one.
6. **The CLI observes; the agent never certifies.** Evidence is whatever CI ran.
7. **Nothing is silent.** Every departure, waiver or deferral is a recorded line with an owner.

## 3. Units

```
Initiative  (optional)   plan.md: goal, phases, stopping points
  └─ Change              redline/changes/<id>/: proposal, delta spec, ledger
       └─ Step           ONE PR ≤ 400 lines = ONE session
```

## 4. Files

```
redline/
├── config.yaml                     # rigor default, generated-file globs, runner, rules
├── specs/<domain>/spec.md          # living behaviour; each scenario carries its ID
├── contracts/lock.yaml             # hashes of frozen `hold` tests
└── changes/<id>/
    ├── proposal.md                 # why, scope, non-goals, rigor level
    ├── specs/<domain>/delta.md     # ADDED/MODIFIED/REMOVED; scenarios tagged new | hold; premises
    ├── design.md                   # how (optional at lite)
    ├── steps.md                    # S, R, G1..Gn, C, and the scenario IDs each step owns
    ├── audit.md                    # auditor findings and their resolution
    └── ledger.yaml                 # a cache of evidence; CI rebuilds it and fails on a mismatch
```

A scenario:

```markdown
#### Scenario AUTH.2FA.S1 [new]: wrong code is rejected
- GIVEN a user with 2FA enrolled
- WHEN they submit an incorrect code
- THEN login fails AND no session is created
```

Premises:

```markdown
### Premises
- P1: Login issues a session in `auth/session.py:42` (`create_session`)
- P2: There is no 2FA check before `create_session` — `auth/login.py:18-35`
```

A test is linked to its scenario with a marker, e.g. `@pytest.mark.spec("AUTH.2FA.S1")`.

Steps, in order, with the scenarios each owns and the deferred items each step owns:

```markdown
## G1: Reject a wrong 2FA code
Owns: AUTH.2FA.S1

## Open items
- O1 [G2]: rate-limit repeated wrong codes
```

A step is named `<change>/<step>` (e.g. `add-2fa/G1`). It counts as merged on `main` when a commit
reachable from `main` carries the trailer `Redline-Step: add-2fa/G1`.

## 5. A change is always the same sequence of steps

| Step | PR contents | CI proves |
|---|---|---|
| **S: Spec** | Proposal and delta spec, with audit findings resolved | Structure is valid, every premise citation resolves, IDs are unique, every finding is closed or waived |
| **R: Red** | Linked tests: `new` as strict expected failures (`xfail(strict=True)`, Jest `test.failing`); `hold` added to the lock | Every `new` test fails on today's code; every `hold` test passes, then fails under mutation |
| **G1…Gn: Green** | Code that turns expected failures into passes | Owned scenarios pass with their markers removed, the lock is unchanged, nothing else regressed |
| **C: Close** | Verify report, delta merged into `specs/`, defect log, deferred items with owners | Every scenario has red, break (for `hold`) and green results from merged commits, and the red commit is an ancestor of the green one |

Red tests can merge onto `main` while CI stays green, because CI expects them to fail. A `new` test
that passes before the code exists turns CI red under strict expected-failure, so a check that
can't fail can't get in. Git history then records test-first as fact.

At **lite** rigor, S and R may share one PR, so the smallest change is two sessions.

## 6. Session protocol

```
redline start <step>   refuses unless the previous step is merged on main, the branch is fresh
                       from main, and no other step is open in this session (hook-enforced where
                       the AI tool allows) → prints the step brief
redline pr             runs the local gates (lines, lock, red/green), opens the PR, ends the step
redline merged         confirms the merge via git, syncs main, refreshes status, prints the
                       hand-off prompt for the next step → stop
```

`pr` runs check-lines always, and check-links and check-order from the R step on (at S the
delta's scenarios have no tests yet). Only when every gate passes does it put the `Redline-Step`
trailer on each of the step's commits (once), push, and open the PR with `gh`.

The brief (goal, owned scenario IDs, cited files, open items) is generated from the spec, the
ledger and the open items. It's the whole hand-off: a new session needs nothing from the old one.

## 7. Trust model

| Source | Counts as evidence? |
|---|---|
| CI run on a merged commit | Yes, and only this |
| CLI run locally | A preview, which CI re-runs |
| The agent's report or summary | Never |
| `ledger.yaml` | A cache, which CI rebuilds from history |

## 8. Rigor levels (on top of the invariants)

| Level | Adds |
|---|---|
| **lite** | Nothing; S and R may share one PR |
| **standard** (default) | Mutation testing on the touched files, and a defect log |
| **critical** | Frozen contract lock (timing included), one track per Green PR, a plan-auditor at the start and end of each phase, blind relabelling of defects, independent end-of-initiative auditors |

The proposal declares its level. The auditor may raise it (auth, payments, data migrations,
public APIs are critical) but never lower it.

## 9. Roles

| Role | Model | Can |
|---|---|---|
| Maintainer (a person) | — | Merge; approve waivers, departures, `Oversized` |
| Main session | Strong | Specs, briefs, review, breaks, PRs |
| Auditor | Strongest, fresh context | Read and report only |
| Implementer | Cheaper | Code from a brief; never commits |

The CLI holds the rules; each AI tool gets thin skills or commands, as in OpenSpec.

## 10. Learning loop

`redline retro` at each close groups the change's defects by cause and proposes rule changes to
`redline/config.yaml`, each as a normal small PR.

## 11. Build order (riskiest first)

1. **Red/green proof**: pytest plugin with `spec` markers and strict expected failures, plus the
   git-ancestry check (red commit is an ancestor of green). If this doesn't feel natural, the
   design changes.
2. 400-line gate; scenario-to-test linking both ways; `start`/`pr`/`merged` and the brief.
3. Premise citations and the auditor agent.
4. Ledger rebuilt by CI; GitHub Action.
5. Mutation (mutmut, then Stryker, PIT); contract lock; critical level.
6. Initiatives and plans; `retro`.

## 12. Open problems

- Scenarios that can't be automated (visual, timing): a recorded manual check with a reason,
  which the auditor may challenge.
- Mutation cost on large codebases: touched files only, at the Red step only.
- Whether a test asserts its scenario's THEN clauses is a judgment; the auditor checks it.
