# Audit: install-workflow
Model: claude-opus-5-5
Round: 1
Audited: dbfa6deaec869a2973b7404f815fba3b5e624ff8

## F1 [open]: rigor `standard` is too low: the change widens a public command and writes every adopting repository's CI, token handling included; raise it to `critical`
The proposal says `standard` because the file "decides no evidence" (`redline/changes/install-workflow/proposal.md:3`, `redline/changes/install-workflow/proposal.md:45-47`). That isn't true for an adopting repository. There the jobs this file defines produce all of the repository's evidence: the push run's note is "the only evidence Redline writes" (`docs/design.md:1441-1445`). Whether a note checks out depends on the workflow's path and on its `redline` job's name and conclusion (`src/redline/ledger.py:61-64`), and this change writes all three.

The file also carries the repository's authentication and authorization:
- the fetch step's `AUTHORIZATION: basic` header, built from `GH_TOKEN` (`.github/workflows/redline.yml:37`);
- each job's token permissions (`.github/workflows/redline.yml:11-12`, `.github/workflows/redline.yml:22-26`);
- the one `contents: write` (`.github/workflows/redline.yml:76-77`).

Its new install step chooses the code that gates every PR there.

It also changes a public API. `install`'s argument takes `HELPERS`' runners alone today (`src/redline/cli.py:91-93`), and the README must list each subcommand (`tests/test_readme.py:36-38`). The README's setup step 3 will send every adopter to this command (`README.md:48-57`). note-run was raised for the same two reasons (`redline/changes/note-run/audit.md:21-22`).

"Under CODEOWNERS" doesn't hold at the first write either. The README puts CI at step 3 and CODEOWNERS at step 4 (`README.md:58-68`).

The proposal should say `Rigor: critical`, and `steps.md` should give C the blind relabel as an open item, as note-run's O6 did (`redline/changes/note-run/steps.md:20`). The change's round limit becomes 3.

## F2 [open]: no THEN checks that the package ships the template, and the only installs the command accepts need it shipped
The requirement writes the workflow "from the template the package ships" (`redline/changes/install-workflow/specs/install/delta.md:4-5`). The package data is `helpers/*.js` alone (`pyproject.toml:21-22`), and there is no `MANIFEST.in` to add more. The change adds `helpers/*.yml` only as an open item (`redline/changes/install-workflow/steps.md:16`), which no scenario checks.

The tests can't see it either way. Each job's suite runs on an editable install (`.github/workflows/redline.yml:55`, `.github/workflows/redline.yml:116`, `.github/workflows/redline.yml:141`), so `files("redline")` (`src/redline/runner.py:220-221`) resolves to `src/redline/`, which holds the template whether or not it is package data. `tests/test_jest.py:38` reads the jest helper the same way.

The command goes ahead only for a Redline installed from a git commit, never an editable one (`redline/changes/install-workflow/specs/install/delta.md:26-28`). pip builds that install into a wheel, which holds the template only if the package data names it. So a G1 without the glob passes every scenario, and the command fails for every adopter.

A test can check it. For example: the wheel built from the tree with `pip wheel --no-deps --no-build-isolation --no-index` holds `redline/helpers/redline.yml`, equal to the template. The build needs only the setuptools every job installs by hash (`pyproject.toml:2`). Such a scenario fails today, as a `[new]` one must.

## F3 [open]: S1 and S2 don't say when the install step runs: a PR-only install passes both, and every push run is left without Redline or a note
S1 pins what the install step clones, checks out and runs (`redline/changes/install-workflow/specs/install/delta.md:16`), and S2 puts it "in place of the editable install" (`redline/changes/install-workflow/specs/install/delta.md:22`). Neither says it runs on a push.

The step it most resembles, the merge-base's install, also works in a tree under `$RUNNER_TEMP`, `cd`s there and installs `.`. That step runs on a PR alone (`.github/workflows/redline.yml:43-51`). The editable install it replaces has no `if` (`.github/workflows/redline.yml:52-55`), and the push step needs it (`.github/workflows/redline.yml:62-66`).

With the merge-base's `if`, the install passes S1 and S2 as written. Every push run would then fail at `redline ci push` with no `redline` installed, and write no note file. The `note` job then never runs (`.github/workflows/redline.yml:67-70`, `.github/workflows/redline.yml:74`). Every red and green in the adopting repository would stay `unverified`, and nothing fails until check-close refuses at C. S1 should say the step has no `if`, and that its keys besides `run` and `name` are the editable install's.

The comment that marks the project's own install (`redline/changes/install-workflow/proposal.md:24-25`, `docs/design.md:1344-1345`) is in no THEN, and its place matters. S1's pip lines use paths relative to the clone, so the step's script runs there. If the comment sits in that script after them, a line an adopter adds at it runs in Redline's clone too: `pip install -r requirements.txt` would read Redline's file. A THEN should pin where it goes, for example after the install step and outside its script.

## F4 [open]: no THEN keeps check-helpers off the written workflow, or keeps `install jest` writing over an edited helper
The command and its template land beside the code built around `HELPERS` (`src/redline/runner.py:25`):
- `install` takes its runners alone (`src/redline/cli.py:92`).
- `shipped` reads `helpers/` plus the helper path's file name (`src/redline/runner.py:220-221`). For `.github/workflows/redline.yml` that is `helpers/redline.yml`, the template's path in the scope (`redline/changes/install-workflow/proposal.md:18-19`).
- `check_helpers` compares each of `HELPERS`' files that exists with the shipped copy (`src/redline/runner.py:230-234`), on every step's PR (`src/redline/pr.py:216`) and every PR outside one (`src/redline/ci.py:108`).

No written workflow equals the template, since its url and commit are filled in. Neither does Redline's own. And a written one may hold the repository's own steps (`docs/design.md:1355-1356`). So registering the workflow in `HELPERS` fails check-helpers in every repository that has the file. Its remedy, "run `redline install workflow`" (`src/redline/runner.py:232`), is one S4 refuses.

Comparing the workflow with the template filled in instead fails every repository that installs its own dependencies at the comment, as most must. No scenario tells these designs from the right one. Redline's suite runs no check-helpers on a checkout that has the file: `tests/test_self.py:23-25` runs check-links and check-order alone.

The other way round, `install` writes over an existing file (`src/redline/runner.py:224-227`), which check-helpers' remedy for an edited jest helper relies on. S4 puts the opposite rule in the same command. The only `install jest` test writes into a fresh repository (`tests/test_jest.py:35-41`), so a refusal put in `install` for every runner passes every test.

What's needed:
- a premise citing `check_helpers` and its callers;
- a THEN, in S1 say, that check-helpers reports nothing for the written workflow, with a step added to it too;
- a `[hold]` scenario in which `redline install jest` over an edited `redline/runners/jest.js` exits 0 and writes the shipped helper.

## F5 [open]: §7 says the test compares the workflow "line for line", but S2 compares it parsed as YAML
§7 says the test compares the written workflow with Redline's own "line for line outside the install and the PR gate" (`docs/design.md:1349-1351`). S2 compares them parsed as YAML (`redline/changes/install-workflow/specs/install/delta.md:20`), and so does the scope (`redline/changes/install-workflow/proposal.md:37-38`). Line for line would tie the template to Redline's comments too. One of them points an adopting repository at a `docs/design.md` it doesn't have (`.github/workflows/redline.yml:1`). §7 should say what S2 tests; G1's track has `docs/design.md` (`redline/changes/install-workflow/steps.md:10`).
