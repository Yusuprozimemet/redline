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
   (declared in config) don't. A bigger PR needs an `Oversized: <reason>` trailer on one of its
   commits and a maintainer's `redline:oversized` label (§7).
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

An initiative is work too big for one change: a goal, reached in phases, each phase a set of
changes. A phase ends at a **stopping point**, where every change of the phase is complete and
`main` is coherent enough to stop for good: the initiative may end there and leave nothing half
done. Whether to go on is the maintainer's call. A change belongs to at most one phase of at most
one initiative. Most changes belong to none.

## 4. Files

```
redline/
├── config.yaml                     # rigor default, generated-file globs, runner, rules (§10)
├── specs/<domain>/spec.md          # living behaviour; each scenario carries its ID
├── contracts/lock.yaml             # hashes of frozen `hold` tests
├── initiatives/<id>/plan.md        # goal, phases, the changes of each, stopping points
└── changes/<id>/
    ├── proposal.md                 # why, scope, non-goals, rigor level
    ├── specs/<domain>/delta.md     # ADDED/MODIFIED/REMOVED; scenarios tagged new | hold; premises
    ├── design.md                   # how (optional at lite)
    ├── steps.md                    # S, R, G1..Gn, C, and the scenario IDs each step owns
    ├── audit.md                    # auditor findings and their resolution
    ├── defects.md                  # the defect log: what went wrong, its cause, what found it
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
calls.

At **critical** rigor (§8) each entry also hashes what the test reaches, and is a map:

```yaml
add-2fa:
  AUTH.2FA.H1:
    tests/test_login.py::test_lockout:
      test: 9c1e…    # the function, as above
      reach: 4b7a…   # what it reaches, below
```

`reach` is the SHA-256 of these sources, each labelled with its file and sorted by file and line:

- **Fixtures**: each parameter of the test, each `usefixtures` name, and each `autouse` fixture,
  found as a `@pytest.fixture` function in the test's class, then its file, then each
  `conftest.py` from its directory up to the root. The nearest wins, as in pytest.
- **Helpers**: each name a reached function reads that its own file defines at module level: a
  function, a class or an assignment (`TIMEOUT = 5`). Fixtures' parameters are fixtures again.
  This repeats until nothing new is reached.
- **Marks**: the module's `pytestmark`, and the test's class decorators and `pytestmark`.
- **Settings**: the root pytest configuration section (`pytest.ini`, `[tool.pytest.ini_options]`
  in `pyproject.toml`, `tox.ini`, `[tool:pytest]` in `setup.cfg`, first found), where pytest-timeout's
  `timeout` and `addopts` such as `--timeout` or `--reruns` live.

Only the test's file and its `conftest.py` files are searched. An imported name isn't followed,
because the code under test is imported too, and hashing it would make every G step a departure.

An entry that is a plain hash, as every lock written before this was, still reads: it is
`{test: <hash>}` with no `reach`. Below critical, `redline lock` keeps writing plain hashes.

The change's level is the `Rigor: lite|standard|critical` line of its `proposal.md`, else
`rigor:` in `redline/config.yaml`, else `standard`. Any other value is an error.

An initiative's plan, `redline/initiatives/2fa-rollout/plan.md`:

```markdown
# Initiative: 2fa-rollout
Goal: every account can require a second factor at login

## Phase 1: Codes from an authenticator app
Changes: add-2fa, add-recovery-codes
Stop: users can enrol and log in with a code; nobody is made to

## Phase 2: Required for admins
Changes: enforce-admin-2fa
Stop: every admin login asks for a code
```

The plan is the only place that says which initiative and phase a change is in; a proposal
doesn't repeat it. A listed change needn't exist yet: the plan names changes before their S
steps. A change is **complete** when the last step of its `steps.md` is merged on `main` (§6);
a change with no `steps.md` yet isn't. A phase is complete when all its changes are.

`redline check-plan [<initiative>]` checks every plan, or one, and fails on:

- **No goal**: the plan has no `Goal:` line.
- **No phases**, or phases not numbered `1, 2, …` in order.
- **A phase without changes or without a stop**: no `Changes:` line, an empty one, or no `Stop:`.
- **A change listed twice**, in one plan or across plans.

The defect log, `redline/changes/add-2fa/defects.md`, records what went wrong in the change's
own work after it was committed: a wrong premise found at G2, a test that couldn't fail, a fix
a later step had to make. A test failing on red, as it should, isn't a defect. The main session
adds an entry when it finds one, at any step:

```markdown
# Defects: add-2fa

## D1: the lockout counted wrong codes per session, not per account
Cause: premise
Found-by: add-2fa/G2
P2 said the counter lived in the session; it lives on the account row.
```

The heading says what went wrong. `Cause:` is one label from a fixed set, so labels can be
counted and compared:

| Cause | What was wrong |
|---|---|
| `premise` | a claim about the code the spec rested on |
| `spec` | a scenario missing, or one that says the wrong thing |
| `test` | a test that couldn't fail, or didn't check its scenario |
| `code` | the code, where the spec and its test were right |
| `handoff` | something lost between steps: a brief, an open item, a deferral |
| `tooling` | Redline, CI or the environment gave a wrong answer |

`Found-by:` is the step that found it (`<change>/<step>`, any change's), or a commit reachable from
`main`. A branch commit doesn't count: `pr` rewrites those when it adds trailers. Lines after
those are free text.

The cause is on its own line and nowhere else, so the critical level's blind relabelling (§8) can
show a second labeller the entry with the `Cause:` line removed and compare the two labels by ID.
The heading and the free text say what happened, not which cause it was. Relabelling isn't built;
when it is, the second labels go outside `defects.md`, so the first labeller can't edit them after
seeing them.

`redline check-defects <change>` fails on:

- **A missing log** at the C step, at standard and critical. A log with no entries is valid: it
  says the change found none. At lite the log is optional; if it exists, it's checked. Run on
  its own, the command checks as at C.
- **A `## ` heading that isn't `## D<n>: <text>`**, or a repeated ID.
- **No `Cause:` line, more than one, or a label not in the table.**
- **No `Found-by:` line**, or one that names no step of any change's `steps.md` and no commit
  reachable from `main`.

It checks the log's form, never that it is complete: a defect nobody writes down is missed (§7).

## 5. A change is always the same sequence of steps

| Step | PR contents | CI proves |
|---|---|---|
| **S: Spec** | Proposal and delta spec, with audit findings resolved | Structure is valid, every premise citation resolves, IDs are unique, every finding is closed or waived |
| **R: Red** | Linked tests: `new` as strict expected failures (`xfail(strict=True)`, Jest `test.failing`); `hold` added to the lock | Every `new` test fails on today's code; every `hold` test passes, then fails under mutation |
| **G1…Gn: Green** | Code that turns expected failures into passes | Owned scenarios pass with their markers removed, the lock is unchanged, nothing else regressed |
| **C: Close** | Verify report, delta merged into `specs/`, defect log, deferred items with owners | Every `new` scenario has red and green results from merged commits, the red commit an ancestor of the green one; every `hold` scenario has a break result; the defect log exists (standard, critical) and is well formed |

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

- **A hash differs**: a locked test's source has changed, or (where the entry has `reach`) a
  fixture, helper, mark or setting it reaches.
- **A locked test is missing**: it was deleted or renamed, or its marker now has `new=True`.
- **A hold test isn't locked**: the test exists but the lock has no entry for it.
- **A critical entry has no `reach`**: it was locked before the change was critical.

Every hash an entry has is checked, whatever the level. The level decides only what `redline
lock` writes and whether a missing `reach` is a difference. So lowering the level in the
proposal checks nothing less, unless the lock is rewritten, and at G that is a change since
`main`, below.

At R, the gate runs exactly that check, so every hold test is in the lock and current. At G1…Gn
the gate adds a fourth difference, `--base main`: the change's lock entries differ from the lock
at the merge-base with `main`. Without it, a G step could edit a frozen test and re-run `redline
lock`. An entry has changed when a hash it had at the merge-base differs, or it was added or
removed. A `reach` added where the merge-base had none hasn't changed it: the frozen source is
the same, and it is now checked further. `pr` and `redline ci pr` run both checks.

**Timing is part of what a frozen test expects** (`../migration-engine`, "The safety net is
frozen"). A test that asserted an effect at once and now waits for it, or waits longer, expects
something else with every value unedited. In Python and pytest, timing is any of these:

| Timing | Where | Caught by |
|---|---|---|
| `time.sleep`, `asyncio.sleep`; a poll loop and its bound (`range(50)`, a deadline); a `timeout=` argument | the test's body | the function hash, every level |
| `@pytest.mark.timeout(n)`, `@pytest.mark.flaky(reruns=n)`, Hypothesis `@settings(deadline=…)` | the test's decorators | the function hash, every level |
| any of the above in a fixture or helper; a constant such as `TIMEOUT = 5` | the test's file, its `conftest.py` files | `reach`, critical |
| `pytestmark = pytest.mark.timeout(n)`; a class decorator | the module, the test's class | `reach`, critical |
| `timeout`, `--timeout`, `--reruns` in the pytest configuration | the root config file | `reach`, critical |

A new or longer wait, poll bound or timeout, or a rerun added to quiet a flaky test, is a
departure, approved like any other: the `Redline-Departure` trailer and the `redline:departure`
label (§7). There is no second path. A fixture or helper edit changes the `reach` of every
critical test that reaches it, so each of those tests needs its own trailer. One label covers
them all.

What the lock still doesn't prove:

- **Timing from outside the files it reads**: an environment variable (`PYTEST_TIMEOUT`,
  `PYTEST_ADDOPTS`, a value the test reads with `os.environ`), a command-line flag in the CI
  workflow, or a value read from a data file.
- **What it can't find statically**: helpers imported from another module (a shared
  `tests/helpers.py`), fixtures from plugins, `request.getfixturevalue`, a fixture renamed with
  `@pytest.fixture(name=…)`, or names reached through attributes (O-LOCK3, §12).
- **That the code under test still meets the bound.** The lock freezes what the test expects,
  not what the API shows while it waits. The migration engine pins that with a second test
  outside the frozen set, which the departure's spec names. Redline doesn't check that it exists.

Editing a frozen test after R is a **departure**. The step re-runs `redline lock`, and one of its
commits carries a trailer naming the test, the person and the reason:

```
Redline-Departure: tests/test_greet.py::test_placeholder_returns_nothing approved-by @maintainer: the placeholder now returns ""
```

A test with a trailer like that among the step's own commits (`base..HEAD`) may change its lock
entry. Every other check still applies, so the lock must match the edited test. A trailer
missing `approved-by @person: <reason>` doesn't count. The trailer stays in `main`'s history, so
the departure is recorded with its approver (§2.7). The trailer is only a claim, so in CI it also
needs a maintainer's `redline:departure` label on the PR (§7).

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

A change in an initiative waits for its phase: `start` also refuses any step of a change in
phase N while a change of an earlier phase isn't complete, and names that change. Within a phase
the changes are independent, each with its own sessions.

`pr` runs check-lines and check-plan always, check-premises and check-audit at S (on the step's own change: an
older change's premises may go stale as the code moves on), and check-links and check-order from
the R step on (at S the delta's scenarios have no tests yet; check-order skips `hold` scenarios,
which have no red by design), check-break at the R step only, check-lock from R on (G steps
with `--base main`, §5), and check-defects at every step on the step's change (a log is
required only at C). A departure or an `Oversized` trailer doesn't refuse: the PR and its
labels don't exist yet, so `pr` prints that CI will need the label (§7). Only when every gate
passes does it put the `Redline-Step` trailer on each of the step's commits (once), push, and open
the PR with `gh`.

`merged <step>` fetches and fast-forwards local `main` first, then looks for the step's trailer on
`main` and refuses if it isn't there. Once it is, it switches to `main` (the next step starts fresh
from it, so uncommitted changes refuse before anything syncs), clears the open-step record if the
step it names is merged, and prints the next step's brief, or that the change is complete after C
and that `redline retro <change>` comes next (§10).
When that completes the change's phase, it also prints that the initiative is at a stopping
point, and the phase's `Stop:` line. Then it prints the next phase and its changes, or that the
initiative is complete. It starts nothing: going on is the maintainer's call.

The brief (goal, owned scenario IDs, cited files, open items, the rules of `redline/config.yaml`)
is generated from the spec, the ledger, the open items and the config. For a change in an initiative, it also gives the initiative's goal,
the phase and its `Stop:` line, so a session knows what its change is for. It's the whole
hand-off: a new session needs nothing from the old one.

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

### Approvals

A person's approval is a label on the PR, applied by a maintainer. A commit trailer in the PR's
own commits (`base..HEAD`) says what is approved and why, and stays in `main`'s history. The label
says a maintainer agreed. Two claims need one:

| Trailer | Allows | Label |
|---|---|---|
| `Redline-Departure: <test> approved-by @person: <reason>` | a frozen test's lock entry to change (§5) | `redline:departure` |
| `Oversized: <reason>` | more than 400 changed lines (§2.3) | `redline:oversized` |

A trailer without its reason (or, for a departure, without `approved-by @person:`) allows nothing.
One label covers every claim of its kind in the PR. The labels are separate, so approving the size
doesn't approve weakening a test. Both rules call one function, `approve` in
`redline/approval.py`, which returns why a claim isn't approved, or nothing.

`redline ci pr --pr <number>` reads the labels through the `GitHub` seam, and only when a claim
needs one. The PR's issue events (`gh api repos/{owner}/{repo}/issues/<number>/events`) give, for
each label still on the PR, who applied it last. That person is a maintainer when their role on
the repository (`gh api repos/{owner}/{repo}/collaborators/<login>/permission`, `role_name`) is
`admin` or `maintain`. The role comes from GitHub, not from a list in `redline/config.yaml`,
because a PR can edit the config to name its own author. A claim fails when its label is missing,
was applied by someone else, or there is no PR number. The workflow passes the number and a
read-only token, and also runs on `labeled` and `unlabeled`, so applying the label re-runs CI.

Locally there is no PR, so no label can exist yet. `redline pr` and `redline check-lock` don't
refuse a claim. They print that CI will need its label. A trailer that allows nothing still fails.

What the label still doesn't prove:

- **Who pressed the button.** Anyone holding a maintainer's token, including an agent given it,
  applies the label as that maintainer.
- **What they saw.** The label isn't tied to a commit. Commits pushed after it, with new
  departures, are covered by it until someone removes it.
- **That the named person agreed.** Any maintainer's label approves a departure, whoever its
  trailer names.
- **The role at the time.** The role is read when CI runs, not when the label was applied.

The real `gh api` calls are tested only by hand; the suite uses the fake.

## 8. Rigor levels (on top of the invariants)

| Level | Adds |
|---|---|
| **lite** | Nothing; S and R may share one PR |
| **standard** (default) | Mutation testing on the touched files, and a defect log |
| **critical** | Contract lock covers what each test reaches, timing included (§4, §5), one track per Green PR, a plan-auditor at the start and end of each phase, blind relabelling of defects, independent end-of-initiative auditors |

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

A rule is a line under its cause in the config's `rules:`, and every brief prints all of them, so
every later session sees what earlier defects taught:

```yaml
rules:
  premise:
    - Cite where a value is stored, not only where it is read
```

`redline retro <change>` reads the change's `defects.md` (it refuses unless check-defects passes,
whatever the level) and the config's `rules:`. It prints, for each cause with defects, most
first: the count, the IDs and headings, and how many rules the cause has already. Then one
proposal per cause: add a rule under `rules.<cause>` against those defects. With no defects, it
says there is nothing to propose.

It writes nothing. The wording of a rule is a judgment, so the session or the maintainer writes
it, one cause per PR, and the maintainer reviews it like any other change. On its own, `retro`
never:

- **edits `redline/config.yaml`**, commits, pushes or opens a PR;
- **edits `defects.md`**: a tool that rewrote causes would bias any later relabelling;
- **proposes removing or weakening** anything: no rule removed, no rigor lowered. A change's level
  is its proposal's and its auditor's call (§8), so `retro` doesn't propose one.

Its output is a proposal, never evidence (§7), and CI doesn't run it.

## 11. Build order (riskiest first)

1. **Red/green proof**: pytest plugin with `spec` markers and strict expected failures, plus the
   git-ancestry check (red commit is an ancestor of green). If this doesn't feel natural, the
   design changes.
2. 400-line gate; scenario-to-test linking both ways; `start`/`pr`/`merged` and the brief.
3. Premise citations and the auditor agent.
4. Ledger rebuilt by CI; GitHub Action.
5. Mutation (mutmut, then Stryker, PIT); contract lock; critical level.
6. Initiatives and plans (part 1); the defect log and `retro` (part 2). The rest of the
   critical level builds on phases: a plan-auditor at each phase's start and end,
   end-of-initiative auditors, one track per Green PR, blind relabelling.

## 12. Open problems

- Scenarios that can't be automated (visual, timing): a recorded manual check with a reason,
  which the auditor may challenge.
- Mutation cost on large codebases: touched files only, at the Red step only.
- Whether a test asserts its scenario's THEN clauses is a judgment; the auditor checks it.
- O-LOCK1 [closed, build 5 part 3]: a departure's approval was a recorded line, not proof. Now
  `redline ci pr` checks a maintainer's `redline:departure` label, with the same function that
  checks `Oversized` (§7, Approvals), and §7 says what that still doesn't prove.
- O-LOCK2 [closed, build 5 part 4]: the lock hashed test functions only, so a weakened helper or
  fixture wasn't caught. At critical it now hashes what each test reaches (§4), not only timing
  values: picking timing out of code by name (`sleep`, `timeout`, `wait`) misses a bare
  `range(50)` poll bound and a renamed helper, and a weakened assert in a fixture is the same
  quiet weakening. The cost is a departure for every critical test a shared fixture edit reaches.
  Every level keeps the function hash, which already holds the test's own timing.
- O-LOCK3 [build 5, a part after the critical tracks]: `reach` stops at the test's file and its
  `conftest.py` files, so helpers imported from shared test modules, plugin fixtures and dynamic
  lookups aren't locked (§5). Decide whether to follow imports into files `redline/config.yaml`
  names as test support.
- O-RETRO1 [build 6, the part after the defect log]: a rule PR from `retro` belongs to no step,
  so it carries no `Redline-Step` trailer, and `redline ci pr` refuses it, as it refuses
  Redline's own PRs. Decide what CI runs on a PR that changes only `redline/config.yaml`: the
  always-on gates (check-lines, check-plan) and the suite, at least.
