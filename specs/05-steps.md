## 5. A change is always the same sequence of steps

| Step | PR contents | CI proves |
|---|---|---|
| **S: Spec** | Proposal and delta spec, with audit findings resolved | Structure is valid, every premise citation resolves, IDs are unique, every finding is closed or waived |
| **R: Red** | Linked tests: `new` as strict expected failures (`xfail(strict=True)`, Jest `test.failing`); `hold` added to the lock | Every `new` test fails on today's code; every `hold` test passes, then fails under mutation |
| **G1…Gn: Green** | Code that turns expected failures into passes | Owned scenarios pass with their markers removed, the lock is unchanged, the code stays in the step's track, nothing else regressed |
| **C: Close** | Delta merged into `specs/`, ledger, defect log, deferred items with owners | Every `new` scenario has red and green results from merged commits, the red commit an ancestor of the green one; every `hold` scenario has a break result; every `manual` scenario has a person's check, its `Redline-Manual` trailer approved by a maintainer's label; the delta's ADDED, MODIFIED and REMOVED are in `specs/`, and nothing else there changed; the defect log exists (standard, critical) and is well formed; at critical, each defect has a blind second label and each disagreement a decision |

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
tree, as `reach` reads it, since check-break counts as evidence only on `main`. A cited file in a
package, a directory with an `__init__.py`, would be copied alone, into a package with no
`__init__.py`: a namespace portion, which loses to the same package anywhere else on `sys.path`,
such as the checkout an editable install points at, so the tests would run the unmutated code and
reach no mutant (O-MUT3). So `also_copy` adds the outermost package of each cited file too,
`src/redline` for `src/redline/runner.py`; mutmut copies it before it writes the mutants over the
cited files' copies.

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
parsed once, and only a file whose text matches the runner's grep pattern is parsed at all. The
history is read in a fixed number of git calls, however long it is (O-PERF1): one `git log --raw`
gives every commit, its parents and the blobs its diff changes, a merge's against its first
parent, so a commit's files are its first parent's with that diff applied; one `git cat-file
--batch` reads every new blob. A commit whose diff changes no runner's file has its first
parent's markers, unread. Finding a red among a green's ancestors still asks git, once per red
of that scenario, which grows with the scenarios, not the history. A file
that doesn't parse at a commit, such as a syntax error committed mid-history, gives no markers
there, and check-order prints `skipped <path> at <commit>: <error>`. History can't be rewritten,
so failing would fail every later PR, and reading its lines as text would let comments and
strings count again. Skipping can only drop a red or a green, never make one, and a green whose
red was dropped fails, where it is seen. In the working tree a file that doesn't parse is an
error: check-links reports it as a gap, and the lock refuses.

check-order judges only the scenarios a test at the commit it reads (`HEAD` by default) still
links. History keeps a scenario whose tests are gone: Redline's own toy once linked TOY.H1 and
TOY.H2 from a committed test file, green with no red, and no commit can take that back. A scenario
no test links any more is printed as `skipped <ID>: no test at <rev> links it`, never failed, and
nothing is lost: a declared scenario with no test is an unlinked gap in check-links, and an ID
declared again is linked again, so its old green without a red fails once more. A `hold`
scenario has no red by design, so it isn't failed either. The gate and `redline check-order` count
the same failures, with one function, `failed` in `redline/order.py` (O-SELF5).

check-links needs a test for a scenario only once its change has one to give. A change whose S step
is merged on `main` and no later step is, unless the step gated is its own from R on, has no tests
yet by design, and neither has the change of a step gated at S; their scenarios aren't unlinked gaps: without that, another change's R, G or C gate, and
Redline's own suite, would fail as soon as an S step merged, until that change's R did. Its unknown,
duplicate and malformed scenarios, and a manual one a test links, still fail. A gate passes its own
step, so at R the change's scenarios need their tests before `pr` stamps a commit; run on its own,
check-links takes the step the trailers of `main..HEAD` name, else the open step, and prints each
waiting change as `skipped <change>: <n> scenarios, before its R step` (O-LINK1). A change with no
`Redline-Step` on `main` at all, as in a history without trailers, isn't waiting: its scenarios
need tests.

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

The toy's test file, `src/adult.test.js`, isn't committed: the tests that run it write it from a
string beside the helper, and the toy's `.gitignore` ignores `src/*.test.js`. Committed, its markers
would link TOY.H1 and TOY.H2 in Redline's own tree, where no spec declares them, and fail
check-links there. `tests/test_self.py` runs check-links and check-order on Redline's own checkout,
as every step from R on runs them, with the step check-links takes on its own (above), and fails on
any gap. check-order needs the whole history, so it
is skipped in a shallow clone, as the `windows` and `runners` jobs check out; the `suite` job on
a PR, and the `redline` job on a push, fetch it all and run it with the suite.

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
  workflow, or a value read from a data file (O-LOCK4).
- **What it doesn't follow**: an import from a file `support:` doesn't name; `from m import *`;
  an import inside a function; a name deeper than `m.name` (`m.sub.name`, `obj.attr`); fixtures
  from installed plugins or `pytest_plugins` modules; `request.getfixturevalue`; a fixture
  renamed with `@pytest.fixture(name=…)`; a module found through `sys.path` edits or an import
  mode other than the default `prepend`. These stay the auditor's judgment (§12).
- **That the code under test still meets the bound.** The lock freezes what the test expects,
  not what the API shows while it waits. The migration engine pins that with a second test
  outside the frozen set, which the departure's spec names. Redline doesn't check that it exists;
  the auditor does (§12).

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
only a claim, so in CI it also needs a maintainer's `redline:departure` label on the PR, applied
by the person the trailer names (§7).

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
- **A `manual` scenario without a person's check**: no `Redline-Manual: <ID> checked-by @person:
  <what was seen>` trailer naming it among the C PR's own commits (`base..HEAD`), or, in CI, no
  maintainer's `redline:manual` label on the PR, applied by the person the trailer names (§7). It has no evidence CI can give, and none
  from history stands in for it: a check made in an earlier PR read code a later step may have
  changed. A second trailer for the same scenario passes, and both are recorded.
- **A `Redline-Manual` trailer that allows nothing**: one missing `checked-by @person: <text>`, or
  one whose ID is no `manual` scenario of the change's deltas (unknown, `new`, `hold`, or another
  change's).

A scenario is `new`, `hold` or `manual` by its tag in the delta, and its evidence is only what its own
steps made (§4, a change's window): a scenario a closed change proved doesn't close a later
change that MODIFIES it. It runs at C only, since at G a scenario
owned by a later step has no green yet by design; run on its own, it checks as at C, with
`--base` (default `main`) for where the PR's own commits begin. On `main` after the merge there
are none, so a `manual` scenario fails there, as check-specs does: both are the C PR's gates.
Locally, where there is no PR, each checked scenario is a note that CI will need the label.

`unverified` refuses: until CI has run on the merged commit, there is no evidence (§7). A C PR
opened right after the last G merges usually waits so, for that merge's push run. The refusal says
it is waiting, not wrong: once the note on that commit lands, fetch it (`git fetch origin
'refs/notes/*:refs/notes/*'`), run `redline ledger <change>`, commit and push. The committed ledger
must then say `pass` too, or check-ledger fails. Nothing else in the PR needs to change.

`unconfirmed` refuses too, and says the note is wrong, not late: `<ID>: <red|green|break> is
unconfirmed: the CI note on <commit> doesn't match its run on GitHub` (§4). Fetching the notes
changes nothing until the note does, or, for a job that failed only on reading GitHub, until a
re-run of it passes, within GitHub's 30 days (O-NOTE3).

What it doesn't prove: that the scenario's own test ran. A result is the whole suite's on the
merged commit, and a test skipped there passes with it (O-CLOSE6).

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

It compares the text outside scenarios too (§4), each requirement's prose by its spec file and
name, trailing and leading blank lines dropped, and a file's text under no requirement as a whole,
and fails, naming the requirement or the file, on:

- **Prose other than the delta's**: a requirement a delta gives prose under whose living prose
  now differs from it, or two of the change's blocks for one requirement giving different prose.
- **Prose no delta gives**: a requirement's prose changed since the merge-base, or a new
  requirement with prose, where no delta of the change gives prose under it.
- **A requirement with no scenario**: one the merge-base had scenarios under, or a new one, now
  with none. It must go, heading and prose. One that had none at the merge-base may stay as it was.
- **A spec file with no scenario** left, which had one at the merge-base: delete it.
- **Text under no requirement changed** in a spec file that is in both the merge-base and the tree.

It compares with the merge-base, so it is the C PR's gate; run on its own it takes `--base`
(default `main`), and run on `main` after the merge it has no diff to read and fails.

**Nothing reaches `specs/` before C.** S writes its delta under `redline/changes/<id>/specs/`, R
and G write tests and code, so none of them writes `redline/specs/`, and one that did would edit
the merge-base the C step compares with, unseen. So at S, R and every G step, `pr` and `redline ci
pr` run check-specs too, and it fails on each file under `redline/specs/` that differs from the
merge-base with `main`, naming it: `<path> changed since the merge-base with main; only the C step
writes redline/specs/, from its delta`. A rename is a file deleted and one added, both named. At
lite, where S and R may share a PR, neither writes there, so nothing changes. Outside any step a
PR touching `specs/` is refused (§7), and both find the files with one function, `touched` in
`redline/pr.py`. So the merge-base a C step compares with holds only what earlier C steps wrote.
The lock needs no such rule: at every step it is compared by test with the merge-base's (above),
so a frozen test changed at S or C is a departure there as at R and G, and an entry added must
match the code, as check-lock asks of every change the lock names.

What it doesn't prove: what a new spec file says under no requirement, or the order of
requirements in a file, neither of which a delta has a form for (§12, Judgments).

At **lite** rigor, S and R may share one PR, so the smallest change is two sessions.
