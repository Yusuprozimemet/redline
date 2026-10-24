## 12. Open problems

Every limit a "What it doesn't prove" list names is either an O-item below, with an owning step,
or a judgment this list names, with whose it is and why no gate can make it (§2.7).

**Judgments**, which stay so:

- **Whether a test asserts its scenario's THEN clauses.** The change auditor runs at S, before any
  test exists, so it can't check this. A gate bounds it: a `new` test that asserts nothing passes
  on today's code and fails its strict red; a `hold` test that asserts nothing kills no mutant and
  fails its break. A test that asserts some clauses and not others passes both. Whether it covers
  them all is the maintainer's, reviewing the R PR, and at critical the architecture auditor's
  (§4), which asks what a test could pass while violating.
- **Whether a scenario really can't be automated** (§4): a `[manual]` scenario needs no test, so
  the tag is a way around red and green. No gate can tell a scenario no assertion can read from
  one nobody tried to test; the auditor challenges each at S, and the maintainer reviewing the S
  PR sees its `Manual:` line. Nor can a gate see what the person checked: the `Redline-Manual`
  trailer's text is their word, and the maintainer whose label approves it reads it on the C PR.
- **Mutation cost on large codebases** is a cost, never a gate passed: only the files the change's
  premises cite are mutated, at the R step only, each scenario's runners stopping at the first
  kill (§5). A run that takes too long fails CI where it is seen. How much to cite is the
  auditor's, who checks the premises.
- **What an Opus audit misses that Fable would have caught** (§9): when Fable isn't available the
  auditors run on Opus at max effort, and the main session that wrote the spec may be Opus too, so
  the two can share blind spots that a fresh context narrows and doesn't remove. Waiting for Fable
  instead could hold the work up without end. The `Model:` line shows which audits ran so; whether
  to have Fable audit one again is the maintainer's call.
- **What `reach` can't follow** (§5): a static reading doesn't run the code, so dynamic imports,
  plugins and renamed fixtures are out of its sight, and following every import would hash the
  code under test. At critical, whether a locked test leans on one is the auditor's.
- **That the code under test still meets a frozen bound** (§5): the second test outside the frozen
  set is named by the departure's spec, which the auditor reads at S.
- **What Redline can't observe**: what an agent read, and that its reply was written unedited
  (§4, §9); who pressed a label's button, and the role a person had before CI ran (§7); that
  GitHub's times for a label and a push are true, and its record of a run a note names (§4), and
  what a maintainer read before labelling (§7); that
  GitHub enforces the permissions it is given, gives each job of a hosted runner a machine of
  its own, which a reused self-hosted runner doesn't, and runs an `always()` job in a cancelled run
  (§7); that a pinned action's commit is sound; that
  PyPI's files were sound when their hashes were taken; what a hosted runner brings under the pins,
  its image's weekly build under a version label and the Python and Node builds the setup actions
  fetch by version (a container pinned by digest would only move that trust to its registry and
  its package manager); and the note's text, which merged code writes for its own merge commit by
  running the suite (§7); and, in Redline's own suite, the PR's pytest plugin, which applies strict
  xfail to the PR's own tests, since one process imports one `redline` (§7, the merge-base's
  Redline). Each is recorded where it applies; none has a mechanism Redline could add.
- **What the claims record leaves out** (§4): PR text, which is untrusted and an injection path
  into the process auditor's context, so it is left out on purpose; and a claim in an earlier
  commit of a PR merged by rebase, since the push run reads the merged commit's own range.
  Redline needs merge commits or squash merges; allowing only those is a repository setting, as
  branch protection is.
- **What a new spec file says outside its requirements, and the order of requirements** (§5): a
  delta has no form for a file's title and preamble, or for where a requirement sits, and neither
  states behaviour a test proves. The maintainer reads both on the C PR.
- **Whether the repository's settings hold** (§7, Repository settings): its administrator sets
  them and can change them between two runs, so a gate that read them would prove only that they
  held when it ran. The administrator is trusted as the maintainer is.

- O-SPEC1 [closed, build 9 part 15]: every gate found scenarios by `#### Scenario <ID>
  [new|hold]:`, so a heading with an unknown tag, such as the `[manual]` §12 once suggested, or with
  none, was no scenario at all: it needed no test, no evidence at C and no place in `specs/`, and
  check-links reported `0 scenarios` without a gap. Now check-links and check-steps fail a line
  that starts `#### Scenario` in any other form, naming its file and line, with one function,
  `malformed` in `redline/links.py` (§4).
- O-SPEC2 [closed, build 9 part 16]: a scenario that can't be automated (visual, timing) had no
  form, so check-links failed it as a malformed heading. Now it is `[manual]`, with one `Manual:
  <reason>` line in its block, which the auditor may challenge at S; it has no test, and a linked
  one is a gap; check-links and check-steps fail the line missing, empty, repeated or under
  another tag, with one function, `unreasoned` in `redline/links.py`; check-specs carries it into
  `specs/`; its ledger entry has no evidence; and check-close refuses it until O-SPEC3 (§4).
- O-SPEC3 [closed, build 9 part 17]: a `[manual]` scenario couldn't close, since check-close had
  no way to record a person's check of it (§5). Now it is the fifth claim, `Redline-Manual: <ID>
  checked-by @person: <what was seen>`, in the C PR's own commits, with a maintainer's
  `redline:manual` label (§7), which `redline ci push` records under `claims:` and `redline
  claims` prints; check-close fails a manual scenario without one, a trailer missing `checked-by
  @person: <text>` and one naming no manual scenario of the change, and takes `--base`; a trailer
  in any PR that isn't a C step fails, with one function, `misplaced` in `redline/close.py`.
- O-CLOSE6 [build 11]: check-close takes a scenario's red, green or break from the whole suite's
  result on the merged commit, so a test skipped or not collected there passes with it (§5). The
  plan: each linked test's outcome in the note, red the first commit where the scenario's `new`
  tests failed strictly, green where they passed without `new`.
- O-CLOSE7 [closed, build 9 part 18]: check-specs compared scenarios only, so a requirement's
  prose, a `### Requirement:` heading with no scenario, or text before the first requirement
  changed unseen at C (§5). Now a delta's prose under an ADDED or MODIFIED requirement is copied as
  its scenarios are, and without it the living prose stays; a requirement or spec file left with no
  scenario goes; text under no requirement changes only in a file C creates or deletes (§4); each
  is compared with the merge-base by `prose_changes` in `redline/specs.py`.
- O-SPEC4 [closed, build 9 part 19]: only C ran check-specs, and check-track exempts `redline/`, so
  an S, R or G PR could change anything under `redline/specs/`, scenarios included, and check-specs
  at C, which compares with C's own merge-base, never saw it. Now at S, R and every G step
  check-specs fails on each file under `redline/specs/` that differs from the merge-base with
  `main`, naming it, found by `touched` in `redline/pr.py`, which the refusal of a PR outside any
  step uses too (§5, §7). The lock needed no such rule: it is compared by test with the
  merge-base's at every step, S and C included (§5).
- O-LOCK4 [build 8]: the lock reads no timing from outside its files: environment variables
  (`PYTEST_TIMEOUT`, `PYTEST_ADDOPTS`), flags in the CI workflow, or data files a test reads (§5).
  It is runner configuration outside a step, with O-RUN4.
- O-CI9 [closed, build 9 part 20]: the toolchain was pinned by version, not hash, so an index
  serving other files under a version wasn't caught; pip came with the pinned Python, and the
  runner images (`ubuntu-latest`, `windows-latest`) moved with GitHub's updates. Now every job
  installs pip from `requirements-pip.txt`, then `requirements.txt`, both with `--require-hashes`
  and `--force-reinstall`, then Redline with `--no-deps --no-index`, building with the hashed
  setuptools; the hashes are those of the wheels for CI's Pythons, written by `scripts/hashes.py`;
  and the jobs run on `ubuntu-24.04` and `windows-2025-vs2026` (§7). What a hosted runner still
  brings under the pins is a judgment, above.
- O-APPR1 [closed, build 9 part 21]: a label isn't tied to a commit, so commits pushed after it,
  with new claims, were covered by it until someone removed it, and each `synchronize` run read it
  again and passed (§7). Now `approve` counts a claim's label only when its last `labeled` event is
  later than the PR's head's last push, read through the `GitHub` seam from the repository activity
  API of the head's repository, not from the commit's dates, which its author sets; a label at or
  before the push, or a head with no push found, fails the claim with both times; and `redline ci
  push` records `at:` and `pushed:` under `claims:`, which `redline claims` prints (§4, §7). What
  the maintainer read, and a base that moves after the label, stay limits (§7).
- O-GH2 [closed, build 9 part 21]: `GitHub.labels` split each issue event on a literal tab
  character in its source (the review's item 18), so an editor that turned tabs into spaces would
  have broken every label read. Now it splits on `"\t"`, and a test fails on a tab in `pr.py`.
- O-APPR2 [closed, build 9 part 22]: any maintainer's label approved a departure, whoever its
  trailer named as approving, and a manual check, whoever its trailer named as checking, so
  `main`'s history could say a person agreed who never did (§7). Now `approve` takes the person
  the trailer names, read with the trailer forms in `redline/approval.py`, and fails a label whose
  last applier isn't that person, logins compared without case, naming both; each trailer is
  approved on its own, so trailers of one kind naming two people fail the one the applier isn't;
  locally check-lock and check-close say who must apply it; and `redline ci push` records `named:`
  under `claims:`, which `redline claims` prints (§4, §7). That one label approves every claim of
  its kind, read or not, stays a limit (§7).
- O-GH1 [closed, build 9 part 23]: the real `gh api` calls that read labels, roles, merged PRs, a
  PR's head and its pushes were tested only by hand; the suite used fakes and canned answers, so a
  renamed field, a jq path selecting nothing, the activity API's ref or a time `moment` can't parse
  would have passed it. Now `tests/test_github.py` makes each call through the seam on merged PR
  #60, whose answers are known, and reads its issue events one per page with `--paginate`, in a
  step of the `runners` job holding the `redline` job's read permissions and token, skipped without
  `REDLINE_REAL_GITHUB`, so GitHub down fails that job and never the gates (§7). That GitHub keeps
  answering so is seen on every run there; Redline's own PRs run as steps stays the review's item 17.
- O-GH3 [closed, build 9 part 23]: the seam failed a read on GitHub's first error, and testing the
  real calls (O-GH1) found that `commits/<sha>/pulls` answers HTTP 500 with an empty body to about
  four calls in ten, at random, so a push run whose merge carried a claim failed and lost its
  claims record more often than not. Now each `gh api` read, `GitHub.read`, is tried up to eight
  times, waiting 1, 2, then 3 seconds; pushing and opening a PR are tried once (§7).
- O-DOC1 [closed, build 9 part 24]: the README said steps 1–6 were on `main` when step 7 was too and
  step 5 wasn't finished, and had no install, commands, walkthrough or settings (the review's
  item 16). Now it says how to install Redline and set up a repository, lists every command, walks
  one toy change from S to C, checked by running it, and lists the repository settings as a
  checklist; it restates no progress, pointing to §11 and §12; and `tests/test_readme.py` fails
  when its command table isn't the CLI's subcommands, it names a command that doesn't exist, or it
  names other labels than `redline/approval.py`'s.
- O-SET1 [closed, build 9 part 24]: §7 rested on a protected `main`, the claim labels, an agent without a
  maintainer's role, no rebase merges and a person reviewing workflow changes, and listed none of
  them, so nothing told whoever sets up a repository what Redline needs (the review's item 7).
  Now §7, Repository settings, lists each with the guarantee it holds up, and a test fails when
  that list names other labels than `redline/approval.py`'s.
- O-SELF1 [closed, build 9, the change note-run]: Redline's own PRs carried no `Redline-Step`
  trailer, so they ran outside any step, and its own red before green was a commit convention, not
  evidence (the review's item 17). Now each build part is a change under `redline/changes/`, its
  design text, proposal, delta and audit at S, its red tests at R, its code at G, its delta into
  `redline/specs/` at C, run through `start`, `pr` and `merged`. `note-run` was the first: its C
  step passed check-close on Redline itself, each red and green confirmed by its push run (§4).
- O-SELF2 [closed, build 9 part 25]: a runner ran pytest with the Python Redline runs in, so the
  Redline that gates a PR and the code its suite tests had to be one installation: a gate in an
  environment of its own would import itself in the suite (O-SELF3). Now `redline ci pr --python
  <path>` runs the suite and check-break's unmutated runs with that interpreter, through
  `interpreter` in `redline/runner.py`, for that run only; a path that isn't a file, or the option
  on `ci push`, is an error (§7).
- O-SELF3 [closed, build 9 part 26]: the workflow installed the Redline the PR contains, `pip
  install -e .`, so a PR that weakened a gate was checked by the weakened gate (the review's item
  17). Now, on a PR, the `redline` job installs the merge-base's Redline, not editable, into a venv
  of its own with the merge-base's pins, before any of the PR's code runs, and calls that venv's
  `redline ci pr --python "$(command -v python)"`, so the suite tests the PR's own Redline; a push
  run is unchanged (§7, the merge-base's Redline).
- O-CI10 [closed, build 9 part 31, the change `suite-job`]: the PR's code, its install, suite and
  check-break's runs, ran in the gate's job as the same user, so it could rewrite a file the gate
  imports after it, in the standard library, the gate's venv or, in an adopting repository, the
  site-packages it shares with the gate (§7, the merge-base's Redline). Now, on a PR, a `suite`
  job with `contents: read` and no outputs installs the merge-base's Redline, then the PR's own,
  and runs `redline ci suite`: check-break at an R step, then the suite. The `redline` job, which
  `needs` it and runs `if: always()`, installs only the merge-base's Redline, `cd`d out of the
  PR's checkout before `python -m venv`, and runs `ci pr --suite-result`, every other gate and
  check-break's two refusals that run no test, reading the suite job's result and nothing else of
  it, in Redline's own workflow and the one `redline install workflow` writes (§7, the PR's code
  runs in a job of its own). Its C step passed check-close, each red and green and H1's break,
  confirmed by its push run (§4).
- O-CI11 [build 9 part 37]: in an adopting repository's workflow the project's dependencies install
  twice, in the `suite` job and, on a push alone, in the `redline` job, each by hand; nothing checks
  that a step there has `if: github.event_name == 'push'`, without which the PR's code runs in the
  gate's job again, and on a push they share the gate's site-packages and can replace one of its
  pins (§7). The plan: the project's install written once, in a local composite action both jobs
  call, and the gate in a venv of its own on a push too, with `ci push --python`.
- O-LINK1 [closed, build 9 part 28]: check-links failed every scenario of a change whose S step was merged
  and whose R wasn't, though at S they have no tests by design, so one change's merged S failed every
  other change's R, G and C gates, and Redline's own suite on the S merge's push run, until its R
  merged: changes of one phase couldn't run beside each other (§6). Now a change with only its S
  merged on `main`, unless the step gated is its own from R on, or the change of a step gated at S,
  has no unlinked gaps, its other gaps kept, by `waiting` in `redline/links.py`; a gate passes its
  step, and check-links on its own reads it from `main..HEAD`'s trailers or the open step, printing
  each waiting change as skipped (§5).
- O-SELF4 [closed, build 9 part 30, the change `install-workflow`]: a repository adopting Redline
  had no workflow to start from, since `.github/workflows/redline.yml` is Redline's own. Now
  `redline install workflow` writes one from the template `src/redline/helpers/redline.yml`, which
  installs Redline from the git commit `direct_url.json` records, by hash, on a push as on a PR,
  and refuses an install with no commit or an existing file; a test keeps it in step with
  Redline's own outside the install and the PR gate, and the README's setup step 3 names it (§7,
  an adopting repository's workflow). Its C step passed check-close, each red and green, and H1's
  break, confirmed by its push run (§4).
- O-SELF6 [build 9 part 36]: `redline install workflow` writes `direct_url.json`'s URL into the
  install step's script quoted for the shell alone, as the spec takes any URL with a git commit. A
  URL holding `${{` would be an Actions expression, and one holding a line break would end the
  YAML block, before the quoting counts. pip writes the URL the person installing typed, and the
  file is reviewed under CODEOWNERS before it runs, so it is their own; still, the command should
  refuse a URL outside the characters a git URL needs.
- O-SELF5 [closed, build 9 part 27]: Redline's own tree failed check-links and check-order, which
  every step from R on runs: `tests/toys/jest/src/adult.test.js` linked TOY.H1 and TOY.H2, which no
  spec declares, and check-order read their green with no red in af3968c, which stays in history.
  Its Python toy markers sit in strings, which count as nothing (O-MARK1). Now the toy's test file
  is written from a string by the tests that run it and ignored; check-order judges only scenarios
  a test at its commit still links, printing the others as skipped, and `redline check-order` skips
  `hold` scenarios as the gate does, both through `failed` in `redline/order.py`; and
  `tests/test_self.py` fails when either gate fails on Redline's own checkout (§5).
- O-AUDIT1 [closed, build 9 part 29]: the auditors and the relabeller ran only on Fable, so when
  Fable's usage ran out every S step stopped, however long that lasted, and nothing recorded which
  model wrote an audit. Now each agent has `model: fable` and `effort: max`, is run with `model:
  opus` when Fable isn't available, and refuses any other model; each audit names its model in a
  `Model:` line before its first finding, and each relabel in a `# Model:` line before its first
  entry; `unnamed` in `redline/audit.py` fails one with none or with a model weaker than Opus, for
  check-audit, the plan and end-of-initiative audits, and check-relabel (§9).
- O-AUDIT2 [closed, build 9 part 29a]: nothing limited a change's audit rounds, and each re-run
  read the whole spec, design and audit again: note-run/S's fifth round cost 219,894 tokens and
  49 tool calls, and opened two findings on the fourth's answers. Now `redline audit-brief` gives
  each round its number, refuses past the change's level (1, 2, 3), and gives a re-round only the
  diff since the commit the last one read; check-audit fails an audit without `Round:` and
  `Audited:` lines or past the limit, and a finding the maintainer defers needs `Deferred-to:` (§9,
  Rounds).
- O-AUDIT3 [build 9 part 32]: the plan and end-of-initiative audits have no limit on their
  rounds, and each re-run reads its whole initiative again.
- O-RELABEL1 [closed, build 9 part 38]: at the C step of a critical change, check-relabel failed
  without `relabel.yaml`, and nothing let a maintainer waive the relabel, as an audit finding can
  be waived, so a change whose maintainer chose to skip it couldn't close (found at suite-job/C).
  Now a `Redline-Relabel: waived-by @person: <reason>` trailer in the C PR's own commits stands in
  for the missing file, approved by the `redline:relabel` label applied by the person it names, a
  maintainer, through `check_relabel` in `redline/relabel.py`; in another form, beside a
  `relabel.yaml`, below critical, in any other step's PR or outside any step it fails, and `redline ci push` records
  it under `claims:` (§4, Blind relabelling; §7, Approvals).
- O-NOTE1 [closed, build 9, the change note-run]: a note was trusted because CI writes it, but anyone
  with the `write` role, the agent's own account among them (§7, Repository settings), can push
  `refs/notes/redline-ci`, which no ruleset covers, and write `result: pass` or a `break:` map on
  any commit (§4). Since note-run's G1, the rebuild checks each note it reads against its `run:` on
  GitHub's Actions API, through `GitHub.push_run`: a push run of `.github/workflows/redline.yml` on
  `main`, in this repository, on the noted commit, whose `redline` job concluded `success` exactly
  when the note records no failure; any other note reads `unconfirmed`, which check-close refuses
  as a note that doesn't match its run (§4, §5). The rest of the note's text is O-NOTE2's, and
  evidence a run can no longer confirm O-NOTE3's.
- O-NOTE2 [build 11]: a run that checks out confirms how it ended, not the rest of its note: the
  `claims:` record, which anyone with the `write` role can still rewrite, and which `break:` entry
  failed when one did, since the job's outcome says only that one failed (§4).
- O-NOTE3 [build 11]: a note CI really wrote can read `unconfirmed` for good, and its change can
  then never close: a run GitHub no longer re-runs, after 30 days; a run deleted, which anyone
  with the `write` role can do; and every run of a repository renamed or transferred, whose
  `html_url` no longer matches its notes; and an R merge whose failed break names a `hold`
  scenario a later step drops from the delta or retags, whose note then records no failure the
  ledger counts beside the job's `failure` (§4). What then confirms that evidence is open.
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
- O-PERF1 [closed, build 9 part 12]: check-order ran `git ls-tree` and `git cat-file` on every commit of
  the history, the parents before a window too: 393 git calls and 9.3 s for this repository's 196
  commits on Windows, run by every gate from R on and twice more at C (check-close and
  check-ledger each rebuild the ledger). And the ledger's `merged`, and `redline claims`, asked
  `git merge-base --is-ancestor` of each first-parent commit in turn until one contained the
  commit. Both grew with the history. Now check-order reads it in a fixed number of calls, a
  commit's markers carried from its first parent unless its diff changes a runner's file (§5), and
  a commit's merge is found in one `rev-list` (§4): 2 calls and 0.3 s on the same 196 commits, the
  same output. The two rebuilds at C stay separate: each is a
  few calls now, and a result shared by ref could go stale within a process.
- O-STEPS1 [closed, build 9 part 13]: `parse_steps` kept only `- <ID> [<step>]: <text>` lines under
  `## Open items`, so an item with no ID, or with an ID and no owner, was dropped without a word,
  though §1 said CI fails on any item without one. Nothing checked `steps.md` as a whole either:
  steps out of order or named twice, an `Owns:` ID no delta declares, and a `new` scenario no G
  step owns, found only at C by check-close. Now check-steps fails on each, at every step, on the
  step's change and each change whose `steps.md` or deltas the PR changes, from one parser,
  `scan`, which `parse_steps` uses too (§4).
- O-STEPS2 [closed, build 9 part 14]: check-steps read one `steps.md`, so an open item deleted, an
  item given to a step already merged, which progress never prints, or a step removed since the
  merge-base, passed it. Now the same gate compares each change's `steps.md` with the merge-base's,
  items by ID and steps by name, and fails on an item dropped, at its owning step too, unless the
  PR adds its text to another change's; on an item given to a merged step; and on a merged step,
  or the PR's own, removed (§4).
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
- O-MUT3 [closed, build 9 part 35]: mutmut copies only the cited files, so a cited file in a package
  landed in a copy of that package with no `__init__.py`, a namespace portion that loses to the
  package the tests can import from anywhere else, such as the checkout an editable install
  points at. The tests ran the unmutated code and reached no mutant, mutmut stopped, and the run
  failed: INSTALL.WF.H1 on `src/redline/runner.py`, in install-workflow/R's CI (PR #75), the first
  `hold` scenario check-break ran on Redline's own code. The real mutmut had run only on a
  top-level module. Now `also_copy` adds each cited file's outermost package, by `package` in
  `redline/breaks.py` (§5), and the `runners` job runs the real mutmut on a `src/` package the
  tests can also import from the original tree.
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
