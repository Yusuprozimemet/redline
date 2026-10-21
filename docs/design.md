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
| Verify can be ignored | OpenSpec | The close is checked, not reported: check-close against CI's evidence, check-specs against the living specs, and the C step can't merge without both |

## 2. Seven invariants (always on, at every rigor level)

1. **The spec comes before the code.** No code PR exists without a merged spec for it.
2. **Red before green, proved on `main`.** A test for a `new` scenario lands as a *strict expected
   failure*, and CI confirms it really fails.
3. **Every PR is ≤ 400 changed lines.** Specs and tests count; lockfiles and generated files
   (declared in config, as it is at the merge-base with `main`, §7) don't. A bigger PR needs an `Oversized: <reason>` trailer on one of its
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
├── config.yaml                     # rigor default, generated-file globs, support files, rules (§10)
├── specs/<domain>/spec.md          # living behaviour; each scenario carries its ID
├── contracts/lock.yaml             # hashes of frozen `hold` tests
├── initiatives/<id>/plan.md        # goal, phases, the changes of each, stopping points
├── initiatives/<id>/audits/        # phase-<n>-start.md, phase-<n>-end.md: plan audits (critical);
│                                   # initiative-<side>.md: end-of-initiative audits (critical)
└── changes/<id>/
    ├── proposal.md                 # why, scope, non-goals, rigor level
    ├── specs/<domain>/delta.md     # ADDED/MODIFIED/REMOVED; scenarios tagged new | hold; premises
    ├── design.md                   # how (optional at lite)
    ├── steps.md                    # S, R, G1..Gn, C, and the scenario IDs each step owns
    ├── audit.md                    # auditor findings and their resolution
    ├── defects.md                  # the defect log: what went wrong, its cause, what found it
    ├── relabel.yaml                # a second, blind label per defect (critical)
    └── ledger.yaml                 # a cache of evidence; CI rebuilds it and fails on a mismatch
```

A scenario:

```markdown
#### Scenario AUTH.2FA.S1 [new]: wrong code is rejected
- GIVEN a user with 2FA enrolled
- WHEN they submit an incorrect code
- THEN login fails AND no session is created
```

A delta's scenarios sit under its `## ` sections, which say what the C step does to the living
spec of the same domain, `redline/specs/<domain>/spec.md`:

```markdown
## ADDED Requirements
### Requirement: Second factor
#### Scenario AUTH.2FA.S1 [new]: wrong code is rejected
- …

## MODIFIED Requirements
### Requirement: Login
#### Scenario AUTH.LOGIN.S2 [new]: the whole scenario, as it will read
- …

## REMOVED Requirements
- AUTH.LOGIN.S3: the password-only login is gone
```

An ADDED scenario is new to the living spec; a MODIFIED one restates, whole and under the same
ID, a scenario it already has; each is copied there, heading to last line, under the same
`### Requirement:`. A REMOVED entry is an `- <ID>: <reason>` line directly under its section, not
a heading, so it needs no test and no evidence: once it leaves `specs/`, a test still linked to it
fails check-links as an unknown scenario. Deleting that test, if it is frozen, is a departure (§5).

A change is **closed** once its C step is merged on `main`: a commit reachable from `main` carries
`Redline-Step: <change>/C`. Its delta stays, the record of what it declared, and its own checks
still read it, but it declares nothing any more: the living spec holds what it said. So every
check that reads all the deltas skips a closed change's: check-links, whose duplicate rule would
otherwise fail a later change that MODIFIES a scenario a closed one ADDED, and which would still
count a scenario a later change REMOVES as declared; the `hold` scenarios check-order leaves out
(§6), where a closed delta's stale tag would keep one out after a later change made it `new`; and
`redline check-premises` run without a change, since a closed change's premises go stale as the
code moves on (§6). Until its C step merges, a change's delta and the living spec may both carry
an ID, as a MODIFIED scenario does, and as every scenario does in the C PR itself.

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

A test is linked to its scenario with a marker, e.g. `@pytest.mark.spec("AUTH.2FA.S1")`. A marker
counts only where its runner reads one: pytest's as a decorator of a test function, Jest's as a
`spec(` call in code, never in a comment or a string (§5, Runners).

Steps, in order, with the scenarios each owns and the deferred items each step owns:

```markdown
## G1: Reject a wrong 2FA code
Owns: AUTH.2FA.S1
Track: auth/login.py, auth/codes/*.py

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
`commit` is the first commit of the change's R step (one on `main` carrying `Redline-Step:
<change>/R`) whose tests link the scenario without `new=True`, `merged` is found as for red, and
`result` is the scenario's entry in the `break:` map of the CI note on `merged` (`pass` or
`fail`). It is `unverified` when that note, or its entry, is missing. The R step's merge is the
only one whose note has a `break:` map (§5), so a break is never read from another change's.

**A change's evidence is its own.** A scenario ID outlives the change that added it: a later
change may MODIFY it, and its tests are the same tests. So a change's red, green and break count
only from its **window**: the commits merged by the PR of its S step or after it, and, once the
change is closed, by the PR of its C step or before it. In git terms, the commits of `S₀..E`,
where `S₀` is the first parent of the merged commit of the change's first S commit (so the S
PR's own commits count, as at lite, where S and R may share a PR, §5), and `E` is the merged
commit of its first C commit, or `main` while it is open. A green counts only when it turns the
scenario green inside the window and is paired with a red inside it. So a later change that
MODIFIES a `new` scenario and never makes it red again has no red and no green, not the earlier
change's, and check-close refuses it (§5); one that does is paired with its own red. A MODIFIED
`hold` scenario's break is the later change's R step's, which CI already notes. The window's end
keeps a closed change's ledger as it was: a later change's commits are outside it. A change whose
S step isn't on `main` (its own S PR, where check-close never runs, or a history without
trailers) is read over all of `main`'s history, as before; R needs S merged, so no change reaches
C that way.

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
who can push to `refs/notes/redline-ci`, because branch protection doesn't cover that ref. CI's
own code isn't among them: the job that writes the note runs none of the repository's code (§7).

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

**A scenario's entry is the change's that declared it last.** A later change may MODIFY a `hold`
scenario a closed change added, and its tests are the same tests. So `redline lock <change>` takes
each scenario the change's deltas name (ADDED, MODIFIED or REMOVED) out of every closed change's
entry, dropping an entry left empty, and locks it under the change if it is still `hold` there. A
test it moves keeps its `reach`: the change writes one for any test whose entry has one, so a move
never checks less. Moved unedited, a test keeps its hash and needs no departure; edited, made
`new` or deleted, it needs one at that step (§5). A closed change's entry is never rewritten with
a later change's hashes; its earlier hashes are in lock.yaml's history. Closed, a change's
check-lock checks the entries it still has against the code and never asks for a test to be
locked, since its delta declares nothing (above). Its entries still count: closed or not, a frozen
test stays frozen.

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
- **Support**: a name a reached statement reads that its file imports from a **support file**,
  `from m import name` (aliases too) or `import m` then `m.name`. The name's statement in that
  file is reached as a helper is, and so on through the support file's own names and imports. A
  fixture imported into the test's file or a `conftest.py` from a support file is a fixture
  there, as in pytest.

A support file is one whose path matches a glob under `support:` in `redline/config.yaml`,
matched as `generated:` globs are (§2.3):

```yaml
support:
  - "tests/helpers.py"
  - "tests/support/*.py"
```

A module is found as `m.py` or `m/__init__.py` from the importing file's directory, then each
parent up to the root (relative imports from the directory their dots name). Any other import
isn't followed, because the code under test is imported too, and hashing it would make every G
step a departure. Without `support:`, only the test's file and its `conftest.py` files are
searched, and every `reach` is what it was before. Adding a file to `support:` changes the
`reach` of each critical test that imports from it, so for a locked test that is a departure,
as editing a fixture is (§5); outside a step it can't be done at all (§7). Name support files
before the R step that locks tests using them.

`reach` reads `support:` from the tree being checked, not at the merge-base: the hash guards
itself, since a glob added or removed changes the `reach` of every locked test it touches, and
`redline lock` at R and check-lock on a later PR must read the same globs to agree. check-track
reads `support:` and `generated:` at the merge-base (§5), and a glob added to either is a claim
(§7, Approvals). A value of `generated:` or `support:` that isn't a list of strings, or of `rules:`
that isn't a map of causes to lists of strings, is an error: a string would be read as its
characters, and `*` matches every path.

An entry that is a plain hash, as every lock written before this was, still reads: it is
`{test: <hash>}` with no `reach`. Below critical, `redline lock` keeps writing plain hashes.

The change's level is the `Rigor: lite|standard|critical` line of its `proposal.md`, else
`rigor:` in `redline/config.yaml`, else `standard`. Any other value is an error. Lowering it once
the proposal is on `main` (its line changed or removed, or the proposal deleted, so that the level
falls to a lower `rigor:`) is a claim (§7, Approvals); raising it isn't, since the auditor may
raise a level but never lower it (§8). A new proposal declares its level without a claim.

An initiative's plan, `redline/initiatives/2fa-rollout/plan.md`:

```markdown
# Initiative: 2fa-rollout
Goal: every account can require a second factor at login
Rigor: critical

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
a change with no `steps.md` yet isn't. A phase is complete when all its changes are. The optional
`Rigor: lite|standard|critical` line, before the first phase, is the initiative's own level (plan
audits, below).

`redline check-plan [<initiative>]` checks every plan, or one, and fails on:

- **No goal**: the plan has no `Goal:` line.
- **An unknown level**: a `Rigor:` line that isn't `lite`, `standard` or `critical`.
- **No phases**, or phases not numbered `1, 2, …` in order.
- **A phase without changes or without a stop**: no `Changes:` line, an empty one, or no `Stop:`.
- **A change listed twice**, in one plan or across plans.
- **A complete phase of a critical initiative** whose end audit (below) is missing or has a
  finding that isn't resolved as `check-audit` requires (§4): `[open]`, `[closed]` without
  `Resolution:`, `[waived]` without `Waived-by:`. Completeness is read from `main`; the audit
  from the tree being checked, so the PR that adds it passes.
- **A complete critical initiative**, every phase complete on `main`, whose three
  end-of-initiative audits (below) aren't all there and resolved, read the same way.
- **A stale audit**: the end audit of the last phase complete on `main`, or, once every phase
  is, one of the three, that didn't read the plan in the tree being checked (below).

**Plan audits**, at critical. An initiative is critical when its plan's `Rigor:` line says
`critical`, or any change it lists is: its proposal's `Rigor:`, else the config's `rigor:`. A
change with no proposal yet takes the config's, so without the plan's line an initiative whose
first S step declares `Rigor: critical` would skip that phase's start audit. The plan's line can
only raise the level: a change it lists that is critical stays so. Changing the line, removing it
or deleting a plan that has one is a claim, as changing the config's `rigor:` is (§7, Approvals).

So is **taking a change out of a plan**: deleting the plan, with or without a `Rigor:` line, or
removing a change from every phase of it, or a whole phase. The change leaves the initiative: a
critical change no longer makes it critical, its phase's audits stop being asked for, and `start`
stops making it wait for earlier phases. That holds at every level, since a change with no
proposal yet takes the config's, so whether its initiative was critical can't be known when it
leaves. It is the same claim, `Redline-Rigor` with the `redline:rigor` label, not a new one: what
the maintainer approves is the same, that an initiative's changes face less than they did. The
rigor check (§7) reads each plan's changes at the merge-base with `main` and fails on any listed
there that its plan, in the tree now, doesn't list, naming the change and the plan, or the plan
and its changes when it was deleted. A plan renamed is a plan deleted. Adding a change, or moving
one to another phase of the same plan, isn't a claim; a change moved to another plan is.

Its plan is then audited at each phase's start and end by the plan-auditor,
`.claude/agents/redline-plan-auditor.md` (§9), given only `<initiative> phase <n> start` or
`<initiative> phase <n> end`. The change auditor reads one change; nobody else reads how the
changes fit together, and that is where a phase goes wrong: a change that needs another of its
own phase, which runs beside it (§6), or a stop that leaves something half done.

- **Start**, before the phase's first step. It reads the plan, the living specs, the code the
  plan is about, and whatever proposals and deltas of the phase's changes exist yet. It checks
  that the `Stop:` line can be observed on `main`, as a THEN clause can (§5); that each change
  of the phase needs nothing from another change of the phase or a later one; that stopping
  after the phase leaves nothing half done; and that the phases still reach the `Goal:`.
- **End**, once every change of the phase is complete on `main`. It also reads each of the
  phase's changes' `steps.md`, `audit.md`, `defects.md`, `relabel.yaml` and `ledger.yaml`. It
  checks that the `Stop:` line is true on `main`, citing the scenarios and tests that show it;
  that each open item was done by its owning step or moved to a change of a later phase, by
  name; and that the later phases still hold, given the defects this one found.

It replies with the whole file, which the main session writes unedited to
`redline/initiatives/<id>/audits/phase-<n>-start.md` or `phase-<n>-end.md`, in the form of
`audit.md` (§4): a finding is closed only by a re-run, and waived only by a person's
`Waived-by:` line. The file lands on `main` in a PR outside any step (§7), which may touch
`redline/initiatives/`.

Two gates refuse without it. `start` refuses every step of a change in phase n while
`phase-<n>-start.md` on `main` is missing or unresolved, or an earlier phase's end audit is.
check-plan fails on a complete phase's end audit, as above.

**Tied to the plan it read.** The auditor is given the plan's blob hash with its arguments,
`<initiative> phase <n> start with plan <blob>`, and its reply's second line records it:
`Plan: <blob>`. An audit is **current** when that is the blob of `plan.md` in the tree being read
(`git rev-parse main:<path>` for `main`, `git hash-object <path>` for the tree being checked). A
PR outside any step may edit a plan, its phases' changes or their `Stop:` lines, after the audit
that read it. Each gate then refuses the newest audit it needs:

- `start` refuses a step of phase n while `phase-<n>-start.md` on `main` isn't current.
- check-plan fails, on every PR, while the end audit of the last phase complete on `main` isn't
  current, or, once every phase is complete, any of the three end-of-initiative audits isn't.
  That end audit asked whether the later phases still hold, which is what a plan edit changes.

The refusal names the audit, the blob it read (or that it has no `Plan:` line) and the plan's
blob now, and says to run the auditor again with the new blob. The re-run reads its old file,
keeps or closes each finding against the plan as it is now, records the new blob, and lands in a
PR outside any step. Earlier audits need only be resolved: a newer one has read the plan since.

**Refusing at a stopping point.** `merged` only prints: the merge is done, and refusing to sync
`main` would undo nothing. At a critical initiative's stopping point it prints that the end
audit is due, where it goes, and that the next phase's start audit is due before its first step.
The refusal is then check-plan's. `pr` and `redline ci pr` run it on every PR, in a step or
outside one, so the next PR in the repository, of any change, fails until the end audit lands
with every finding resolved. `start` alone wouldn't do: an initiative that stops for good starts
nothing, and its stop would go unaudited. The cost is that one late audit holds up unrelated
PRs. That is meant: an unaudited stop is a silent gap (§2.7), and the fix is one small PR.

What it doesn't prove: that the agent read the plan whose blob it recorded, since it can't hash
a file, and the blob is the main session's word, as what the agent read and that its reply was
written unedited are (§9); a plan edited during phase 1, before any end audit, which nothing
refuses until that end audit reads it; and a change moved between phases of its plan, which is
a plan edit, not a claim, seen only by a stale audit. A deleted plan, or a change taken out of
one, needs the rigor claim (above).

**End-of-initiative audits**, at critical, once every phase is complete on `main`. A plan audit
asks of one phase whether its `Stop:` is true and whether the phases after it still hold. Nobody
asks of the whole initiative, after its last stop, whether what it built can be relied on,
whether its gates could have passed while its `Goal:` was false, or what its record shows. Three
auditors do, as the migration engine's three end-of-migration auditors did. Each is read-only, on
the strongest model, in a fresh context (§9), and is given only `<initiative>`:

| Side | Agent (`.claude/agents/`) | Asks | Reads, besides the plan |
|---|---|---|---|
| `security` | `redline-security-auditor.md` | Can what the initiative built, and the way it was built, be trusted with more agent autonomy? | the code the changes' `Track:` lines name, `.github/workflows/`, `.claude/`, `redline/config.yaml` |
| `architecture` | `redline-architecture-auditor.md` | Do its gates hold: could every test pass while the `Goal:` is false? | the living specs, each change's deltas and `steps.md`, the tests linked to them, the lock, each `ledger.yaml` |
| `process` | `redline-process-auditor.md` | What does its record show, and how far can it be trusted? | each change's `proposal.md`, `audit.md`, `defects.md`, `relabel.yaml`, `steps.md` and `ledger.yaml`; the config's `rules:`; the text `redline claims` prints (below) |

- **Security** checks authentication, authorization, secrets and the untrusted input the code
  reads; and for the agents, what their tools and the workflow's tokens can reach, prompt
  injection through the specs, defect logs and PR text a session reads, and actions not pinned.
- **Architecture** checks that the `Goal:` is stated by scenarios on `main`, each with a test that
  can fail (a red and green, or a break, in the ledger); what a gate enforces and what rests on an
  agent's word; and what a test could pass while violating: a THEN clause it doesn't assert, a
  break that mutated nothing its scenario protects.
- **Process** checks the defects by cause across changes and phases, and whether a cause came back
  after `retro` added a rule against it; how often the relabeller disagreed and how each was
  decided; what the auditor found and who waived it; which decisions were a person's and which an
  agent's; and each claim git history holds, and whose label approved it.

**How they differ from the last phase's end plan audit.** That audit reads one phase in the plan's
own terms: its `Stop:`, its open items, the phases after it, and after the last phase there are
none. These read every phase against the `Goal:`, each from a side the plan-auditor doesn't look
from, and none judges the plan. They run beside it, at the same stopping point, independently:
none reads another's file or the plan audits, so their disagreement is part of the result. Each
reads only its own earlier file, on a re-run.

Each replies with the whole file, which the main session writes unedited to
`redline/initiatives/<id>/audits/initiative-<side>.md`, in the form of `audit.md`, in a PR
outside any step. A finding is closed by a re-run once it is answered: fixed on `main`, or taken
on by name by a change whose proposal says so. The initiative is complete, so that change is in
no phase of it, and its own S step can carry the re-run that closes the finding. A limit the
maintainer accepts is a waiver. No finding is left without an owner (§2.7).

The gate is check-plan's, as at any stopping point: on every PR it fails on a complete critical
initiative while any of the three is missing or unresolved. `merged` at the last stopping point
prints the three, where each goes, and that check-plan fails until they land. `start` can't be
the gate: a complete initiative starts nothing.

What it doesn't prove: that none read another's file, since Claude Code can't limit Read (§9). A
plan edited after them makes them stale, and check-plan fails until each is run again (above).

**The claims record.** With `Read, Grep, Glob`, an auditor sees files, not git history, and the
claims (§7, Approvals) live only there: the `Oversized`, `Redline-Track`, `Redline-Departure` and
`Redline-Rigor` trailers, and the labels that approved them. Those are the decisions a person made
to let a gate pass, which is what the process auditor asks about. `redline claims <initiative>`
prints them from `main`, and the main session gives that text to the process auditor after its
arguments, as it gives `redline blind`'s text to the relabeller:

```markdown
# Claims: 2fa-rollout
From main: 1 claim on 9 commits: the steps of add-2fa, add-recovery-codes, enforce-admin-2fa,
add-sms-codes, and every commit that touches redline/initiatives/2fa-rollout/ or redline/config.yaml.
Left the plan: add-sms-codes in 9c0d1e2.

## 4d5e6f1 add-2fa/G2 (PR #12): Lock out after five wrong codes
Redline-Departure: tests/test_login.py::test_lockout approved-by @maintainer: five, not three
Label at the merge: redline:departure, applied by @alice, admin (CI note on 7a8b9c0)
```

- **The changes** are every change any version of the plan on `main` listed: the plan at each
  commit on `main`'s first-parent line that changed it, oldest first, in the order each change
  first appears. A change taken out of the plan, under an approved rigor claim (above), stays in,
  so its claims stay in the record. `Left the plan:` names each change the plan on `main` no
  longer lists, and the commit on that line where it last left: the merge of the PR that took it
  out, or the commit itself after a squash. A change put back isn't named. A deleted plan is a
  version that lists nothing, so `claims` still prints a deleted initiative, every change named
  as left, and says `The plan was deleted from main in <commit>.` It fails only on an initiative
  no commit on that line ever had a plan for.
- **The commits** are every non-merge commit reachable from `main` whose `Redline-Step` names a
  step of one of those changes, or that touches the initiative's directory (plan
  edits, audits, a `Rigor:` line) or `redline/config.yaml` (its `rigor:`), oldest first. Only
  those with a claim trailer get a heading; with none, the text says `No claims.`
- **The PR** of a commit is the merged PR GitHub associates with it
  (`gh api repos/{owner}/{repo}/commits/<sha>/pulls`), through the `GitHub` seam (§7).
- **The label** is what `redline ci push` recorded (§7) in the CI note on the commit where the
  claim merged, the first commit on `main`'s first-parent line that contains it, as for the
  ledger: the claim's label on the PR, who applied it last and their role, when CI ran on the
  merge; or that it wasn't on the PR, or that no merged PR was found. When that commit has no
  note, or its note has no record of the claim, `claims` says so (`Label at the merge: not
  recorded: …`) and then reads the label as CI reads it, now (`Label now: …`).

It prints every claim and judges none: a claim of a PR that didn't need it, a label applied by
someone who isn't a maintainer, or a departure approved by someone other than the person its
trailer names, is for the auditor to weigh. It writes nothing, and its text is no evidence (§7).

What it still doesn't prove:

- **That the auditor saw that text, unedited**: it is the main session's word, as `blind`'s is.
- **The labels at the button**: the record is read when CI runs on the merged commit, moments
  after the merge, not when it was pressed. §7's limits hold too: who pressed the button, and
  what they saw.
- **That a record is CI's**: a note is only as trustworthy as the people who can push
  `refs/notes/redline-ci`, which branch protection doesn't cover. Whoever can push it can write
  or rewrite a record.
- **The labels of a claim with no record**: commits merged before build 6 part 11 have none, nor
  does a merge whose push run couldn't read GitHub until a re-run adds it. For those, `claims`
  reads labels and roles now, so a label removed after the merge reads as missing, one added
  after it as present, and a re-run's record reads them as late as it runs.
- **A PR merged by rebase**: the push run reads the claims of the merged commit and its first
  parent's range only, as it reads the step (§7), so a claim in an earlier commit of the PR gets
  no record.
- **A claim that should have been made**: a PR merged over a gate, without CI or with it failing,
  has no trailer to print. It shows only that the record holds no claim there.
- **PR text**: descriptions and review comments aren't printed.
- **Whose test a departure edited**: a departure on a test another change locked is a claim of
  the step that made it, printed in that step's initiative, not in the initiative of the change
  that locked the test.
- **Which of a left change's steps were the initiative's**: every step of a change any version
  listed is printed, those merged after it left too, since a step doesn't say which initiative it
  was for. The commits are oldest first and `Left the plan:` names where it left, so the auditor
  can tell them apart. A change moved to another plan is printed in both initiatives' claims.
- **A version only inside a PR**: the plan is read where `main`'s first-parent line changed it,
  so a change listed and taken out again among one PR's own commits, under a merge commit, isn't
  read. It was never in the plan on `main`, and the rigor check (§7) compared no version with it.
- **A plan renamed**: it is a plan deleted (§4), so the old name's `claims` prints its history up
  to the rename and the new name's from it; neither names the other.

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
The heading and the free text say what happened, not which cause it was.

**Blind relabelling.** The main session labelled each defect, and it also wrote the spec, the
tests or the code the defect is about. A second label from a reader who shares none of that view
says whether the causes, and so `retro`'s rules, can be trusted:

1. `redline blind <change>` prints the log with every `Cause:` line and every `Decided:` line
   removed. It refuses unless check-defects passes.
2. The main session gives that text, and nothing else, to the relabeller,
   `.claude/agents/redline-relabeller.md` (§9): read-only, on the strongest model, in a fresh
   context. It labels each entry from its text alone and replies with the whole relabel file.
3. The main session writes the reply unedited to `redline/changes/<id>/relabel.yaml`, outside
   `defects.md`, so the first labels and the second can't be edited into each other.

```yaml
# Relabel: add-2fa
D1:
  cause: premise
  note: P2 claimed where the counter lived, and the code showed otherwise.
D2:
  cause: unclear
  note: The entry says the fix was in a later step but not what was wrong.
```

`cause` is one label of the table, or `unclear` when the text doesn't let it choose; `note` is one
sentence on what decided it. A disagreement, where the second label isn't the `Cause:` line, is
decided by the maintainer or the main session in a `Decided: <reason>` line under the defect in
`defects.md`: the label kept and why, or the `Cause:` changed and why. `unclear` is a
disagreement too: an entry nobody else can label is a weak record.

`redline check-relabel <change>` prints each disagreement, then fails on:

- **A missing `relabel.yaml`** at the C step, at critical. Below critical it is optional; if it
  exists, it is checked. Run on its own, the command checks as at C.
- **A defect with no label**, or a label for an ID the log doesn't have. A defect added after the
  relabel needs the relabeller run again; a re-run keeps every earlier entry.
- **A label not in the table** and not `unclear`, or an entry without a `note`.
- **A disagreement with no `Decided:` line.**
- **A `Cause:` changed after the relabel** with no `Decided:` line: the first label of a defect is
  its `Cause:` in the parent of the first commit whose `relabel.yaml` labels it. Changing it after
  seeing the second label is the bias relabelling exists to show, so it is allowed only in the
  open, with a reason.

What it doesn't prove: that the relabeller saw only the blind text. It can read any file, and the
main session could hand it more. Claude Code can't limit Read to one file, as with the auditor
(§9). Nor does it prove that the reply was written unedited; it is a recorded file in the PR,
reviewed as such.

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
| **G1…Gn: Green** | Code that turns expected failures into passes | Owned scenarios pass with their markers removed, the lock is unchanged, the code stays in the step's track, nothing else regressed |
| **C: Close** | Delta merged into `specs/`, ledger, defect log, deferred items with owners | Every `new` scenario has red and green results from merged commits, the red commit an ancestor of the green one; every `hold` scenario has a break result; the delta's ADDED, MODIFIED and REMOVED are in `specs/`, and nothing else there changed; the defect log exists (standard, critical) and is well formed; at critical, each defect has a blind second label and each disagreement a decision |

Red tests can merge onto `main` while CI stays green, because CI expects them to fail. A `new` test
that passes before the code exists turns CI red under strict expected-failure, so a check that
can't fail can't get in. Git history then records test-first as fact.

A `hold` test can't prove itself that way, because it passes from the start. A **break** proves
it can fail. `redline check-break <change>` checks every `hold` scenario the change's deltas
declare:

- **Its tests** are the tests whose marker names the scenario without `new=True`. A `new=True`
  marker on a `hold` scenario doesn't count. No such test is a failure.
- **Unmutated**, those tests alone must pass on today's code, run by each runner that has one of
  them (`pytest --redline-spec <ID>`; Jest with `REDLINE_SPEC=<ID>`, below). A runner that can't
  start, such as Jest without `npx`, fails the scenario: a run that didn't happen proves nothing.
- **Mutated files** are the step's touched files only (§12). The R step's own diff adds tests and
  nothing else, so its touched code is the code its scenarios protect: the files the change's
  premises cite, which the auditor has checked, each mutated by the tool of the runner its
  extension names (a cited `.py` file by mutmut, a `.js` file by Stryker), and only for a runner
  that has one of the scenario's tests. No other file is mutated.
- **Pass** means at least one mutant makes the tests fail. Made and killed mutants are added up
  across the scenario's runners, which stop at the first kill. A scenario fails if its tests
  survive every mutant, or if none of its runners has a file to mutate. When nothing was killed
  and a runner's tool was unavailable, the scenario is skipped, not failed; once another runner's
  tool has killed a mutant, an unavailable one changes nothing.

It runs at the R step only. `pr` and `redline ci pr` run it as a gate there, as previews. After an
R step merges, `redline ci push` runs it again on the merged commit and adds one result per
`hold` scenario to the CI note (`break:` then `  <ID>: pass|fail`). A failed break fails the run.
That note is the only source of a ledger `break`. A local or PR run is never evidence.

The mutation tools sit behind the `Mutator` seam in `redline/breaks.py`: `MUTATORS`, a registry
keyed by runner name, holds one tool per runner, mutmut for pytest and Stryker for Jest. It is a
registry and not a field of `Runner`, so a runner stays plain data, and a test replaces every tool
by replacing one dict, built from the registry's own keys, so a runner added later is replaced
too. A test fails if a runner has no tool. The gates' tests always use the fake; the real tools
are proved on toys in the `runners` CI job (§7). mutmut doesn't run on Windows (3.8 refuses and
points at WSL), so the real mutmut runs only in CI on Linux. On Windows,
check-break still checks each scenario's tests and their unmutated run. It reports each scenario
whose mutation it couldn't run as skipped, with the reason, because CI runs it; in CI a skip fails
the run. Stryker runs on Windows too, so a test that skipped the fake would start it.

mutmut runs in a throwaway copy of the repository, with Redline's settings and no others, written
to the copy's `setup.cfg` under `[mutmut]`: `source_paths`, the cited files; `pytest_add_cli_args`,
`--redline-spec=<ID>`, so only the scenario's tests run against a mutant and a kill by any other
test can't count; and `also_copy`, below. mutmut reads `[tool.mutmut]` from `pyproject.toml`
when that table exists, and then never reads `setup.cfg`, so the repository's own settings would
name other files and drop the filter, crediting the scenario with every other test's kills. So the
table is taken out of the copy's `pyproject.toml` by text, and Python's TOML parser checks that the
result is the original without `tool.mutmut`, so pytest's own settings there stay as they were. A
table it can't take out that way, such as an inline `tool = { mutmut = … }`, is an error, not a
guess. mutmut copies only `tests/`, `test/`, root `test*.py` files and a few config files into
its `mutants/` directory, so `also_copy` adds the directory of each of the scenario's tests, of each
`conftest.py` from the root down to them, and of each `support:` file (§4), or the file itself at
the root: mutmut copies a listed file without making its directory. `support:` is read from the
tree, as `reach` reads it, since check-break counts as evidence only on `main`.

Stryker mutates in its own sandbox, so no copy of the repository is made (copying `node_modules`
is costly): `npx --no-install stryker run --mutate <files> --testRunner jest --reporters json`,
with `REDLINE_SPEC=<ID>` so its Jest workers run the scenario's tests alone (below). Its report,
`reports/mutation/mutation.json`, is read and then deleted. A mutant is **made** when its status
is `Killed`, `Survived`, `NoCoverage` or `Timeout`, and **killed** only when it is `Killed`: a
timeout isn't a kill, as for mutmut. `CompileError`, `RuntimeError`, `Ignored` and `Pending` aren't
counted. Stryker is unavailable, with the reason, without `npx` or without `@stryker-mutator/core`
or `@stryker-mutator/jest-runner` in `node_modules`. It is proved on the real tool (below), and
check-break calls it for a scenario with a Jest test.

**Runners.** A test file's extension decides its runner, and nothing in `redline/config.yaml`
changes that: a switch there could hide tests from check-links and the lock, and a configurable
command could make a suite pass by running nothing. Each runner sits behind the `Runner` seam in
`redline/runner.py`. It knows the files its markers are read from, the files that are tests
(which check-track doesn't count as code), how its marker reads, where each test starts and ends,
and the command that runs its tests, all of them or one scenario's. Its mutation tool is the
`MUTATORS` registry's (above).

| Runner | Markers read in | Test files | Run | Marker | `new` | Mutation |
|---|---|---|---|---|---|---|
| pytest | `*.py` | `test_*.py`, `*_test.py`, `conftest.py` | `python -m pytest`, `--redline-spec=<ID>` | `@pytest.mark.spec("ID")` | `spec("ID", new=True)`: `xfail(strict=True)` | mutmut |
| Jest | `*.js`, `*.jsx`, `*.mjs`, `*.cjs`, `*.ts`, `*.tsx` | `*.test.<ext>`, `*.spec.<ext>`, `*__tests__/*.<ext>`, for those extensions | `npx --no-install jest --ci`, `REDLINE_SPEC=<ID>` | `spec("ID").test("name", fn)` | `spec("ID", { new: true }).test(…)`: `test.failing` | Stryker |

check-links, check-order, check-break and the lock read every runner's markers, so a scenario may
be linked from either language. They read them with one function per runner, the one that finds
its tests (below), so the four can't disagree. A marker counts only where its runner reads it.
pytest's is a decorator of a test function (at module level, or a method), read with Python's
parser: a commented-out `# @pytest.mark.spec("X", new=True)`, or a marker inside a string, is no
marker, so it makes no red and links nothing. The plugin refuses a `spec` marker pytest would
apply from anywhere else, a class decorator, `pytestmark` or `pytest.param(marks=…)`, since
Redline doesn't read it there. Jest's is a `spec(` call in code, found by one scanner (below)
that blanks comments and the contents of strings and template literals, keeping each offset and
newline: a `// spec("X", { new: true })`, or one inside a string or a template, is no marker. The
code of a template's `${…}` is code, and Jest runs a test written there, so a marker in it counts.
The ID and `{ new: true }` are read from the original text at the offset found. A marked function pytest doesn't collect still counts
(O-RUN6). Jest's test files are its default `testMatch`, by extension only, so an
`openapi.spec.json` stays code.

check-order reads each commit's test files from git: each runner's files in the commit's tree,
each blob read once and its markers kept by blob hash, so a file unchanged across commits is
parsed once, and only a file whose text matches the runner's grep pattern is parsed at all. A file
that doesn't parse at a commit, such as a syntax error committed mid-history, gives no markers
there, and check-order prints `skipped <path> at <commit>: <error>`. History can't be rewritten,
so failing would fail every later PR, and reading its lines as text would let comments and
strings count again. Skipping can only drop a red or a green, never make one, and a green whose
red was dropped fails, where it is seen. In the working tree a file that doesn't parse is an
error: check-links reports it as a gap, and the lock refuses.

The suite `redline ci` runs is every test of each runner the repository uses, run by the command
check-break runs (all tests, no `REDLINE_SPEC`). pytest is used when git tracks one of its test
files; Jest when the root `package.json` lists `jest` in `dependencies` or `devDependencies`. Jest
listed without `npx`, or without `node_modules/jest`, fails the suite, naming what is missing, and
so does a repository that uses no runner: a run that didn't happen proves nothing. Each runner that
fails gives one line, `suite: the test suite failed (<runner> exit <code>): <last line of its
output>`. Jest tests a root `package.json` doesn't list Jest for never run there (O-RUN9).

Jest has no marker, so Redline ships one. `redline install jest` writes `redline/runners/jest.js`,
which tests import. It isn't named `spec.js`: Jest's default `testMatch` takes any `spec.js` for a
test file, and a file with no tests fails the run. `spec(id)` returns an object whose `test` is Jest's `test`, or `test.failing`
for `{ new: true }` (Jest 28.1 or later, with jest-circus; without it the helper throws), so a
`new` test that passes fails the run. Under `REDLINE_SPEC=<ID>` it skips every test that isn't
linked to that ID without `new`, which is how a scenario's tests alone are run. A weakened helper
would undo all of that, so every gate, at every step and outside one, runs check-helpers: it fails
if `redline/runners/jest.js` exists and differs from the copy in the installed Redline.

**Proved on the real tools.** The suite fakes Jest and Stryker, so a second CI job, `runners`,
runs them on a toy project, `tests/toys/jest`, with Node and the project's packages pinned (its
`package-lock.json`). It runs `tests/test_runners.py` with `REDLINE_REAL_RUNNERS=1`; without that
variable those tests are skipped, and with it a missing tool fails them. They prove that the
helper runs a `new` test as `test.failing`, so a `new` test that passes fails the run; that the
helper isn't taken for a test file; that `REDLINE_SPEC` runs one scenario's tests alone; and that
Stryker counts as above, with `REDLINE_SPEC` reaching its Jest workers: of the 6 mutants of the
toy's `adult`, TOY.H1's test kills 4 and TOY.H2's all 6. They also run check-break end to end on
a git repository holding the toy, its `node_modules` linked rather than copied, and a delta whose
premise cites `src/adult.js`: TOY.H1 and TOY.H2 hold, and a TOY.H3 test that asserts nothing
about `adult` survives all 6 mutants and fails.

A Jest test is `path::name`, where the name is the first argument of its `test` call, a string
literal. Two tests in one file with the same name are an error, since a `describe` around them
isn't part of the name. Its hash covers its source from `spec(` to the `)` that closes its `test(`
call. The same scanner finds that `)`, counting brackets in the blanked text, so its strings,
templates and comments hold none, while a `${…}` balances its own. The scanner doesn't know regex
literals (O-MARK3): one with an unbalanced bracket misreads the count, and one with a quote, a
backtick or `/*` is read as opening a string, a template or a comment, which hides code, never
shows a marker that isn't there. A string ends at the end of its line, so `/"/g` hides the rest
of that line only. Brackets that don't balance, or a template or block comment still open, by the
end of the file are an error, never a shorter hash or a file blanked to its end: check-links
reports it as a gap, check-order skips the file at that commit with a note, and the lock refuses.

At critical, a Jest entry has no `reach` (O-RUN3), so check-lock reports
it as a critical entry without one: a critical change can't lock a Jest test yet.

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

A frozen test is frozen whichever change locked it. At every step, S, R, G and C, the gate runs
that check on every change the lock names, as a PR outside a step does (§7), and on the step's own
change at R and G, so every hold test is in the lock and current. It also compares the lock **by
test** with the lock at the merge-base with `main`: a test frozen there, in any change's entry,
has changed when a hash it had differs now, in whichever entry holds it, or it is in no entry.
Without that, a step could edit a frozen test, its own change's or another's, and re-run `redline
lock`. A `reach` added where the merge-base had none hasn't changed it: the frozen source is the
same, and it is now checked further. At R, the step's new tests weren't frozen at the merge-base,
so locking them changes nothing. At G1…Gn the gate adds, with `--base main`, an entry of the
step's change added since the merge-base: tests are locked at R. `pr` and `redline ci pr` run
every check.

**Timing is part of what a frozen test expects** (`../migration-engine`, "The safety net is
frozen"). A test that asserted an effect at once and now waits for it, or waits longer, expects
something else with every value unedited. In Python and pytest, timing is any of these:

| Timing | Where | Caught by |
|---|---|---|
| `time.sleep`, `asyncio.sleep`; a poll loop and its bound (`range(50)`, a deadline); a `timeout=` argument | the test's body | the function hash, every level |
| `@pytest.mark.timeout(n)`, `@pytest.mark.flaky(reruns=n)`, Hypothesis `@settings(deadline=…)` | the test's decorators | the function hash, every level |
| any of the above in a fixture or helper; a constant such as `TIMEOUT = 5` | the test's file, its `conftest.py` files, the support files it imports from | `reach`, critical |
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
- **What it doesn't follow**: an import from a file `support:` doesn't name; `from m import *`;
  an import inside a function; a name deeper than `m.name` (`m.sub.name`, `obj.attr`); fixtures
  from installed plugins or `pytest_plugins` modules; `request.getfixturevalue`; a fixture
  renamed with `@pytest.fixture(name=…)`; a module found through `sys.path` edits or an import
  mode other than the default `prepend`.
- **That the code under test still meets the bound.** The lock freezes what the test expects,
  not what the API shows while it waits. The migration engine pins that with a second test
  outside the frozen set, which the departure's spec names. Redline doesn't check that it exists.

Editing a frozen test is a **departure**, at any step: an R step too, when another change froze
the test before it. The step re-runs `redline lock`, and one of its
commits carries a trailer naming the test, the person and the reason:

```
Redline-Departure: tests/test_greet.py::test_placeholder_returns_nothing approved-by @maintainer: the placeholder now returns ""
```

A test with a trailer like that among the step's own commits (`base..HEAD`) may change its lock
entry. Every other check still applies, so the lock must match the edited test. A trailer
missing `approved-by @person: <reason>` doesn't count. The test is everything before the last
` approved-by @`, so a Jest test whose name is a sentence can be named (O-RUN7). The trailer
stays in `main`'s history, so the departure is recorded with its approver (§2.7). The trailer is
only a claim, so in CI it also needs a maintainer's `redline:departure` label on the PR (§7).

**One track per Green PR.** A G step's **track** is the code it may change: the `Track:` line
under its heading in `steps.md`, a comma-separated list of globs, matched as `generated:` globs
are (§2.3). It is written at S, so the auditor sees what each G step will touch before any code
exists, and the step's brief prints it for the implementer. A Green PR then changes one track:
its own.

At a G step, `pr` and `redline ci pr` run check-track. It fails on:

- **No `Track:` line**, or an empty one, at critical. Below critical the line is optional; if it
  is there, it is checked.
- **A file outside the track**: a file the step's diff (from the merge-base with `main`, renames
  as a delete and an add) adds, edits or deletes that matches none of the track's globs. Not
  counted: anything under `redline/` (the lock, the ledger, the defect log), test files (each
  runner's, Runners above, and `support:` files, §4), and `generated:` files.

The track is read from `steps.md` at the merge-base, as the auditor saw it, not from the PR: a
step that widened its own `Track:` line would pass any diff. The `support:` and `generated:` globs
it exempts are read there too, from `redline/config.yaml`, as check-lines reads `generated:` (§7). A file outside the track is a
claim, like `Oversized`: a `Redline-Track: <reason>` trailer among the step's commits and a
maintainer's `redline:track` label (§7). Without the trailer, it fails.

Two G steps' tracks may overlap: G2 often builds on code G1 wrote, and keeping them apart would
force splits that make no sense. The check is that a Green PR stays where it said it would.

**The close is checked against the evidence.** A ledger that matches `main`'s history can still
be incomplete: a `new` scenario that never turned green, a result CI never noted, a break that
failed. check-ledger passes all three, so at the C step `pr` and `redline ci pr` also run
`redline check-close <change>`. It rebuilds the ledger from `main` and fails, naming the scenario,
on:

- **A `new` scenario without both a red and a green**, or either with a `result` that isn't
  `pass`. The red's result is the suite's on its merged commit, which passes because the test
  failed strictly, as it should.
- **A `hold` scenario without a break**, or one whose `result` isn't `pass`.

A scenario is `new` or `hold` by its tag in the delta, and its evidence is only what its own
steps made (§4, a change's window): a scenario a closed change proved doesn't close a later
change that MODIFIES it. It runs at C only, since at G a scenario
owned by a later step has no green yet by design; run on its own, it checks as at C.

`unverified` refuses: until CI has run on the merged commit, there is no evidence (§7). A C PR
opened right after the last G merges usually waits so, for that merge's push run. The refusal says
it is waiting, not wrong: once the note on that commit lands, fetch it (`git fetch origin
'refs/notes/*:refs/notes/*'`), run `redline ledger <change>`, commit and push. The committed ledger
must then say `pass` too, or check-ledger fails. Nothing else in the PR needs to change.

What it doesn't prove: that the scenario's own test ran. A result is the whole suite's on the
merged commit, and a test skipped there passes with it.

There is no verify report. The ledger, which CI rebuilds, already holds the evidence, and
check-close reads it. A report the agent wrote would either repeat the ledger or be the agent
certifying its own work (§2.6).

**The delta reaches the living specs.** At C, `pr` and `redline ci pr` also run `redline
check-specs <change>`. It compares each scenario of `redline/specs/**/spec.md` at the merge-base
with `main` to the same scenario now (a scenario is its heading line up to the next heading,
trailing blank lines dropped, and the `### Requirement:` it sits under), and fails, naming the
scenario, on:

- **A scenario heading in no section**: not under ADDED or MODIFIED, or a heading under REMOVED.
- **ADDED**: the domain's living spec already had it at the merge-base, or doesn't have it now with
  the delta's text under the delta's requirement.
- **MODIFIED**: the living spec didn't have it at the merge-base, or doesn't have it now as above.
- **REMOVED**: the living spec didn't have it at the merge-base, or still has it.
- **A change the delta doesn't name**: a scenario anywhere under `specs/` added, changed or removed
  since the merge-base that none of the change's deltas names. A C step changes only what its
  deltas say.

It compares with the merge-base, so it is the C PR's gate; run on its own it takes `--base`
(default `main`), and run on `main` after the merge it has no diff to read and fails. What it
doesn't prove: anything outside the scenarios. A requirement's own prose, a `### Requirement:`
heading with no scenario under it, or text before the first requirement, can change unseen.

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
the changes are independent, each with its own sessions. In a critical initiative, it also
refuses while the phase's start audit, or an earlier phase's end audit, is missing or unresolved
on `main` (§4, plan audits). Both refusals read `main`: its plans, the `steps.md` of each change
they list, the levels that make an initiative critical (each proposal's `Rigor:`, else the config's
`rigor:`), and the audits. That is the working tree too, since `start` refuses a branch that isn't
fresh from `main`. `start` runs on the agent's machine, so `redline ci pr` repeats all three on
every step's PR: the step must be the change's next, and its phase must be ready (§7).

`pr` runs check-lines and check-plan always, check-premises and check-audit at S (on the step's own change: an
older change's premises may go stale as the code moves on), and check-links and check-order from
the R step on (at S the delta's scenarios have no tests yet; check-order skips `hold` scenarios,
which have no red by design), check-break at the R step only, check-lock at every step (on the
whole lock, by test, against `main`'s; G steps with `--base main`, §5), check-track at G steps (§5), check-close and check-specs at the C step (§5), check-defects and check-relabel at every step on the
step's change (the log is required only at C, the relabel only at C and critical), and the rigor
check at every step (§7). A departure or an `Oversized` trailer doesn't refuse: the PR and its
labels don't exist yet, so `pr` prints that CI will need the label (§7). Only when every gate
passes does it put the `Redline-Step` trailer on each of the step's commits (once), push, and open
the PR with `gh`.

`merged <step>` fetches and fast-forwards local `main` first, then looks for the step's trailer on
`main` and refuses if it isn't there. Once it is, it switches to `main` (the next step starts fresh
from it, so uncommitted changes refuse before anything syncs), clears the open-step record if the
step it names is merged, and prints the next step's brief, or that the change is complete after C
and that `redline retro <change>` comes next (§10), then its progress (below).
When that completes the change's phase, it also prints that the initiative is at a stopping
point, and the phase's `Stop:` line. Then it prints the next phase and its changes, or that the
initiative is complete. It starts nothing: going on is the maintainer's call. In a critical
initiative it also prints the plan audits now due (§4): the phase's end, and the next phase's
start, or, after the last phase, the three end-of-initiative audits, and the plan's blob to give
each auditor, and, to the process auditor, the text `redline claims <initiative>` prints.

The brief (goal, owned scenario IDs, cited files, open items, the rules of `redline/config.yaml`)
is generated from the spec, the ledger, the open items and the config. For a change in an initiative, it also gives the initiative's goal,
the phase and its `Stop:` line, so a session knows what its change is for. It's the whole
hand-off: a new session needs nothing from the old one.

**Progress.** The brief ends with how far the work has come, from what `main` holds, so `start`
and `merged` both show it, once each; after C, where no brief follows, `merged` prints it alone.
One function, `progress` in `redline/progress.py`, writes it for both:

```
## Progress
add-greet: [████░░░░░░░░░░░░░░░░] 1 of 5 steps merged · next: add-greet/R
Phase 1 of 2 (Greet): [██████████░░░░░░░░░░] 1 of 2 changes complete
greetings: [░░░░░░░░░░░░░░░░░░░░] 0 of 2 phases complete
Open items later steps own:
- O2 [G2]: names with spaces
```

The first line counts the change's steps of `steps.md` merged on `main` and names the first that
isn't, or says `the change is complete`. A change in an initiative adds its phase's changes
complete and the plan's phases complete, as `start` reads completeness (§4): a change with no
`steps.md` yet isn't. Without an initiative those two lines are left out. Then the open items whose
owning step isn't merged, or `(none)`. An item owned by a merged step isn't printed: whether it was
done is the auditor's to say, not the bar's. A bar is 20 characters, filled `n × 20 ÷ total`
rounded down, so it is full only when everything is done. It prints and judges nothing, as `merged`
does: no count refuses or fails.

## 7. Trust model

| Source | Counts as evidence? |
|---|---|
| CI run on a merged commit | Yes, and only this |
| CLI run locally | A preview, which CI re-runs |
| The agent's report or summary | Never |
| `ledger.yaml` | A cache, which CI rebuilds from history |

CI is `.github/workflows/redline.yml`, a thin wrapper around `redline ci`; every rule lives in the
CLI. It checks out the full history, `main` and `refs/notes/*`. A second job, `runners`, runs the
real Jest and Stryker on a toy project, and the real mutmut on toy repositories (§5), and records
nothing. The mutmut toys hold a scenario whose test kills no mutant beside a test that kills them
all, so a kill credited to the wrong test shows. A repository with Jest tests
installs Node and runs `npm ci` in its workflow before `redline ci`, so the suite can run them. A
third job, `windows`, runs Redline's own suite on Windows with a read-only token, and records
nothing either. It runs pytest, not `redline ci`: mutmut doesn't run on Windows, and a skipped
break fails the run (§5).

**Text is UTF-8, on every platform.** Windows' Python decodes and prints text in the code page
(cp1252) unless told otherwise, while git writes, and Redline's files hold, UTF-8. So every file
Redline reads or writes says `encoding="utf-8"`, and a file that isn't UTF-8 is an error. What it
reads from a process (git, `gh`, mutmut, a runner) is UTF-8 with `errors="replace"`, since a
process may print bytes that aren't UTF-8 and failing there would fail inside `subprocess`. `git()`
runs with `-c core.quotePath=false`, so a path outside ASCII reads as itself, not as a quoted
`"t\303\274.py"` that names no file. `main()` reconfigures stdout and stderr to UTF-8 with
`errors="replace"`, so a brief printed into a pipe, as an agent session reads it, never fails on a
"≤". A reader that decodes the pipe in its console's code page shows those characters wrongly, but
nothing is lost or fails. In a console, Python already writes Unicode. So the progress bar (§6)
prints `█` and `░` with no ASCII fallback, which would never run: its counts are digits, and read
without the bar.

On a pull request, `redline ci pr --base main` works out the step from the `Redline-Step`
trailers of the PR's own commits (`main..HEAD`), which `pr` added. It refuses if they name more
than one distinct step: a PR is one step.

It also refuses, before anything runs, a step that isn't next, as `start` does (§6): the step must
be in the change's `steps.md` at the merge-base with `main`, every step before it there must be
merged on `main`, and the step itself must not be. A change with no `steps.md` at the merge-base
may only be at its S step, which writes it. Without this, a trailer could name a step that doesn't
exist, which `gates` gives the fewest checks, or one already merged, such as a closed change's R,
whose gates don't run check-specs, while the PR still counts as in a step and may touch
`redline/changes/`, `redline/contracts/` and `redline/specs/`; and a G1 PR could pass CI before its
S step merged, against invariant 1. `steps.md` is read at the merge-base, as check-track reads
`Track:` lines (§5), so a PR can't add itself a step.

Then, still before anything runs, `start`'s other two refusals (§6), by the same function: a change
whose earlier phase isn't complete, and, in a critical initiative, a step while an earlier phase's
end audit, or its own phase's start audit, is missing or unresolved, or that start audit isn't
current. Everything they read comes from the merge-base: the plans, the `steps.md` of every change
they list, the proposals' `Rigor:` lines and the config's `rigor:`, the audits and the plan's blob.
Only what is merged is read from `main`, as above. A step's PR may edit any of those files, so a
PR read from its own tree could move its change to an earlier phase (a plan edit, not a claim),
trim an earlier change's `steps.md` to the steps already merged, lower a proposal's `Rigor:` so no
audit is asked for, or add the audit it lacks. At `start` the branch is fresh from `main`, so the
merge-base is the tree `start` read, and CI asks the same question of the same files. The plan,
its blob and its audits come from one tree, so an audit is current against the plan beside it.

What it doesn't prove: a plan edited on `main` after the step's branch forked, which makes its
start audit stale. The step's PR is read at the fork, where the audit was current, as `start` read
it. That is by design: the step began under an audited plan, and a later edit is read by the next
step's `start` and, through the end audit, by check-plan on every PR (§4).

It then runs that step's gates (the same ones `pr` runs
locally), the test suite, and `check-ledger <change> --main main`, and prints every failure. This
proves the PR's state: the gates hold, `new` tests fail strictly, and the committed ledger
matches `main`'s evidence. It records nothing. A PR run is not evidence, because its commits are
not on `main` yet.

A PR whose commits carry no `Redline-Step` trailer is **outside any step**: a rule PR from
`retro` (§10), a plan edit, or a change to Redline itself. It is opened with `gh`, not `pr`.
`redline ci pr` refuses it, before anything runs, if it touches `redline/changes/`,
`redline/contracts/` or `redline/specs/`, and names each such file. Those files belong to steps:
a proposal, delta, audit, defect log and ledger are written at S, R and C; the lock is rewritten
only at R, or at G with an approved departure; deltas reach `specs/` at C. Outside a step, none
of those gates would run, so a step could dodge them by leaving its trailer off.

Otherwise it runs the gates that hold for any PR, and prints every failure:

- **check-lines**, with the `Oversized` rule (§7, Approvals): over 400 lines needs the trailer and
  a maintainer's `redline:oversized` label.
- **check-plan** on every initiative.
- **The rigor check**: a changed `rigor:` or `Rigor:` line, a change's level lowered, a glob added
  to `generated:` or `support:`, a deleted plan or a change taken out of one needs `Redline-Rigor`
  and its label
  (Approvals, below).
- **check-lock** on every change the lock names, without `--base`. The PR can't touch the lock,
  so a locked test or (at critical) what it reaches can't change outside a step at all. A
  `Redline-Departure` trailer doesn't help: a departure is a step's, and re-locks the test.
- **The test suite**: each runner's the repository uses (§5).

It doesn't run check-links (on `main` an S step's scenarios have no tests yet, by design),
check-ledger or check-defects (they are a change's, and the PR can't touch a change).

On a push to `main`, `redline ci push` runs the suite on the merged commit and writes the note
(`result: pass|fail`, `run: <url>`) on it under `refs/notes/redline-ci`, then pushes that ref;
with `--note <file>` it writes the note's text to the file instead, which is how the workflow runs
it (below). A failed suite is still recorded, and the run fails. This is the only evidence Redline writes, and
the next PR's `check-ledger` picks it up.

When the merged commits (`<merged>^..<merged>`: the PR's own commits under a merge commit, the
commit itself after a squash) carry claim trailers (Approvals, below), it also records the
approvals as they stand at the merge, for `redline claims` (§4). Through the `GitHub` seam it
reads the merged PR of the first commit with a claim, the PR's labels with who applied each last,
and that person's role, and adds one entry per claim under `claims:`:

```
result: pass
run: https://github.com/acme/app/actions/runs/7
claims:
- commit: 4d5e6f1…
  claim: 'Redline-Departure: tests/test_login.py::test_lockout approved-by @maintainer: five, not three'
  pr: 12
  label: redline:departure
  by: alice
  role: admin
```

`pr` is null when GitHub associates no merged PR with the commit; `by` and `role` are null when
the label isn't on the PR. The record judges nothing: a label applied by someone who isn't a
maintainer is recorded as it is. A merge without claims gets no `claims:`, and `result:`, `run:`
and `break:` are as before, so the ledger reads the note as it did. If GitHub can't be read, the
note is written without the record and the run fails, so the result is kept and the gap is seen.
A re-run of the push job keeps a record an earlier run wrote: labels read later are what the
record exists to avoid.

**Only a job that runs no repository code can write the notes.** A run executes the code it
checks out: `pip install -e .`, every `conftest.py`, every test, the PR's own on a PR and the
merged ones on a push. A token that can write `refs/notes/redline-ci` there would let that code
write `result: pass` or a `break:` map on any commit, which is the evidence this section trusts.
So the workflow's default token is `contents: read`, and each job says what it holds:

- **`redline`**, on both events, holds `contents: read`, with `issues: read` and `pull-requests:
  read` for the labels. Its checkout sets `persist-credentials: false`, and the step that fetches
  `main` and the notes passes the token to that one `git fetch` itself, so a private repository
  still fetches. On a push it runs `redline ci push --note <file>`: the suite, check-break at R
  and the claims record as above, but the note's text goes to the file, nothing is added under
  `refs/notes/redline-ci` and nothing is pushed. A step that runs even when the suite failed, so
  a failed run is still recorded, hands the file on as a job output, base64-encoded, since a claim
  trailer's text could hold the delimiter of a multi-line output.
- **`note`**, on a push only, after `redline`, is the only job with `contents: write`. It checks
  the merged commit out and runs git alone: decode the output, then fetch `refs/notes/*`, `git
  notes add -f` it on `$GITHUB_SHA` and push the ref, up to five times (below). The output reaches it through an environment
  variable, never a `${{ }}` inside a script, which would run the note's text as shell. A checked
  out tree can't make git run code: hooks and filter drivers come from git's config, which a
  repository doesn't carry. The commit it notes is the workflow's, not something `redline` said,
  so merged code can choose only the text of its own merge commit's note, as before.
- **`runners`** and **`windows`** hold `contents: read` and set `persist-credentials: false`.

A test reads the workflow and fails when any job but `note` holds `contents: write`, when a job
that runs repository code keeps its credentials, and when `note` has a step that isn't
`actions/checkout` or a line that isn't one of its git commands, the decode or the retry loop's
shell: `pip`, `python`, `redline`, a script in the repository or a local `uses: ./…` action would
all be repository code.

**Every merged commit gets its note.** GitHub keeps at most one running and one pending run per
concurrency group, and cancels the pending one when another queues, whatever
`cancel-in-progress` says. One group for every push to `main` would leave the middle of three
quick merges without a run, so its red, green or break stayed `unverified` and check-close
refused until someone re-ran it by hand. So a push run's group is its own run's
(`github.run_id`), and nothing cancels it. A PR run's group is still its ref: only its newest
head and labels count, and runs one at a time finish in order, so the check shows the newest
answer. Nothing else needed push runs in order: each notes only its own `$GITHUB_SHA`, and the
claims record reads only that commit's note.

Push runs now race to push `refs/notes/redline-ci`. The push isn't forced, so a run whose fetch
another run's push has overtaken is refused, and the `note` job tries again: it fetches the ref
over its own, adds its note again and pushes, five times at most, waiting a second longer each
time. Since a run adds one note, on its own commit, that is the same as merging the notes with
its own winning, and every other run's note is kept. After five refusals the job fails, where it
is seen. A test runs the job's own script, read from the workflow, against a bare repository
whose hook writes another run's note and refuses the first push.

**What CI runs is pinned.** CI's runs are the evidence, so two runs of one commit run the same
tools unless a commit changes them. Each action is used by its full commit SHA, its release tag in
a comment (`actions/checkout@11d5960…  # v4.4.0`), since a tag can be moved to other code; an
action has one SHA throughout. Python and Node are exact versions: `3.12` gave Linux 3.12.15 and
Windows 3.12.10 in one run, so Linux is `3.12.15` and Windows `3.12.10`, the last 3.12 GitHub
builds for Windows (3.12's later releases are source-only security fixes); Node is `22.23.3`.
Every `pip install` takes `-c constraints.txt`, which pins with `==` every package any job
installs, on Linux and Windows, and no pip line pins a version of its own. The build backend is pinned in `pyproject.toml`'s `[build-system]` itself
(`setuptools==84.2.1`), since whether `-c` reaches pip's isolated build environment depends on
pip's version. `npm ci` already installs from the toy's `package-lock.json`.

Tests read the workflow: every `uses:` is a 40-hex SHA with a `# vX.Y.Z` tag, every
`python-version` and `node-version` is `X.Y.Z`, and every `pip install` has `-c constraints.txt`
and no `==`; and every dependency and extra in `pyproject.toml`, and pytest-xdist, has an `==`
line in the file. A constraints file pins only what it names, so a release that adds a dependency
would install it unpinned. So one more test, which runs only in GitHub Actions, follows what the
pip lines pull in, from the installed metadata: Redline's requirements, its `mutation` extra where
mutmut is installed and pytest-xdist where it is, and their requirements in turn. It fails on any
of those that isn't in the file at the version installed. It runs with the suite, in the `redline`
and `windows` jobs. It follows requirements, not every installed distribution, because a runner
image brings tools of its own that no job installs or runs: Windows' Python carries pipx and its
dependencies.
The pins are kept current by hand: the file's header gives the command that regenerates it, and a
bump is a PR outside any step, gated like any other.

What it doesn't prove: that GitHub enforces the permissions it is given, or that the actions the
jobs use are sound: a pin stops a moved tag from changing them, but the pinned commit is trusted as
it is. The toolchain is pinned by version, not by hash, so an index serving other files under a
version isn't caught; the runner images (`ubuntu-latest`, `windows-latest`), and pip, which comes
with the pinned Python, change with GitHub's updates. Nor does it prove the note's text, which merged code
still writes for its own merge commit, as it runs the suite that says `pass`. A token with
`contents: write` held elsewhere, a maintainer's or an agent's given one, still writes any note
(§4).

### Approvals

A person's approval is a label on the PR, applied by a maintainer. A commit trailer in the PR's
own commits (`base..HEAD`) says what is approved and why, and stays in `main`'s history. The label
says a maintainer agreed. Four claims need one:

| Trailer | Allows | Label |
|---|---|---|
| `Redline-Departure: <test> approved-by @person: <reason>` | a frozen test's lock entry to change (§5) | `redline:departure` |
| `Oversized: <reason>` | more than 400 changed lines (§2.3) | `redline:oversized` |
| `Redline-Track: <reason>` | a G step changing files outside its track (§5) | `redline:track` |
| `Redline-Rigor: <reason>` | a change to `rigor:` in `redline/config.yaml` or to a plan's `Rigor:` line; a change's level lowered; a glob added to its `generated:` or `support:`; a plan deleted, or a change taken out of one | `redline:rigor` |

`rigor:` sets the level of every change whose proposal names none, and so what all their gates
require, so changing it, up or down, is a claim on any PR, in a step or outside one (§7). A plan's
`Rigor:` line sets whether its initiative's plans are audited (§4), so it is the same claim. The
rigor check compares the config's `rigor:` at the merge-base with `main` to its value now, and
each plan's `Rigor:` there to its line now (none, for a plan without one or one deleted), and
each plan's changes there to its changes now (a deleted plan lists none, §4), and fails on a
difference without the trailer, or, in CI, without the label. A new plan declares its level and
its changes without a claim, as a new proposal does.

A change's level (its proposal's `Rigor:`, else the config's `rigor:`, §4) sets what its own gates
require: the defect log and the relabel at C, a `Track:` line on every G step, `reach` in a
critical lock entry, and whether its initiative is critical, which asks for plan audits. So the
rigor check also reads the level of each change with a proposal at the merge-base, there and now,
and fails on one that is lower now, naming the change and both levels. Only lowering is a claim: a
raise asks more of every gate, and it is the auditor's to make (§8). A proposal new since the
merge-base declares its level without a claim. A deleted proposal or a removed `Rigor:` line
takes the config's level, and is a claim when that is lower. A lowered `rigor:` also names each
change it lowers. An unknown level, there or now, fails, and no trailer allows it. The gates read
the level from the tree, as they read `rigor:`: a lowering not approved fails the rigor check, and
an approved one holds from the PR that makes it, as a raise does.

`generated:` and `support:` say which files the gates don't count: check-lines leaves out
generated files, and check-track exempts both (§5). Each gate reads them at the merge-base, so a
PR can't widen them for itself, as a step can't widen its own `Track:` line. But a glob merged
once holds for every PR after it: `generated: ["*"]` would end the 400-line gate. So the rigor
check also fails on each glob in either list now that the config at the merge-base doesn't have,
a new config's included; it names the glob. It is the same claim: what the maintainer approves
is that later PRs face less. Removing a glob isn't a claim, and nothing judges whether one glob
covers another: an added glob is a claim even when an old one already matched what it matches.
The cost is that a PR adding a lockfile counts its lines unless an earlier PR declared its glob.

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
public APIs are critical) but never lower it. Nor may a step: lowering a change's level once its
proposal is on `main` is the rigor claim, a maintainer's decision (§7, Approvals).

## 9. Roles

| Role | Model | Can |
|---|---|---|
| Maintainer (a person) | — | Merge; approve waivers, departures, `Oversized` |
| Main session | Strong | Specs, briefs, review, breaks, PRs |
| Auditor | Strongest, fresh context | Read and report only |
| Plan-auditor | Strongest, fresh context | Read and report on an initiative's phase, at its start and end |
| Relabeller | Strongest, fresh context | Label defects from their text, blind to the first label |
| End-of-initiative auditors (3) | Strongest, fresh context each | Read and report on a whole initiative, each from one side, none reading another |
| Implementer | Cheaper | Code from a brief; never commits |

The CLI holds the rules; each AI tool gets thin skills or commands, as in OpenSpec.

For Claude Code the auditor is `.claude/agents/redline-auditor.md`: tools `Read, Grep, Glob` only,
`model: fable`, and it refuses on any other model rather than run on a weaker one. Claude Code
can't limit Write to one file, so the auditor stays read-only and replies with the whole
`audit.md`, which the main session writes unedited. A re-run reads the old `audit.md`, keeps
every finding and closes only what it has checked. The `Waived-by:` line is the maintainer's.

The relabeller (§4, blind relabelling) is `.claude/agents/redline-relabeller.md`, the same way:
tool `Read` only, `model: fable`, and the same refusal. It is given the text `redline blind`
prints and, on a re-run, the old `relabel.yaml`, whose entries it keeps unchanged. It labels
only from the entries' text, reads no other file, and replies with the whole `relabel.yaml`.

The plan-auditor (§4, plan audits) is `.claude/agents/redline-plan-auditor.md`: tools `Read,
Grep, Glob`, `model: fable`, the same refusal. It is given `<initiative> phase <n> start|end
with plan <blob>`, reads the old audit file on a re-run with the auditor's rules, and replies with
the whole file, its `Plan:` line the blob it was given.

The end-of-initiative auditors (§4) are `redline-security-auditor.md`,
`redline-architecture-auditor.md` and `redline-process-auditor.md`, the same way: `Read, Grep,
Glob`, `model: fable`, the same refusal. Each is given `<initiative> with plan <blob>`, reads no
other audit file but its own, and replies with the whole `initiative-<side>.md`, `Plan:` line too.
The process auditor is also given the text `redline claims <initiative>` prints (§4), and without
it opens a finding: the record's claims are out of its sight.

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
   11, the actions pinned to commits and the toolchain to versions (O-CI7, O-CI8). The
   review's other code items join this step, each with its own O-ID, as they are taken.
10. **Progress in `merged`** (O-PROG1), after build 9's encoding fix, since the bar prints `█`.

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
- O-LOCK3 [closed, build 5 part 5]: `reach` stopped at the test's file and its `conftest.py`
  files, so helpers imported from shared test modules weren't locked. Now it follows imports into
  the support files `support:` in `redline/config.yaml` names, and only those, so the code under
  test stays out (§4). §5 lists what it still doesn't follow.
- O-RETRO1 [closed, build 6 part 3]: a rule PR from `retro` belongs to no step, so `redline ci
  pr` refused it, as it refused Redline's own PRs. Now a PR outside any step runs check-lines
  (with `Oversized`), check-plan, check-lock on every locked change and the suite, and is refused
  if it touches a change, the lock or the living specs (§7).
- O-CI1 [closed, build 6 part 4]: a PR outside any step could change `rigor:` in
  `redline/config.yaml`, which sets the level of every change whose proposal declares none. Now
  any PR that changes it needs a `Redline-Rigor` trailer and a maintainer's `redline:rigor` label
  (§7).
- O-CI2 [closed, build 9]: `redline ci pr` checked only that a `Redline-Step` trailer had a `/`. A
  trailer naming a step `steps.md` lacks got the fewest gates, and one naming a step already merged
  got that step's, while the PR, counted as in a step, could touch `redline/specs/` with no
  check-specs; and a G1 PR passed CI before its S step merged. Only the local `start` checked the
  order. Now CI refuses, before anything runs, a step that isn't in `steps.md` at the merge-base,
  one with an earlier step not merged on `main`, and one already merged (§7).
- O-CI3 [closed, build 9 part 2]: `start` also refused a change whose earlier phase wasn't
  complete, and a critical initiative's step while its plan audits on `main` were missing,
  unresolved or stale (§6); CI repeated neither, and both read the plan, the changes' `steps.md`
  and their levels from the working tree, which a step's PR may edit. Now one function makes both
  refusals, `start` reading `main` and `redline ci pr` the merge-base, before any gate (§7). A plan
  edited on `main` after a step's branch forked isn't read by that step's PR, by design (§7).
- O-CI5 [closed, build 9 part 9]: the workflow gave every job `contents: write`, and
  `actions/checkout` kept the token in `.git/config`, so a PR's own code (`pip install -e .`, its
  `conftest.py`, its tests) could push `refs/notes/redline-ci` and write `result: pass` or a
  `break:` map on any commit, and so could merged code on every push run; §7 said the push run's
  token was read-only. Now every job that runs repository code holds `contents: read` and keeps no
  credentials; `redline ci push --note` hands the note's text on, and a `note` job that runs git
  alone writes it on the merged commit, which a workflow test checks line by line (§7).
- O-CI6 [closed, build 9 part 10]: every push to `main` shared one concurrency group, and GitHub
  cancels a group's pending run when another queues, so the middle of three quick merges got no
  note: its evidence stayed `unverified` and check-close refused until a re-run by hand. Now a push
  run's group is its own, and the `note` job, whose push then races, fetches the notes again,
  re-adds its note and pushes, five times at most, which a test proves by running the job's script
  against a bare repository that refuses its first push (§7).
- O-CI7 [closed, build 9 part 11]: the workflow used its actions by tag (`actions/checkout@v4`),
  which the action's owner, or whoever takes over its repository, can move to other code, and §7
  said so as a limit. The security auditor checks other repositories for the same thing. Now each
  action is used by its full commit SHA with its tag in a comment, which a test checks (§7).
- O-CI8 [closed, build 9 part 11]: `pip install -e ".[mutation]"` resolved pytest, pyyaml, mutmut
  and their dependencies afresh on every run, beside a pinned pytest-xdist on Windows, and
  `python-version: "3.12"` gave two patch versions in one run, so a new release could change what
  CI's evidence says with no commit. Now Python is exact in every job (`3.12.15`, and `3.12.10` on Windows), every pip line installs from
  `constraints.txt`, setuptools is pinned in `[build-system]`, and a test in CI fails on an
  installed package the pip lines pull in that the file doesn't pin at its version (§7).
- O-CFG1 [closed, build 9 part 3]: check-lines and check-track read `generated:` and `support:`
  from the PR's own tree, so a PR could exempt its own files, and a string such as
  `generated: "*.lock"` was read as its characters, `*` among them. Now both gates read the globs
  at the merge-base, a glob added to either needs the `Redline-Rigor` claim, and a value that
  isn't a list of strings is an error (§4, §7). `reach` still reads `support:` from the tree, since
  its hash guards itself (§4).
- O-CI4 [closed, build 9 part 4]: the rigor check compared the config's `rigor:` and each plan's
  `Rigor:` line with the merge-base, but not proposals, so a step's PR could lower its own
  change's level from critical to lite and drop the defect log and relabel at C, the required
  `Track:` lines and its initiative's plan audits. Now a change's level lower than at the
  merge-base needs `Redline-Rigor` and the `redline:rigor` label; a raise doesn't (§7, §8).
- O-MARK1 [closed, build 9 part 5]: check-order and check-links read a marker as text on a line,
  so a commented-out `new=True` marker made a red whose test never failed, which check-close then
  accepted, and a marker inside a string linked its scenario: Redline's own history reported `ID`
  from the plugin's usage message. The lock read decorators, so the gates disagreed. Now one
  function per runner reads the markers for all four, pytest's from a test function's decorators
  with Python's parser, check-order's by blob hash; a file that doesn't parse at a commit is
  skipped with a note; and the plugin refuses a `spec` marker from a class, `pytestmark` or
  `pytest.param` (§5).
- O-MARK2 [closed, build 9 part 6]: Jest markers were read from the whole text, so a `new` marker
  in a comment, a string or a template made a red in check-order, linked its scenario in
  check-links and could be locked. Now one scanner blanks comments and the contents of strings and
  templates, keeping `${…}` as code; `spec(` is found in the blanked text, its ID read from the
  original, and the `)` closing a test is counted on the blanked text, so hashes are unchanged. A
  template or block comment never closed is an error (§5).
- O-MARK3 [build 8]: the Jest scanner doesn't know regex literals, so one with a quote, a backtick,
  `/*` or an unbalanced bracket misreads a file: it hides code or fails, never adds a marker (§5).
  A real JavaScript parser would read them, which O-RUN3's `reach` needs too.
- O-PLAN1 [closed, build 6 part 8]: an initiative was critical only through its changes' levels,
  and a change with no proposal yet takes the config's, so an initiative whose first S step
  declared `Rigor: critical` skipped that phase's start audit. Now the plan has its own `Rigor:`
  line, which only raises the level and changes only under the rigor claim (§4, §7).
- O-PLAN2 [closed, build 6 part 7]: nothing audited a whole initiative once its last phase was
  complete. Now three independent auditors (security, architecture, process) each return
  `audits/initiative-<side>.md`, and check-plan fails on every PR until all three are resolved (§4).
- O-PLAN3 [closed, build 6 part 8]: a plan audit wasn't tied to the plan it read, so a PR outside
  any step could change a phase's changes or its `Stop:` after the start audit and `start` still
  passed. Now each audit records the plan's blob in a `Plan:` line; `start` refuses a stale start
  audit, and check-plan a stale latest end audit or end-of-initiative audit (§4).
- O-PLAN4 [closed, build 6 part 9]: the end-of-initiative auditors read files only, so the claims
  git history holds (`Oversized`, `Redline-Track`, `Redline-Departure`, `Redline-Rigor` trailers,
  and who labelled them) were out of the process auditor's sight. Now `redline claims
  <initiative>` prints them from `main`, with each one's PR and label, and the process auditor is
  given that text as the relabeller is given `redline blind`'s (§4).
- O-PLAN5 [closed, build 6 part 10]: a PR outside any step could delete a plan that had no
  `Rigor:` line. Its changes left the initiative, and check-plan stopped asking for its audits.
  Now deleting a plan, or taking a change out of one, is the rigor claim: a `Redline-Rigor`
  trailer and a maintainer's `redline:rigor` label, checked by `pr` and `redline ci pr` (§4, §7).
- O-PLAN6 [closed, build 6 part 11]: `redline claims` read each claim's label and its applier's
  role when it ran, which may be long after the merge, so a label removed or added since, or a
  role changed, misreported what approved the PR. Now `redline ci push` records each claim of the
  merged PR, its label, who applied it last and their role, under `claims:` in the CI note on the
  merged commit (§7), and `claims` reads that record, saying when a commit has no note or no
  record (§4).
- O-PLAN7 [closed, build 6 part 12]: `redline claims` printed the steps of the changes the plan on
  `main` lists, so a change taken out of the plan, under an approved rigor claim, took its own
  claims out of the record the process auditor reads, and a deleted plan had no `claims` at all.
  Now `claims` takes the changes every version of the plan on `main`'s first-parent line listed,
  names each that has left the plan and where, and prints a deleted plan's initiative too (§4).
- O-CLOSE1 [closed, build 7 part 1]: check-ledger only compared the committed ledger with the
  one rebuilt from history, so a change could close with a `new` scenario that never turned green,
  a result CI never noted or a failed break. Now `check-close` runs at the C step and fails on any
  scenario whose red and green, or break, isn't on `main` with `result: pass` (§5).
- O-CLOSE2 [closed, build 7 part 2]: §5 said the C step merges the delta into `specs/` and adds a
  verify report, but nothing checked that the delta's ADDED, MODIFIED and REMOVED reached the
  living specs, and the verify report had no form. Now the delta's sections have a form (§4),
  `check-specs` runs at C and fails on a declared change missing from `specs/` or an undeclared
  one in it, and the verify report is dropped: the ledger and check-close are the verify (§5).
- O-CLOSE3 [closed, build 7 part 3]: a closed change keeps its delta, so when a later change
  MODIFIED a scenario an earlier one ADDED, check-links found the ID in the living spec and two
  changes' deltas and failed it as a duplicate; and a scenario a later change REMOVED stayed
  declared by the closed delta, so a test still linked to it wasn't unknown, as §4 says it is. Now
  a change whose C step is merged on `main` is closed, and check-links, the `hold` scenarios
  check-order leaves out, and `check-premises` without a change skip its delta (§4). Its own
  checks still read it.
- O-CLOSE4 [closed, build 7 part 4]: evidence was found by scenario ID across all of `main`'s
  history, not by change. When a later change MODIFIED a `new` scenario an earlier one closed, its
  ledger took the earlier change's red, and its red and green if it never made the scenario red
  again; a `hold` scenario's break was the earlier change's commit. Either way check-close passed
  the later change on evidence it didn't make, and the earlier change's rebuilt ledger took the
  later green. Now a change's red and green count only from its window, the PRs from its S step to
  its C step, and a `hold` scenario's break is its own R step's (§4).
- O-CLOSE5 [closed, build 7 part 5]: a later change that MODIFIED a `hold` scenario could edit its
  test at its R step, where `redline lock` rewrote only its own entry and check-lock checked only
  its own change; and at S and C nothing checked the lock, nor at G another change's entries. The
  edit of a frozen test needed no departure, and the stale entry then failed every PR outside a
  step. Now `redline lock` moves a scenario from a closed change's entry to the later change that
  declares it, keeping `reach` (§4), and every step's gate checks the whole lock, and compares it
  by test with `main`'s, so editing any frozen test is a departure at any step (§5).
- O-RUN1 [closed, build 5 part 8]: check-break failed a scenario with a Jest test instead of
  running it, and check-track counted a Jest test file as code. Now check-break runs each runner
  of a scenario, adding up its tools' kills, and check-track exempts every runner's test files (§5).
- O-RUN8 [closed, build 5 part 9]: `redline ci` ran pytest's suite alone, so a Jest test that
  failed wasn't seen, and a repository with Jest tests alone failed on a pytest that collected
  nothing. Now the suite runs each runner the repository uses, and fails when Jest is listed but
  can't run, or when no runner is used (§5).
- O-RUN9 [build 8]: the suite runs Jest only when the root `package.json` lists it, so Jest tests in
  a subproject, a workspace or a repository with Jest installed elsewhere never run, yet check-links
  and check-order count them. Taking Jest from tracked `*.spec.ts` files instead would fail every
  repository whose `.spec` files are another tool's, Redline's own toy among them. It is O-RUN6's
  problem, a linked test that never runs, and belongs with the runner configuration of O-RUN4.
- O-PROG1 [closed, build 10]: `merged` didn't show how far the work had come. Now every brief ends
  with the change's progress from `main`, and `merged` prints it alone after C: its steps merged out
  of its `steps.md` and the next step; in an initiative, the phase's changes complete and the plan's
  phases complete; and the open items later steps still own, as 20-character `█`/`░` bars. It prints
  and judges nothing (§6).
- O-RUN7 [closed, build 5 part 8]: a `Redline-Departure` trailer's test was read up to its first
  space, so a locked Jest test named by a sentence couldn't be edited with an approved departure.
- O-ENC1 [closed, build 9 part 7]: on Windows, Python decoded text as cp1252. `git()`,
  `load_config` and the open-step file didn't say UTF-8, so a config rule with "Ł" failed `start`
  and most gates, and an unchanged scenario with "≤" read as changed in check-specs; and a brief
  with "≤" printed to a pipe crashed after `start` had recorded the step. Now every file read and
  write is UTF-8, every process's output is UTF-8 with `errors="replace"`, `main()` prints UTF-8,
  and a `windows` CI job runs the suite (§7).
- O-ENC2 [closed, build 9 part 7]: git quotes a path outside ASCII in any output not split on NUL,
  so `ls-tree --name-only`, `ls-files`, `diff --name-only` and `grep` named such a file as
  `"\303\274…"`: a living spec under `redline/specs/grüße/` vanished at the merge-base, and
  check-specs reported its scenarios as changes no delta names. Now `git()` runs with
  `core.quotePath=false` (§7).
- O-MUT1 [closed, build 9 part 8]: mutmut reads `[tool.mutmut]` in `pyproject.toml` before `setup.cfg`,
  where Redline wrote its settings, so in a repository with that table mutmut mutated the files the
  repository names and ran every test against each mutant: a kill by any test was the scenario's
  break. And a scenario's test outside `tests/`, `test/` and root `test*.py` never reached the
  mutant run, which failed. Now Redline's settings are the only ones, `[tool.mutmut]` is taken out
  of the copy, and the scenario's tests, their `conftest.py` files and the `support:` files are
  copied (§5).
- O-MUT2 [closed, build 9 part 8]: no test ran the real mutmut; every check-break test used the fake, so
  how mutmut reads its settings went unseen. Now the `runners` CI job runs `Mutmut` on toy
  repositories, one with `[tool.mutmut]`, and checks each scenario's kills against a test that
  kills every mutant (§7).
- O-RUN5 [closed, build 5 part 7]: the helper had been checked under real Jest by hand only, and
  Stryker not at all. Now the `runners` CI job runs both on a toy project (§5). It found that Jest
  took the helper, then `redline/runners/spec.js`, for a test file and failed every run, so the
  helper is now `redline/runners/jest.js`.
- O-RUN6 [build 8]: a linked test in a file its runner doesn't collect (Jest's `testMatch`,
  pytest's `python_files`) never runs, yet check-links and check-order count it. A `new` test's
  red then passes with the suite without running. A `hold` scenario's break catches it, since
  nothing is killed. It belongs with the runner configuration of O-RUN4.
- O-RUN2 [build 8]: tests in Java: a JUnit 5 `@Spec` annotation with an extension for `new`, a
  scanner for Java sources, and PIT behind the `Mutator` seam.
- O-RUN3 [build 8]: a critical entry's `reach` follows pytest fixtures only, so a critical change
  can't lock a Jest test (§5).
- O-RUN4 [build 8]: a runner's own configuration (`jest.config`, Stryker's config, `package.json`)
  can skip or weaken tests in a PR outside any step. For pytest, only a critical `reach` covers
  its settings.
