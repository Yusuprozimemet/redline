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

A citation is a backquoted `file:line` or `file:first-last` from the repository root, optionally
followed by a symbol in brackets. `redline check-premises` checks that the file exists, the lines
are within it, and the symbol is on them; a premise with no citation fails too.

Audit findings, written by the auditor only (closing a finding is a re-audit, never the main
session's word); a waiver names the person who approved it:

```markdown
## F1 [open]: P2 is wrong; `auth/login.py:30` already calls `verify_code`
## F2 [closed]: P1 cited the wrong line
Resolution: P1 now cites `auth/session.py:42`
## F3 [waived]: no test for the lockout timing
Waived-by: @maintainer: timing is a manual check (O2)
```

`pr` at S refuses if `audit.md` is missing, or any finding is `[open]`, a `[closed]` one has no
`Resolution:` or a `[waived]` one has no `Waived-by:`.

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

The ledger has one entry for each scenario the change's deltas declare:

```yaml
change: add-2fa
scenarios:
  AUTH.2FA.S1:
    red: {commit: 1a2b3c…, merged: 4d5e6f…, result: pass}
    green: null
    break: null
```

`red` is check-order's red commit (where the test's marker has `new=True`; once there is a green,
it is the red commit that is an ancestor of green), and `green` is the commit where `new` was
removed. `merged` is the first commit on `main`'s first-parent line that contains `commit`, which
is the commit CI ran on after the merge. `result` is that run's outcome: `pass`, `fail`, or
`unverified` when no result is recorded. `break` is the mutation evidence (§5) and is `null` for a
`new` scenario. A `hold` scenario is the other way round: its test carries no `new=True`, so it
has no red and no green, and both stay `null`. Its `break` is `{commit, merged, result}`:
`commit` is the first commit on `main` whose tests link the scenario without `new=True`, `merged`
is found as for red, and `result` is the scenario's entry in the `break:` map of the CI note on
`merged` (`pass` or `fail`). It is `unverified` when that note, or its entry, is missing.

`redline ledger <change>` rebuilds the ledger from `main`'s history and writes it.
`redline check-ledger <change>` rebuilds it and fails if the committed file is missing or
differs. Only commits reachable from `main` count. So a step's PR carries the evidence of the
steps merged before it, never of its own commits: `pr` changes their hashes when it adds
trailers, and CI hasn't run on them after a merge. By the C step, the ledger holds every
`new` scenario's red and green, and every `hold` scenario's break.

From git alone, the rebuild knows which commits made each scenario red and green, and where they
merged. It can't know whether the tests really failed or passed there. Only a CI run can say
that. After a run on a merged commit, CI records the outcome as a git note on that commit under
`refs/notes/redline-ci` (`result: pass` or `result: fail`, then `run: <url>`), and the rebuild
reads that note. Until the note exists, the result is `unverified`. Once it lands, the committed
ledger is stale, and the next step's PR refreshes it. A note is only as trustworthy as the people
who can push to `refs/notes/redline-ci`, because branch protection doesn't cover that ref.

The contract lock, `redline/contracts/lock.yaml`, freezes each change's `hold` tests:

```yaml
add-greet:
  GREET.H1:
    tests/test_greet.py::test_placeholder_returns_nothing: 9c1e…   # sha256
```

Its tests are the same ones check-break counts (§5): a `hold` scenario of the change's deltas,
named by a spec marker without `new=True`. One function finds them for both. A test is
`path::name`, or `path::Class::name` for a method. Its hash is the SHA-256 of the function's
source, from its first decorator to its last line, with `\n` line endings. It covers the function,
not the whole file, because the R step's test files also hold `new` tests. Every G step edits
those, removing `new=True` and fixing the tests, and a whole-file hash would make every one of
those edits a departure. The cost is that the hash doesn't cover helpers and fixtures the test
calls (O-LOCK2, §12).

## 5. A change is always the same sequence of steps

| Step | PR contents | CI proves |
|---|---|---|
| **S: Spec** | Proposal and delta spec, with audit findings resolved | Structure is valid, every premise citation resolves, IDs are unique, every finding is closed or waived |
| **R: Red** | Linked tests: `new` as strict expected failures (`xfail(strict=True)`, Jest `test.failing`); `hold` added to the lock | Every `new` test fails on today's code; every `hold` test passes, then fails under mutation |
| **G1…Gn: Green** | Code that turns expected failures into passes | Owned scenarios pass with their markers removed, the lock is unchanged, nothing else regressed |
| **C: Close** | Verify report, delta merged into `specs/`, defect log, deferred items with owners | Every `new` scenario has red and green results from merged commits, the red commit an ancestor of the green one; every `hold` scenario has a break result |

Red tests can merge onto `main` while CI stays green, because CI expects them to fail. A `new` test
that passes before the code exists turns CI red under strict expected-failure, so a check that
can't fail can't get in. Git history then records test-first as fact.

A `hold` test can't prove itself that way, because it passes from the start. A **break** proves
it can fail. `redline check-break <change>` checks every `hold` scenario the change's deltas
declare:

- **Its tests** are the tests whose marker names the scenario without `new=True`. A `new=True`
  marker on a `hold` scenario doesn't count. No such test is a failure.
- **Unmutated**, those tests alone (`pytest --redline-spec <ID>`) must pass on today's code.
- **Mutated files** are the step's touched files only (§12). The R step's own diff adds tests and
  nothing else, so its touched code is the code its scenarios protect: the Python files the
  change's premises cite, which the auditor has checked. No other file is mutated.
- **Pass** means at least one mutant of those files makes the tests fail. A scenario fails if its
  tests survive every mutant, or if there is nothing to mutate.

It runs at the R step only. `pr` and `redline ci pr` run it as a gate there, as previews. After an
R step merges, `redline ci push` runs it again on the merged commit and adds one result per
`hold` scenario to the CI note (`break:` then `  <ID>: pass|fail`). A failed break fails the run.
That note is the only source of a ledger `break`. A local or PR run is never evidence.

The mutation tool is mutmut, behind the `Mutator` seam in `redline/breaks.py`, which tests
replace. mutmut doesn't run on Windows (3.8 refuses and points at WSL), so the real tool runs only
in CI on Linux, and the tests always use the fake. On Windows, check-break still checks each
scenario's tests and their unmutated run. It reports the mutation as skipped, not failed, because
CI runs it.

The R step also writes the lock (§4). `redline lock <change>` rewrites that change's entry from the
tests as they are now. `redline check-lock <change>` prints each difference between the lock and
the code:

- **A hash differs**: a locked test's source has changed.
- **A locked test is missing**: it was deleted or renamed, or its marker now has `new=True`.
- **A hold test isn't locked**: the test exists but the lock has no entry for it.

At R, the gate runs exactly that check, so every hold test is in the lock and current. At G1…Gn
the gate adds a fourth difference, `--base main`: the change's lock entries differ from the lock
at the merge-base with `main`. Without it, a G step could edit a frozen test and re-run `redline
lock`. `pr` and `redline ci pr` run both checks.

Editing a frozen test after R is a **departure**. The step re-runs `redline lock`, and one of its
commits carries a trailer naming the test, the person and the reason:

```
Redline-Departure: tests/test_greet.py::test_placeholder_returns_nothing approved-by @maintainer: the placeholder now returns ""
```

A test with a trailer like that among the step's own commits (`base..HEAD`) may change its lock
entry. Every other check still applies, so the lock must match the edited test. A trailer
missing `approved-by @person: <reason>` doesn't count. The trailer stays in `main`'s history, so
the departure is recorded with its approver (§2.7). Git alone can't prove the named person
approved it. That proof needs a maintainer's label checked through the `GitHub` seam (O-LOCK1,
§12), as `Oversized` does.

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

`pr` runs check-lines always, check-premises and check-audit at S (on the step's own change: an
older change's premises may go stale as the code moves on), and check-links and check-order from
the R step on (at S the delta's scenarios have no tests yet; check-order skips `hold` scenarios,
which have no red by design), check-break at the R step only, and check-lock from R on (G steps
with `--base main`, §5). Only when every gate passes does it put the
`Redline-Step` trailer on each of the step's commits (once), push, and open the PR with `gh`.

`merged <step>` fetches and fast-forwards local `main` first, then looks for the step's trailer on
`main` and refuses if it isn't there. Once it is, it switches to `main` (the next step starts fresh
from it, so uncommitted changes refuse before anything syncs), clears the open-step record if the
step it names is merged, and prints the next step's brief, or that the change is complete after C.

The brief (goal, owned scenario IDs, cited files, open items) is generated from the spec, the
ledger and the open items. It's the whole hand-off: a new session needs nothing from the old one.

## 7. Trust model

| Source | Counts as evidence? |
|---|---|
| CI run on a merged commit | Yes, and only this |
| CLI run locally | A preview, which CI re-runs |
| The agent's report or summary | Never |
| `ledger.yaml` | A cache, which CI rebuilds from history |

CI is `.github/workflows/redline.yml`, a thin wrapper around `redline ci`; every rule lives in the
CLI. It checks out the full history, `main` and `refs/notes/*`.

On a pull request, `redline ci pr --base main` works out the step from the `Redline-Step`
trailers of the PR's own commits (`main..HEAD`), which `pr` added. It refuses if no commit carries
one, or if they name more than one distinct step: a PR is one step. It then runs that step's gates
(the same ones `pr` runs locally), the test suite, and `check-ledger <change> --main main`, and
prints every failure. This proves the PR's state: the gates hold, `new` tests fail strictly, and
the committed ledger matches `main`'s evidence. It records nothing. A PR run is not evidence,
because its commits are not on `main` yet.

On a push to `main`, `redline ci push` runs the suite on the merged commit and writes the note
(`result: pass|fail`, `run: <url>`) on it under `refs/notes/redline-ci`, then pushes that ref. A
failed suite is still recorded, and the run fails. This is the only evidence Redline writes, and
the next PR's `check-ledger` picks it up.

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

For Claude Code the auditor is `.claude/agents/redline-auditor.md`: tools `Read, Grep, Glob` only,
`model: fable`, and it refuses on any other model rather than run on a weaker one. Claude Code
can't limit Write to one file, so the auditor stays read-only and replies with the whole
`audit.md`, which the main session writes unedited. A re-run reads the old `audit.md`, keeps
every finding and closes only what it has checked. The `Waived-by:` line is the maintainer's.

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
- O-LOCK1 [build 5, part 3]: a departure's approval is a recorded line, not proof. The proof is
  a maintainer's label, read through the `GitHub` seam and checked by `redline ci pr`, shared with
  `Oversized` (§2.3), which has no label check yet either.
- O-LOCK2 [build 5, part 3]: the lock hashes test functions only, so a weakened helper or fixture
  isn't caught. The critical level's lock (with timing) decides whether to hash what a test calls.
