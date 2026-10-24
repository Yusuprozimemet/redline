## 7. Trust model

| Source | Counts as evidence? |
|---|---|
| CI run on a merged commit | Yes, and only this |
| CLI run locally | A preview, which CI re-runs |
| The agent's report or summary | Never |
| `ledger.yaml` | A cache, which CI rebuilds from history |

CI is `.github/workflows/redline.yml`, a thin wrapper around `redline ci`; every rule lives in the
CLI. It checks out the full history, `main` and `refs/notes/*`. A second job, `runners`, runs the
real Jest and Stryker on a toy project, the real mutmut on toy repositories (§5) and the real
`gh api` calls on one of this repository's merged PRs and one of its push runs (Approvals, below),
and records nothing. The mutmut toys hold a scenario whose test kills no mutant beside a test that kills them
all, so a kill credited to the wrong test shows. A repository with Jest tests
installs Node and runs `npm ci` in its workflow before `redline ci`, so the suite can run them. A
third job, `windows`, runs Redline's own suite on Windows with a read-only token, and records
nothing either. It runs pytest, not `redline ci`: mutmut doesn't run on Windows, and a skipped
break fails the run (§5). A fourth, `suite`, runs a PR's code, apart from the gate (below).

**The suite can run with another Python than the gate's.** A runner's commands run pytest as
`<python> -m pytest`, the suite's and check-break's unmutated runs alike (§5), and `<python>` is the
interpreter Redline itself runs in. That is right where Redline and the project share one
environment, as in a repository that installs a pinned Redline beside its own packages. It isn't
for Redline itself: a gate the PR can't edit must sit in an environment of its own (O-SELF3), and
the gate and the code under test are both the package `redline`, so a suite run with the gate's
Python would import the gate and test it, not the PR. So `redline ci pr --python <path>` runs those
commands with that interpreter instead. mutmut is already the one on `PATH`, the project's, and
Jest's command has no Python. A path that isn't a file is an error, never a fallback to the gate's
own. The path is the workflow's word, as every line CI runs is, and on a PR the workflow is the PR's
own (Repository settings, CODEOWNERS). `redline ci push` and the local commands take no such option.

**The merge-base's Redline gates each PR.** Redline's own workflow installs the Redline the PR
contains, `pip install -e .`, for the suite to test; gated by that one, a PR that weakens a gate
would be checked by the weakened gate. So on a pull request the `redline` job first adds the
merge-base with `main` as a worktree in `$RUNNER_TEMP`, and installs that tree, not editable,
into a venv of its own with the three hashed pip lines (below), run with the venv's Python and
reading the merge-base's own requirements files. That runs before the PR's own pip lines, so no
code of the PR's has run yet. The gate step then called that venv's `redline` by its path:
`redline ci pr --base main --pr <n> --python "$(command -v python)"`, the setup-python
environment that holds the PR's own Redline, which the suite tests; that call is the `suite`
job's now, as `ci suite` (below). Everything else is read at
the merge-base already (above), so the gate's code is now read there too. A push run is unchanged:
its merged code is `main`. So are `runners` and `windows`, which test the PR's own code and record
nothing. A PR that changes `ci pr`'s options can't use them in its own workflow, since the
merge-base's Redline doesn't have them yet; the next PR is the first gated with them, as this one
was the first gated with `--python`. An adopting repository installs a pinned Redline, which its
PRs don't contain, and needs none of this.

**The PR's code runs in a job of its own.** Gated by the merge-base's Redline, the PR's code still
ran in the gate's job, as the same user: its `pip install -e .`, its suite and check-break's runs,
any of which could rewrite a file the gate imports after it, a lazy import in the standard library
or a file in the gate's venv, and in an adopting repository the site-packages the gate shares with
the code under test (O-CI10). So on a pull request a fourth job, `suite`, runs all of the PR's
code, and the `redline` job runs none of it. `suite` checks out, fetches and sets up Python as
`redline` does, installs the merge-base's Redline into a venv of its own and the PR's beside it, as
above, and runs `"$RUNNER_TEMP/gate/bin/redline" ci suite --base main --python "$(command -v
python)"`: the step from the trailers, as `ci pr` works it out, check-break at an R step, then the
suite. It holds `contents: read` alone and has no `outputs`, so nothing the PR's code writes
reaches the gate but the job's result. The `redline` job `needs: suite` and runs `if: always()`,
so a failed suite job still gates, where a skipped job would leave a skipped check that branch
protection reads as passed; `!cancelled()` wouldn't do, since a run cancelled while `suite` runs
would then skip the gate, where `always()` runs it to fail on the result `cancelled`. On a pull
request it installs only the
merge-base's Redline, its editable install now `if: github.event_name == 'push'`, and its gate runs
`ci pr --base main --pr <n> --suite-result "$SUITE"`, `SUITE` being `${{ needs.suite.result }}`:
every gate and check-ledger, as before, but not the suite or the part of check-break that runs
tests, and a result other than `success` is the failure `suite: the suite job's result is
<result>`. Each job gets a runner of its
own, so nothing the PR's code writes reaches the gate's files. A push run is unchanged: `suite` is
skipped, and the `redline` job's code is `main`'s, which gates itself.

Moving the suite and check-break's test runs loses nothing: their verdicts were the PR's code's
already. A PR's `conftest.py` can turn any test's outcome, a mutant's run included, and in
Redline's own suite the plugin is the PR's (below). check-break's two refusals that run no test, a
`hold` scenario no test links without `new=True` and premises that cite no file to mutate, aren't
the PR's code's, so at an R step `ci pr --suite-result` still makes them; `ci suite` makes them
too, with the rest of check-break. What the move keeps from the PR's code is every other gate,
which starts no process but git and `gh` and reads the PR's files as data: the trailers and the
step's order, the lock, the ledger, the approvals. `ci pr` without `--suite-result` runs it all in
one process, as before, for a local preview; `--suite-result` takes `success`, `failure`,
`cancelled` or `skipped`, the results a job can have, and `ci suite` takes `--base` and `--python`
alone, other options refused. As with `--python`, the PR that adds
them, the change `suite-job`'s G1, can't use them; its G2 moves the workflows.

An adopting repository's workflow has the same two jobs (below). On a pull request its `redline`
job installs the pinned Redline and nothing of the project's, so the project's dependencies, `npm
ci` and the scripts it runs among them, install in `suite`, where a comment marks the place. On a
push the `redline` job's suite needs them too, so a comment there says they go in steps with
`if: github.event_name == 'push'`. Nothing checks that such a step has it, and on a push they share
the gate's site-packages and can replace one of its pins (O-CI11).

What it doesn't prove:

- **The workflow.** On `pull_request` GitHub runs the PR's own workflow file, so a PR can call its
  own `redline` again; the gate holds only with CODEOWNERS on `.github/` (Repository settings,
  item 5).
- **The pytest plugin.** Redline's own suite runs the PR's plugin, so strict xfail on `new` tests
  is the PR's own code under test, like the note's text (§12, Judgments): one process imports one
  `redline`, so the gate can't put its own plugin in the PR's pytest. In an adopting repository the
  plugin is the pinned Redline's.
- **The suite job.** Its result is the PR's code's: the gate reads whether the job succeeded, not
  why. A runner that isn't fresh for each job, a self-hosted one reused, would let the suite job
  leave files for the next job; Redline's jobs run on GitHub's hosted images (§12, Judgments).

**An adopting repository's workflow.** `.github/workflows/redline.yml` is Redline's own: it
installs the Redline its PR contains and gates with the merge-base's, and runs the `runners` and
`windows` jobs, none of which an adopting repository has. So `redline install workflow` writes
one for that repository at `.github/workflows/redline.yml`, the one path a note checks out from
(§4), from a template shipped in the package. It installs the Redline that ran the command: pip
records a commit installed by `redline @ git+<url>@<commit>` in the distribution's
`direct_url.json` (PEP 610), with its URL, `vcs_info.vcs` `git` and the full `commit_id` even
when a short one was asked for. The workflow clones that URL into `$RUNNER_TEMP`, checks out that
commit and installs it with Redline's own three hashed pip lines, read from that commit's
requirements files, not editable, in the `redline` job on a push as on a PR and in the `suite`
job; then a comment after each such step, outside its script, marks where the project installs
its own dependencies, on a push alone in the `redline` job (above). Every other line is Redline's
own: the triggers, the default permissions, the concurrency group, the `redline` job's checkout,
fetch, setup-python, push step and note hand-off, the `suite` job's checkout, fetch and
setup-python, and the `note` job, so a note it writes checks out (§4). Its PR gate runs `redline
ci pr --base main --pr <n> --suite-result "$SUITE"` and its suite job `redline ci suite --base
main`, with no `--python`, since Redline and the project share one environment in `suite` (above).
A test keeps the template in step: it writes the workflow and compares it with Redline's own, both
parsed as YAML, so comments aside: with the installs, the `ci pr` and `ci suite` runs and
Redline's other jobs taken out, the two are equal whole, a job's `name` or `if` included, and a
change to Redline's workflow that an adopter needs fails until the template has it too. The
template isn't one of the runners' helpers: a written workflow never equals it and may hold the
project's own steps, so check-helpers doesn't read it. Every suite runs on an editable install,
which reads the template from the tree, so a test builds the wheel and finds it there. The
template, `src/redline/helpers/redline.yml`, holds `{url}` and `{commit}` in the install step's
script, and `write_workflow` in `redline/runner.py` puts in the commit, checked as 40 hex digits,
and the URL, quoted for the shell by `shlex.quote`. It reads `direct_url.json` through
`distribution("redline")`, imported into `redline.runner` so the tests can give it any.

The command refuses, writing nothing, when the Redline that runs it wasn't installed from a git
commit (an editable or local install, an index or archive URL, another VCS), so a workflow never
pins a Redline nobody can fetch; and when `.github/workflows/redline.yml` exists, which is the
repository's own and may hold its own steps (Node for Jest, say). To move to another commit,
reinstall Redline from it, remove the file and run the command again.

What it doesn't prove: that the commit is on a branch a clone fetches, or that the URL serves the
same commit later; a clone that can't check it out fails the run, where it is seen. Nor that the
URL is safe outside the shell: a `${{` in it is an Actions expression, and a line break ends the
script, before the shell's quoting counts (O-SELF6). Nor that the
project's own dependencies, installed beside Redline's pins, leave them as they were (O-CI11).

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
locally), the test suite, and `check-ledger <change> --main main`, and prints every failure; with
`--suite-result`, the suite job's result stands for the suite and check-break's test runs (above). This
proves the PR's state: the gates hold, `new` tests fail strictly, and the committed ledger
matches `main`'s evidence. It records nothing. A PR run is not evidence, because its commits are
not on `main` yet.

A PR whose commits carry no `Redline-Step` trailer is **outside any step**: a rule PR from
`retro` (§10), a plan edit, or a change to Redline itself. It is opened with `gh`, not `pr`.
`redline ci pr` refuses it, before anything runs, if it touches `redline/changes/`,
`redline/contracts/` or `redline/specs/`, and names each such file, found by `touched` in
`redline/pr.py`, the function a step's check-specs uses to keep `specs/` untouched before C (§5). Those files belong to steps:
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
- **No manual check**: a `Redline-Manual` trailer fails, since it is a C step's (Approvals, below).
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
  claim: 'Redline-Departure: tests/test_login.py::test_lockout approved-by @alice: five, not three'
  pr: 12
  label: redline:departure
  by: alice
  role: admin
  at: '2026-11-02T10:15:00Z'
  pushed: '2026-11-02T09:40:12Z'
  named: alice
```

`pr` is null when GitHub associates no merged PR with the commit; `by`, `role` and `at` are null
when the label isn't on the PR, and `pushed` when no push of the PR's head is found. `at` is when
the label was last applied and `pushed` when the PR's head was last pushed, read as `redline ci
pr` reads them (Approvals, below). `named` is the person a departure's or a manual check's trailer
names, read with the trailer's own form, and null for the three claims that name nobody. The
record judges nothing: a label applied by someone who isn't a maintainer, by someone other than
the named person, or before the head was pushed, is recorded as it is. A merge without claims gets no `claims:`, and `result:`, `run:`
and `break:` are as before, so the ledger reads the note as it did. If GitHub can't be read, the
note is written without the record and the run fails, so the result is kept and the gap is seen:
the ledger reads that note `unconfirmed` until a re-run of the job passes, within GitHub's 30
days (§4, O-NOTE3).
GitHub's own answers fail now and then: `commits/<sha>/pulls` answered HTTP 500 with an empty body
to about four calls in ten when the real calls were first tested (O-GH3), each call alone, and
GraphQL's `associatedPullRequests` to about one in six. So every `gh api` read the seam makes is
tried up to eight times, waiting a second longer each time up to three seconds, and fails only when
the eighth fails. Pushing and opening a PR aren't retried: they aren't reads. Nor is a run's 404 in
`push_run`: a run GitHub doesn't have makes its note `unconfirmed` at once (§4).
A re-run of the push job keeps a record an earlier run wrote: labels read later are what the
record exists to avoid.

**Only a job that runs no repository code can write the notes.** A run executes the code it
checks out: `pip install -e .`, every `conftest.py`, every test, the PR's own on a PR and the
merged ones on a push. A token that can write `refs/notes/redline-ci` there would let that code
write `result: pass` or a `break:` map on any commit, which is the evidence this section trusts.
So the workflow's default token is `contents: read`, and each job says what it holds:

- **`redline`**, on both events, holds `contents: read`, with `issues: read` and `pull-requests:
  read` for the labels, and `actions: read` for the runs the ledger checks notes against (§4). No job holds `actions:
  write`, so no code a PR runs can re-run, cancel or delete a run the ledger trusts. Its checkout sets `persist-credentials: false`, and the step that fetches
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
- **`runners`** and **`windows`** hold `contents: read` and set `persist-credentials: false`;
  `runners` also holds `redline`'s `issues: read`, `pull-requests: read` and `actions: read`, for
  the real `gh api` calls (Approvals, below).

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
The runner images are named by version, never `-latest`, which GitHub moves to a new OS: Linux
jobs run on `ubuntu-24.04`, and `windows` on `windows-2025-vs2026`, since `windows-2025` already
changed its Visual Studio once under the one label.

Every package pip installs is pinned by version and by hash. Each job that installs runs three
lines, in this order, and no other pip line:

1. `python -m pip install --require-hashes --force-reinstall -r requirements-pip.txt`: pip itself,
   so the pinned pip installs the rest, not the one the Python came with.
2. `python -m pip install --require-hashes --force-reinstall -r requirements.txt`: every package
   any job installs, each `==` with its sha256 hashes. pip refuses a file whose hash isn't listed,
   and a package the file lacks, so a dependency a new release adds can't come in unpinned.
   `--force-reinstall` is there because pip doesn't check the hash of a package already installed
   at the pinned version, and Windows' Python comes with pipx's `packaging`.
3. `python -m pip install --no-deps --no-build-isolation --check-build-dependencies --no-index -e .`:
   Redline itself, which has no single file to hash, so `--require-hashes` refuses it. It downloads
   nothing, and builds with the setuptools line 2 installed, which must be `[build-system]`'s
   `setuptools==84.2.1`.

On a PR the `redline` and `suite` jobs run first the gate's, in the merge-base's worktree with
the venv's Python, line 3 installing `.`, not `-e .` (above); then `suite` runs the PR's own, and
on a push `redline` runs `main`'s.

A marker keeps mutmut, and what only it needs, off Windows, where it doesn't run, so every job
installs the one file. `npm ci` already installs from the toy's `package-lock.json`, whose sha512
hashes it checks.

The hashes are those of the wheels that install on CI's Pythons, CPython 3.12 on Linux x86_64 and
on Windows x64, not of every file PyPI holds for the version: that was 398 hashes, against 29,
and an sdist, which would run its build, isn't among them. The pins are kept by hand, and
`scripts/hashes.py`, on any platform, rewrites each pin's hash lines from PyPI's JSON API, as the
files' headers say. A bump is a PR outside any step, gated like any other.

Tests read the workflow and both files: every `uses:` is a 40-hex SHA with a `# vX.Y.Z` tag;
every `python-version` and `node-version` is `X.Y.Z`; no `runs-on` ends in `-latest`, and each
names a version; each job that runs pip runs the three lines in order, and no other, with no `==`,
`redline` and `suite` the gate's three before them;
every line of the files is a comment or an `==` pin with at least one sha256; pip is pinned;
setuptools is pinned as in `[build-system]`; and every dependency and extra in `pyproject.toml`,
and pytest-xdist, is pinned. pip refuses what the file lacks, but line 3 doesn't resolve
Redline's own requirements. So one more test, which runs only in GitHub Actions, follows what the
jobs installed, from the metadata: Redline's requirements, its `mutation` extra where mutmut is
installed and pytest-xdist where it is, and their requirements in turn. It fails on any of those
that isn't in the file at the version installed. It runs with the suite, in the `suite` job on a
PR, the `redline` job on a push, and the `windows` job. It follows requirements, not every installed distribution, because a runner image
brings tools of its own that no job installs or runs: Windows' Python carries pipx and its
dependencies. It follows the setup-python environment the suite runs in, not the gate's venv,
which installs the merge-base's `requirements.txt`, the file that passed it on the merge-base's
push run.

What it doesn't prove: that GitHub enforces the permissions it is given, or that the actions the
jobs use are sound: a pin stops a moved tag from changing them, but the pinned commit is trusted as
it is. Nor that the files the hashes were taken from were sound: they are PyPI's when the pins
were last rewritten, and a file that was bad then stays trusted. Nor what GitHub's hosted runners
bring under the pins: a version label still gets a new image build every week, git and the shell
among it (each run's log names its build), and setup-python and setup-node fetch a version's
Python and Node builds from a manifest they read as they run, which no hash of Redline's checks
(§12). Nor does it prove the note's text, which merged code
still writes for its own merge commit, as it runs the suite that says `pass`. A token with
`contents: write` held elsewhere, a maintainer's or an agent's given one, still writes any note,
but the ledger reads its result only when its run checks out (§4); its `claims:` stay its writer's
(O-NOTE2).

### Approvals

A person's approval is a label on the PR, applied by a maintainer. A commit trailer in the PR's
own commits (`base..HEAD`) says what is approved and why, and stays in `main`'s history. The label
says a maintainer agreed. Six claims need one:

| Trailer | Allows | Label |
|---|---|---|
| `Redline-Departure: <test> approved-by @person: <reason>` | a frozen test's lock entry to change (§5) | `redline:departure` |
| `Oversized: <reason>` | more than 400 changed lines (§2.3) | `redline:oversized` |
| `Redline-Track: <reason>` | a G step changing files outside its track (§5) | `redline:track` |
| `Redline-Rigor: <reason>` | a change to `rigor:` in `redline/config.yaml` or to a plan's `Rigor:` line; a change's level lowered; a glob added to its `generated:` or `support:`; a plan deleted, or a change taken out of one | `redline:rigor` |
| `Redline-Manual: <ID> checked-by @person: <what was seen>` | a `manual` scenario to close at C (§5) | `redline:manual` |
| `Redline-Relabel: waived-by @person: <reason>` | a critical change to close at C without its blind relabel (§4) | `redline:relabel` |

A person's check is evidence at the C step only, where check-close reads it. A `Redline-Manual`
trailer in any other step's PR, or in a PR outside any step, fails, naming it: no gate would read
it, yet `redline ci push` would record it under `claims:`, and the claims record would show a
check that closed nothing.

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

A trailer without its reason (or, for a departure, without `approved-by @person:`, for a manual
check, without `checked-by @person:`) allows nothing.
One label covers every claim of its kind in the PR. The labels are separate, so approving the size
doesn't approve weakening a test. Both rules call one function, `approve` in
`redline/approval.py`, which returns why a claim isn't approved, or nothing.

**A named person approves their own claim.** A departure names who approved it (`approved-by
@person`) and a manual check who made it (`checked-by @person`), and the trailer stays in `main`'s
history as that person's word. So its label counts only when the person who applied it last is
the person the trailer names, logins compared without case, as GitHub's are. Each trailer is
approved on its own: two departures of one test, or two checks of one scenario, each name
someone, and each must be the label's applier. One label has one last applier, so a PR whose
trailers of one kind name two people fails the one the applier isn't, naming both: name the same
person, or split the PR. Reading every `labeled` event instead wouldn't do: GitHub records none
while the label is on, so the second person would first remove it, and an `unlabeled` event reads
as a withdrawal. The applier must still be a maintainer, so the named person is one too. The
trailer forms live in `redline/approval.py` beside `approve`, which takes the named person, so
check-lock, check-close and the claims record read a name the same way. `Oversized`,
`Redline-Track` and `Redline-Rigor` name nobody, and any maintainer's label approves them.

`redline ci pr --pr <number>` reads the labels through the `GitHub` seam, and only when a claim
needs one. The PR's issue events (`gh api repos/{owner}/{repo}/issues/<number>/events`) give, for
each label still on the PR, who applied it last. That person is a maintainer when their role on
the repository (`gh api repos/{owner}/{repo}/collaborators/<login>/permission`, `role_name`) is
`admin` or `maintain`. The role comes from GitHub, not from a list in `redline/config.yaml`,
because a PR can edit the config to name its own author. A claim fails when its label is missing,
was applied by someone who isn't a maintainer or isn't the person its trailer names, or there is
no PR number. The workflow passes the number and a
read-only token, and also runs on `labeled` and `unlabeled`, so applying the label re-runs CI.

**A label counts only for the head it was applied after.** A label isn't tied to a commit: one
applied to the first head stays on the PR while later pushes add commits, new claims among them,
and each `synchronize` run reads it again and passes. So a claim's label counts only when it was
applied after the PR's head was pushed. The label's time is its last `labeled` event's
`created_at`. The push's time comes from GitHub's record of the head branch's pushes, the
repository activity API (`gh api repos/{owner}/{repo}/activity?ref=refs/heads/<ref>`): the
`timestamp` of the latest `push`, `force_push` or `branch_creation` whose `after` is the PR's head
SHA, the head's SHA, ref and repository read from `gh api repos/{owner}/{repo}/pulls/<number>`.
Both are GitHub's times. The PR's timeline won't do: an ordinary push leaves only `committed`
events there, dated by the commit's committer date, which its author sets; issue events record a
force push and nothing else. A claim fails when its label was applied at or before the push,
naming the label, its time, the head and its push's time, and saying to apply the label again: a
maintainer removes and re-applies it, and the `labeled` run reads the new time. It also fails
when no push of the head is found, as for a fork whose activity the token can't read: a time
that can't be read approves nothing. GitHub's "Update branch" pushes a merge to the head, so the
label is applied again after it too. Both rules call `approve`, so every claim of the five is
read this way, and the push is read once, beside the labels, only when a claim needs a label.

Locally there is no PR, so no label can exist yet. `redline pr` and `redline check-lock` don't
refuse a claim. They print that CI will need its label, and for a departure or a manual check who
must apply it (`applied by @alice, a maintainer`). A trailer that allows nothing still fails.

What the label still doesn't prove:

- **Who pressed the button.** Anyone holding a maintainer's token, including an agent given it,
  applies the label as that maintainer.
- **What they saw.** The label is tied to when the head was pushed, not to what the maintainer
  read: one applied after the push by someone who never opened the PR passes. Nor does it cover
  the base: `main` moving after the label, with no push to the head, changes the diff a gate
  reads, such as the lines check-lines counts, and the label still counts. Nor which claims of
  its kind they read: one label approves them all, so a maintainer named by two departures who
  read one approves both, by design (one label covers every claim of its kind).
- **The times.** The label's and the push's times are GitHub's, trusted as GitHub is (§12).
- **That the person looked, or at what.** A manual check's text is the person's word, about
  whatever they ran; the maintainer reads it on the C PR (§12).
- **The role at the time.** The role is read when CI runs, not when the label was applied.

**The real calls are tested on this repository's own PR.** The suite reads GitHub through fakes and
canned answers, which test what `approve` does with an answer, not that GitHub gives it: a field
renamed, a jq path that selects nothing, a ref the activity API reads another way, or a time
`moment` can't parse would each pass them. So `tests/test_github.py` makes every call the `GitHub`
seam makes, through the seam, on PR #60, merged with known answers: `pulls` of its head gives 60;
`pushed` gives its head and the activity API's `branch_creation` time, which `moment` parses;
`labels` gives the one label still on it, with who applied it and when, after another was applied
and removed; and `role` gives its author's role. `push_run` reads run 39848744114, the push run of
b41ea41, and gives its URL, `push`, b41ea41, `main`, `.github/workflows/redline.yml` and its
`redline` job's `success`, so a note on b41ea41 naming it checks out (§4); no push run has failed
lately, so only the fake answers `failure`. It also reads a run GitHub doesn't have and gets the
404 that makes a note `unconfirmed` at once, which only `gh`'s message tells from other errors. One more test reads the PR's issue events one
per page with `--paginate` and gets every line a single page gives, as `labels` and `pushed`
rely on. PR #60 carries no claim, so its labels approve nothing and are recorded nowhere, and no
PR claims `Oversized` to be tested.

The tests are skipped unless `REDLINE_REAL_GITHUB` is set, and run in a step of the `runners` job,
which holds the `redline` job's read permissions and token, so they read what CI's own token can,
the activity API and the Actions API included. They aren't in `redline ci`'s suite: a GitHub outage or a changed API
fails the `runners` job, where it is seen, and never a PR's gates or a merged commit's note. Nor
do they run on Windows. If GitHub stops keeping PR #60's records, the tests fail and move to a
newer PR. What they don't prove is a label that approves a claim in a real `redline ci pr` run:
that reads the same calls, with the same token, through `approve`, which the canned answers test.

### Repository settings

CI's answers count only where GitHub is set up to honour them. These settings are the
repository's, not Redline's: no gate makes them, and a PR can't see whether they hold. Each of
these guarantees rests on one, and without it the guarantee is a convention:

1. **A ruleset on `main`** that requires a pull request and the `redline` status check, and blocks
   force pushes and deletion. Without it a PR merges whether `redline` passes or not: the 400-line
   gate, every claim's label and the C step's check-close and check-specs (§1) are advice, and the
   push run only records `result: fail` after the merge. Only `redline` is required: `runners` and
   `windows` record nothing, and a GitHub outage fails `runners` (Approvals, above), which mustn't
   hold up a merge.
2. **The six labels** of the Approvals table: `redline:departure`, `redline:oversized`,
   `redline:track`, `redline:rigor`, `redline:manual` and `redline:relabel`. Without them no claim can be approved,
   so every PR that makes one fails.
3. **The agent in an account of its own, with the `write` role.** The agent runs `gh` with the
   credentials it is given. With a maintainer's, a label it applies is that maintainer's, and
   `approve` passes it (Approvals, "Who pressed the button"). With its own account, its role reads
   `write`, which isn't `admin` or `maintain`, so its labels approve nothing, with no change to
   Redline. A maintainer is then not the author of its PRs, so the ruleset can require their
   review before a merge, the maintainer's role in §9. `write` still pushes
   `refs/notes/redline-ci`, which no ruleset covers, so the agent can write a note on any commit;
   the ledger reads its result only when its run checks out (§4), and its `claims:` not at all
   (O-NOTE2).
4. **Merge commits or squash merges only.** The push run reads the step and the claims of the
   merged commit's own range, `<merged>^..<merged>`, so a PR merged by rebase records no claim but
   its last commit's (§4).
5. **CODEOWNERS** naming a maintainer for `.github/` and `redline/config.yaml`, with code-owner
   review required by the ruleset. On `pull_request`, GitHub runs the PR's own workflow file, so a
   PR can change what its own CI runs, which no gate sees; and the config holds the rules and
   globs every gate reads. It needs item 3's second account: GitHub doesn't ask an author to
   review their own PR.

The README repeats the list as a setup checklist. A test fails when the README or this list names
other labels than `redline/approval.py`'s.

What it doesn't prove: that the settings are set, or stay so. Whoever administers the repository
can change them between two runs, and is trusted as the maintainer is (§12).
