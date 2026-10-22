# Redline

A spec-driven, test-first development tool for working with AI agents. A requirement isn't real
until a test has proved it can fail.

A change is a spec, then tests that fail, then the code that makes them pass, then a close, each
step one PR of at most 400 lines and one agent session. Redline doesn't take the agent's word for
any of it: CI runs on each merged commit and records what it saw, and the next step's gates read
that record from git. [docs/design.md](docs/design.md) is the whole design.

**Status:** being built, in the order of [§11](docs/design.md#11-build-order-riskiest-first) of the
design; [§12](docs/design.md#12-open-problems) lists what is still open, each item with the step
that owns it. Nothing has been released, so pin a commit.

## Install

Redline needs Python 3.12 or later, git, and the GitHub CLI `gh` for opening PRs and reading
labels in CI. It isn't on PyPI; install it from a commit:

```sh
pip install "redline @ git+https://github.com/Yusuprozimemet/redline@<commit>"
```

On Linux, `redline[mutation] @ git+…` adds mutmut, which check-break uses to prove a `hold` test
can fail. mutmut doesn't run on Windows, so there check-break leaves the mutation to CI. For Jest
tests, Node with `jest` (28.1 or later) and, for check-break, `@stryker-mutator/core` and
`@stryker-mutator/jest-runner` in the project, and `redline install jest` writes the `spec` helper
the tests import.

## Set up a repository

1. **`redline/config.yaml`**: the default rigor, files the 400-line gate doesn't count, shared test
   helpers, and the rules every brief prints (§4, §10):

   ```yaml
   rigor: standard
   generated: ["*.lock", "package-lock.json"]
   support: ["tests/helpers.py"]
   rules: {}
   ```

2. **The agents**: copy the six files of [.claude/agents/](.claude/agents/) into the repository's
   `.claude/agents/`. They are the read-only auditors and the blind relabeller of §9, for Claude
   Code, and refuse to run on a weaker model than the one they name.
3. **CI**: a workflow that checks out the full history with `main` and `refs/notes/*`, runs
   `redline ci pr --base main --pr <number>` on each PR (and on `labeled` and `unlabeled`), and on
   a push to `main` runs `redline ci push --note <file>` in a read-only job and hands the note to a
   job that runs git alone to add and push it. Redline's own
   [workflow](.github/workflows/redline.yml) is the model; its `redline` and `note` jobs are the
   part every repository needs. There is no workflow to copy yet (O-SELF1).
4. **The repository settings** Redline's guarantees rest on. Without them a gate is advice. Each is
   explained in [§7, Repository settings](docs/design.md#repository-settings):
   - [ ] A ruleset on `main`: require a pull request and the `redline` status check; block force
     pushes and deletion.
   - [ ] The five labels: `redline:departure`, `redline:oversized`, `redline:track`,
     `redline:rigor` and `redline:manual`.
   - [ ] The agent in an account of its own with the `write` role, never a maintainer's
     credentials, so its labels approve nothing; then require a maintainer's review.
   - [ ] Merge commits or squash merges only, never rebase merges.
   - [ ] CODEOWNERS naming a maintainer for `.github/` and `redline/config.yaml`, with code-owner
     review required.

## Commands

A step's session:

| Command | What it does |
|---|---|
| `redline start <change>/<step>` | refuses unless the previous step is merged and the branch is fresh from `main`; prints the step's brief |
| `redline pr` | runs the step's gates locally, adds the `Redline-Step` trailer, pushes and opens the PR |
| `redline merged <change>/<step>` | confirms the merge, switches to `main` and prints the next step's brief: the hand-off |

Gates, run by `pr`, by CI or both, and each on its own:

| Command | Fails when |
|---|---|
| `redline check-lines` | the branch changes more than 400 lines without an approved `Oversized` claim |
| `redline check-premises` | a premise has no `file:line` citation, or one that doesn't resolve |
| `redline check-audit <change>` | the audit is missing or a finding is unresolved |
| `redline check-steps <change>` | `steps.md` is malformed, or lost an item or step since the merge-base |
| `redline check-plan` | an initiative's plan is malformed, or a plan audit it needs is missing or stale |
| `redline check-links` | a scenario has no test, or a test names no scenario |
| `redline check-order` | a scenario turned green with no red commit before it |
| `redline check-break <change>` | a `hold` scenario's tests survive every mutant |
| `redline check-lock <change>` | a frozen test changed without an approved departure |
| `redline check-ledger <change>` | the committed ledger isn't what `main`'s history says |
| `redline check-close <change>` | a scenario lacks its red and green, its break, or its person's check |
| `redline check-specs <change>` | `redline/specs/` differs from what the deltas say |
| `redline check-defects <change>` | the defect log is missing at C or malformed |
| `redline check-relabel <change>` | the blind relabel is missing at critical, or a disagreement is undecided |

Records and helpers:

| Command | What it does |
|---|---|
| `redline ledger <change>` | rebuilds the change's `ledger.yaml` from `main`'s history and CI's notes |
| `redline lock <change>` | writes the change's `hold` tests into `redline/contracts/lock.yaml` |
| `redline blind <change>` | prints the defect log without its causes, for the relabeller |
| `redline retro <change>` | groups the defects by cause and proposes rules; writes nothing |
| `redline claims <initiative>` | prints every approved claim in `main`'s history, for the process auditor |
| `redline install jest` | writes the Jest `spec` helper into `redline/runners/` |
| `redline ci pr\|push` | what CI runs: a PR's gates and suite, or a merged commit's suite and note |

## A change from S to C

A toy repository has `greet.py`, whose `greet` returns `"Hello"` whatever the name and raises
`ValueError` on an empty one, and a test of it. The change `add-greet` makes it greet by name and
keeps the refusal. Each step below is its own branch, session and PR. After every merge, CI's push
run notes the merged commit, and each step refreshes the ledger from those notes before committing:

```sh
git fetch origin 'refs/notes/*:refs/notes/*'
redline ledger add-greet
```

**S, the spec.** On a fresh branch, write `redline/changes/add-greet/steps.md`, then `redline start
add-greet/S`. Add `proposal.md` (why, scope, `Rigor: standard`) and the delta,
`specs/greet/delta.md`:

```markdown
## ADDED Requirements

### Requirement: Greeting

#### Scenario GREET.S1 [new]: greets by name
- GIVEN the name "Ada"
- WHEN greet is called with it
- THEN it returns "Hello, Ada"

#### Scenario GREET.H1 [hold]: an empty name is refused
- WHEN greet is called with ""
- THEN it raises ValueError

### Premises
- P1: `greet` returns "Hello" whatever the name — `greet.py:4` (`return`)
- P2: An empty name raises ValueError — `greet.py:2-3` (`ValueError`)
```

`steps.md` names the steps, S, R, `G1` with `Owns: GREET.S1`, and C. Run the `redline-auditor`
agent with `Audit add-greet` and write its reply unedited to `audit.md`; resolve its findings by
fixing the spec and running it again. Commit, then `redline pr`.

**R, the red tests.** `redline start add-greet/R`, then write the tests, `new` as a strict
expected failure:

```python
@pytest.mark.spec("GREET.S1", new=True)
def test_greets_by_name():
    assert greet("Ada") == "Hello, Ada"

@pytest.mark.spec("GREET.H1")
def test_an_empty_name_is_refused():
    with pytest.raises(ValueError):
        greet("")
```

`redline lock add-greet` freezes the `hold` test. On the PR, CI's suite passes because GREET.S1's
test fails, and check-break mutates `greet.py` until GREET.H1's test fails. After the merge the
note on the merged commit records both: `result: pass`, and `break:` with `GREET.H1: pass`.

**G1, the code.** `redline start add-greet/G1` prints the brief with GREET.S1, the premises and the
track. Make `greet` return `f"Hello, {name}"` and remove `new=True`. Editing the frozen GREET.H1
test here would need a departure a maintainer approves.

**C, the close.** `redline start add-greet/C`. Copy the delta's requirement into
`redline/specs/greet/spec.md`, add `defects.md` (`# Defects: add-greet`, empty if nothing went
wrong), and refresh the ledger. check-close passes only when the evidence is all on `main`:

```yaml
GREET.S1:
  red:   {commit: 6eaa0bc…, merged: 7388206…, result: pass}
  green: {commit: 625eb89…, merged: 14999fd…, result: pass}
  break: null
GREET.H1:
  red: null
  green: null
  break: {commit: 6eaa0bc…, merged: 7388206…, result: pass}
```

After the C merge, `redline merged add-greet/C` says the change is complete, and `redline retro
add-greet` proposes rules from its defect log.

## How Redline is built

Redline follows its own rules: every PR changes at most 400 lines, one session builds one step,
and tests come first, each seen to fail before the code that makes it pass. Its own PRs don't run
as steps yet, though: they carry no `Redline-Step` trailer, so their red before green is a commit
convention a reviewer checks, not evidence Redline checks (O-SELF1).
