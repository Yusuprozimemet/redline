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
    ├── specs/<domain>/delta.md     # ADDED/MODIFIED/REMOVED; scenarios tagged new | hold | manual; premises
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

A scenario's heading is exactly `#### Scenario <ID> [new|hold|manual]: <title>`. Every gate finds
scenarios by that form, so a line that starts `#### Scenario` in any other (no tag, an unknown one,
no `: ` after the tag) would be no scenario to any of them: it would need no test, no evidence at C
and no place in `specs/`, and nothing would say so. So check-links fails such a line in the living
specs and the deltas of changes not closed, and check-steps in its change's deltas, at every step
from S on, each naming the file and line (O-SPEC1).

A scenario that can't be automated, such as how a page looks or how long a wait feels, is
`[manual]`, and its block (heading to the next `#` line) says why in one `Manual: <reason>` line:

```markdown
#### Scenario AUTH.2FA.S4 [manual]: the code field is readable on a phone
Manual: legibility is a person's judgment; no assertion reads it
- GIVEN the login page on a 360px-wide screen
- THEN the code field and its label fit without zooming
```

It has no test: a test linked to it is a gap in check-links (tag it `new` or `hold`, since a
scenario a test can check is proved by the test, not by a person's word), and unlinked it is
none. Its block is checked by the same two gates that check headings, naming file and line: a
`[manual]` scenario without one `Manual:` line with a reason, or with two, fails, and so does a
`Manual:` line under a `new` or `hold` scenario, where a tag was likely forgotten. The auditor may
challenge at S that it can't be automated (§12). check-specs carries it into `specs/` like any
other, `Manual:` line included, so the living spec keeps the reason; the brief prints it. A G
step may own it, where its code is written, but needn't, as with `hold`: nothing is lost, since
check-close asks for its check at C. Its ledger entry has no red, green or break (all `null`):
its evidence is a person's check, not CI's (O-SPEC2): a `Redline-Manual` trailer in the C PR's
own commits, approved by a maintainer's label, which check-close reads (§5, §7, O-SPEC3).

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

A requirement's prose, the lines between its `### Requirement:` heading and its first scenario, is
copied the same way. Where a delta gives prose under an ADDED or MODIFIED requirement, the living
spec's prose for that requirement reads the same after C; where it gives none, the living prose
stays as it was, and a new requirement has none. So a delta rewords prose but never empties it, and
a MODIFIED requirement may carry prose and no scenario, to reword its prose alone. A requirement
under both ADDED and MODIFIED, or in two deltas, gives the same prose in each, or gives it once. A
requirement the C step leaves with no scenario, its every scenario REMOVED or moved, goes with its
heading and prose, and a spec file left with no scenario is deleted: what nothing tests mustn't
still read as behaviour. Text under no requirement, a file's title and any lines before its first
`### Requirement:` or under another `## ` or `### ` heading, has no form in a delta, so it changes
only in a spec file the C step creates or deletes.

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
session's word); a waiver or a deferral names the person who approved it. Before the first
finding, a `Model:` line names the model the auditor ran on, `Round:` which round this is, and
`Audited:` the commit it read (§9, Rounds). A closed finding keeps only its heading and its
`Resolution:`; its evidence stays in git history:

```markdown
# Audit: add-2fa
Model: claude-fable-5-1
Round: 2
Audited: 3f2a9c1e5b7d4a6c8e0f2b4d6a8c0e2f4b6d8a0c
## F1 [open]: P2 is wrong; `auth/login.py:30` already calls `verify_code`
## F2 [closed]: P1 cited the wrong line
Resolution: P1 now cites `auth/session.py:42`
## F3 [waived]: no test for the lockout timing
Waived-by: @maintainer: timing is a manual check (O2)
## F4 [deferred]: a code reused within its window isn't refused
Deferred-to: O-2FA3, by @maintainer
```

`pr` at S refuses if `audit.md` is missing, has no `Model:` line naming a Fable or Opus model, no
`Round:` line or one above the change's limit, no `Audited:` line, or any finding is `[open]`, a
`[closed]` one has no `Resolution:`, a `[waived]` one no `Waived-by:` or a `[deferred]` one no
`Deferred-to:`.

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

`redline check-steps <change>` checks the form of `steps.md` against the change's own deltas,
which it reads even once the change is closed, as the change's other checks do. It fails, naming
the line, on:

- **A malformed open item**: a line under `## Open items`, blank lines aside, that isn't `- <ID>
  [<step>]: <text>`, so an item with no ID or no owner, or one wrapped onto a second line the
  brief wouldn't print; an ID given twice; an owner that isn't a step of this `steps.md`; or an
  item's line outside `## Open items`. An item moves to another change as a line in that change's
  `steps.md`.
- **Steps out of order**: not S, then R if there is one, then G1…Gn numbered from 1, then C. S
  and C are required, R and the G steps aren't: a change that only REMOVES scenarios is S and C,
  one with only `hold` scenarios S, R and C. A `## ` heading that is neither a step nor `## Open
  items`, such as `## G1 Greet by name`, fails too, since it isn't read as a step.
- **A step named twice.**
- **An `Owns:` ID no delta of the change declares** under ADDED or MODIFIED. A REMOVED entry
  needs no test, so no step owns it.
- **A `new` scenario no G step owns.** Without this it is found only at C, by check-close, as a
  scenario with no green.
- **A malformed scenario heading**, or a `Manual:` line missing, repeated or out of place, in
  one of the change's deltas (above). check-links reads
  every delta too, but only from R on.

`pr` and `redline ci pr` run it at every step, on the step's change and on each other change
whose `steps.md` or deltas the PR changes since the merge-base: nothing else stops a step from
editing another change's. It reads the tree, not the merge-base. It checks the form of what will
land on `main`, which the next step's PR then reads at its merge-base for its order and its
`Track:` (§5, §7); those read the merge-base so that a PR can't widen what it may do, and this
one so that what it lands is well formed. At S, where `steps.md` and the delta land together,
it is the first check of either.

**Across steps**, the same gate compares each of those changes' `steps.md` with the one at the
merge-base, items by ID and steps by name (O-STEPS2). A later step may edit the file, and the form
alone can't see what left it. It fails on:

- **An open item dropped**: an ID at the merge-base that is gone now. An item is never closed by
  removing it, at its owning step either: it stays as the record, progress stops printing it once
  its step merges (§6), and whether it was done is the end audit's to say (§4, plan audits). An
  item **moved** to another change passes: the same PR adds to that change's `steps.md` an item
  with the same text, after `]: `, that it didn't have at the merge-base. Its ID there may differ,
  since each file numbers its own. That change is then one the PR edits, so its item is checked too.
- **An item given to a merged step**: one owned now by a step merged on `main`, as `start` reads
  merged steps, that is new since the merge-base or had another owner there. Progress never prints
  it. The PR's own step isn't merged yet, so an item given to it is done in this PR; one moved from
  a merged step to a later one is printed again, and passes.
- **A step removed**: a step at the merge-base that is gone now and is merged on `main` or is the
  PR's own. A step not yet merged, such as a G3 found unneeded, may go without a claim: its `new`
  scenarios must still have a G step and its items an owner, above, so no gate asks less. A step
  renamed is one removed and one added.

A change with no `steps.md` at the merge-base, at its S step or new in the PR, has nothing to
compare, and only its form is checked. Run on its own, `redline check-steps` takes `--base`
(default `main`); with no step, only merged steps are kept. On `main` after the merge there is no
diff, and it passes.

What it doesn't prove: an item's text reworded under its ID, or a merged step's `Owns:` or
`Track:` edited. Whether new words say less is a judgment, the end audit's, as a scenario's is
the auditor's (§12); check-track and the C step's checks read what they need at the merge-base
or from the ledger, so a merged step's lines are only its record.

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
is the commit CI ran on after the merge: the first commit of that line that is `commit` or one of
its descendants, which `git rev-list --ancestry-path <commit>..main` lists in one call however
long the line (O-PERF1). With `--first-parent` it would walk first parents only and miss the
merge of a PR of two commits. `result` is that run's outcome: `pass`, `fail`, `unverified` when
no result is recorded, or `unconfirmed` when the note doesn't match its run on GitHub (below). `break` is the mutation evidence (§5) and is `null` for a
`new` scenario. A `hold` scenario is the other way round: its test carries no `new=True`, so it
has no red and no green, and both stay `null`. Its `break` is `{commit, merged, result}`:
`commit` is the first commit of the change's R step (one on `main` carrying `Redline-Step:
<change>/R`) whose tests link the scenario without `new=True`, `merged` is found as for red, and
`result` is the scenario's entry in the `break:` map of the CI note on `merged` (`pass` or
`fail`). From a note that checks out (below), it is `unverified` when the note says `result: pass`
and has no entry for it, and `fail`, entry or none, when it says `result: fail`. It is
`unverified` when that note is missing, and `unconfirmed` when the note doesn't match its run
(below). The R step's merge is the
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
ledger is stale, and the next step's PR refreshes it. Branch protection doesn't cover
`refs/notes/redline-ci`, so anyone who can push to the repository can push a note. CI's own code
can't: the job that writes the note runs none of the repository's code (§7).

**A note is checked against its run.** Anyone with the `write` role, the agent's own account among
them (§7, Repository settings), could otherwise write `result: pass` on any commit. So the rebuild
reads each note it uses against GitHub's Actions API, through `push_run` in the `GitHub` seam. A
note **checks out** when its `run:` is a run's URL, `https://github.com/<owner>/<repo>/actions/runs/<id>`;
`gh api repos/{owner}/{repo}/actions/runs/<id>`, asked of the checkout's own repository with only
the id taken from the note, gives that URL as its `html_url`, `push` as its `event`, the noted
commit as its `head_sha`, `main` as its `head_branch` and `.github/workflows/redline.yml` as its
`path`; and the run's `redline` job (`…/runs/<id>/jobs`) concluded `success` exactly when the note
records no failure. A failure is `result: fail`, or a `break:` entry `fail` naming a `hold`
scenario whose break the ledger reads from that note: CI writes a `break:` map only on an R merge,
keyed by exactly the change's `hold` scenarios (§5), notes `result: pass` beside a failed break
and fails the job, so that note reads `pass` with that break `fail`. An entry for any other
scenario counts for nothing, so it can't excuse a failed job, and a delta that drops or retags a
`hold` scenario after R still reads its R note when that scenario's break passed; when it failed,
the note records no failure the ledger counts beside the job's `failure`, so it reads `unconfirmed`
(O-NOTE3). A break is read as its entry only from a note that says `result: pass`; from one that
says `result: fail` every break is `fail`, entry or none, so a forged entry can't turn a failed
run into a passing break. A run whose jobs have no `redline` job confirms nothing.

A note that doesn't check out reads as a fourth result, `unconfirmed`, whatever it says, `fail`
included: a run GitHub doesn't have (a 404, answered at once, with no retry), a `run:` that isn't
a run's URL or is missing, and any field that differs. Its breaks are `unconfirmed` too, an entry
it lacks included. Errors aren't results, since either answer would be a guess: a note that isn't
YAML, or whose `result:` is neither `pass` nor `fail`, before GitHub is asked; a machine without
`gh`; a 404 for the checkout's own repository, which the rebuild reads once before any run, since
GitHub answers 404 too for a repository the token can't see; and any other failure to read a
run. A note's error names its commit, and a run's its `run:`; the repository's says only that GitHub
doesn't show the token the checkout's repository, as `gh`'s 404 names none. So a ledger is now
rebuilt with `gh` and a token that can read the repository's Actions API. GitHub is asked about each
run once in a rebuild, however many entries read its note. It lists a run's jobs from its latest
attempt, so a push run whose job failed only because GitHub couldn't be read for the claims record
(§7), and whose note says `result: pass`, reads `unconfirmed` until a re-run of it passes, which
GitHub allows for 30 days (O-NOTE3).

What it doesn't prove: a confirmed run says how the run ended, not what else its note says. Its
`claims:` record, and which `hold` scenario's `break:` entry failed when one did, are still the
text of whoever pushed the note (O-NOTE2). GitHub's answers are trusted as GitHub is (§12). And a
note CI really wrote can read `unconfirmed` for good: a run past its 30 days, a run deleted, which
anyone with `write` can do, and every run of a repository renamed or transferred, whose `html_url`
no longer matches the notes (O-NOTE3).

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

Each audit uses the independent three-round budget and incremental brief in §9 (O-AUDIT3).

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
claims (§7, Approvals) live only there: the `Oversized`, `Redline-Track`, `Redline-Departure`,
`Redline-Rigor` and `Redline-Manual` trailers, and the labels that approved them. Those are the decisions a person made
to let a gate pass, which is what the process auditor asks about. `redline claims <initiative>`
prints them from `main`, and the main session gives that text to the process auditor after its
arguments, as it gives `redline blind`'s text to the relabeller:

```markdown
# Claims: 2fa-rollout
From main: 1 claim on 9 commits: the steps of add-2fa, add-recovery-codes, enforce-admin-2fa,
add-sms-codes, and every commit that touches redline/initiatives/2fa-rollout/ or redline/config.yaml.
Left the plan: add-sms-codes in 9c0d1e2.

## 4d5e6f1 add-2fa/G2 (PR #12): Lock out after five wrong codes
Redline-Departure: tests/test_login.py::test_lockout approved-by @alice: five, not three
Label at the merge: redline:departure, applied by @alice, admin, at 2026-11-02T10:15:00Z, head pushed at 2026-11-02T09:40:12Z, trailer names @alice (CI note on 7a8b9c0)
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
  merge, with when the label was applied and when the PR's head was pushed, as GitHub timed them
  (`at <time>, head pushed at <time>`; a record written before build 9 part 21 has neither),
  and, for a departure or a manual check, the person its trailer names (`trailer names @<login>`;
  a record written before build 9 part 22 has none); or that it wasn't on the PR, or that no merged PR was found. When that commit has no
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
  `refs/notes/redline-ci`, which branch protection doesn't cover. The ledger checks a note's
  result against its run (above), but not its `claims:`: whoever can push the ref can write or
  rewrite a record (O-NOTE2).
- **The labels of a claim with no record**: commits merged before build 6 part 11 have none, nor
  does a merge whose push run couldn't read GitHub until a re-run adds it. For those, `claims`
  reads labels and roles now, so a label removed after the merge reads as missing, one added
  after it as present, and a re-run's record reads them as late as it runs.
- **A PR merged by rebase**: the push run reads the claims of the merged commit and its first
  parent's range only, as it reads the step (§7), so a claim in an earlier commit of the PR gets
  no record. Redline needs merge commits or squash merges, a repository setting (§7, Repository settings).
- **A claim that should have been made**: a PR merged over a gate, without CI or with it failing,
  has no trailer to print. It shows only that the record holds no claim there.
- **PR text**: descriptions and review comments aren't printed, on purpose: they are untrusted
  text in the process auditor's context (§12).
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
# Model: claude-fable-5-1
D1:
  cause: premise
  note: P2 claimed where the counter lived, and the code showed otherwise.
D2:
  cause: unclear
  note: The entry says the fix was in a later step but not what was wrong.
```

The `# Model:` comment, before the first entry, names the model the relabeller ran on (§9).
`cause` is one label of the table, or `unclear` when the text doesn't let it choose; `note` is one
sentence on what decided it. A disagreement, where the second label isn't the `Cause:` line, is
decided by the maintainer or the main session in a `Decided: <reason>` line under the defect in
`defects.md`: the label kept and why, or the `Cause:` changed and why. `unclear` is a
disagreement too: an entry nobody else can label is a weak record.

`redline check-relabel <change>` prints each disagreement, then fails on:

- **A missing `relabel.yaml`** at the C step, at critical, unless a maintainer waived the relabel:
  a `Redline-Relabel: waived-by @person: <reason>` trailer in the C PR's own commits, approved by
  the `redline:relabel` label applied by the person it names (§7, Approvals). A waiver is a
  recorded choice not to have the second label, not a second label: the defects keep the main
  session's causes alone. Below critical the file is optional; if it exists, it is checked. Run on
  its own, the command checks as at C, reading the PR's commits from `main`.
- **A `Redline-Relabel` trailer** not in that form, beside a `relabel.yaml`, below critical, or in
  any other PR, a step's or one outside any step, where no gate would read it.
- **No `# Model:` line naming a Fable or Opus model** before the first entry (§9).
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
