<!-- One or two sentences: the change and step (e.g. `suite-job S`), the build
     part or O-ID it covers, and its rigor level (lite / standard / critical). -->

## Design

<!-- Where the design text lives: the specs/ section and its commit, or
     "already on main: <section> (PR #n)". For an S step, the proposal and the
     delta files. Each new open problem gets an O-ID and an owning step in
     specs/12-open-problems.md. -->

## Why this approach

<!-- The diff shows what changed. Explain why you did it this way and what you
     considered instead. "An AI wrote it" is not an answer here, and it won't be
     one in review either. -->

## Code

<!-- One line per file: what it gains. "None: the S step is the spec" if so. -->

## Evidence

<!-- Commits: design, then red (N tests, all failing, no code), then green.
     The full suite passes: N tests.
     Put each deliberate break on its own line:
       broken: <what> → <which tests failed>, restored with git checkout
       broken: none → <why>
     check-lines: N (limit 400). Never claim Oversized to get past it: split the change.
     Audits, only if one ran: round n of m, model, tokens / calls, findings opened and closed. -->

- broken:
- `redline check-lines`:

## Still open

<!-- O-IDs with their owning step, e.g. "O3 [C]: close O-CI10". "None" if none. -->

None

## Self-check

- [ ] Design, red and green are separate commits, and red failed with no code
- [ ] The full suite passes locally (`.venv/Scripts/python -m pytest -n auto`)
- [ ] I broke the new logic on purpose, saw tests fail, and restored it
- [ ] `redline check-lines` ≤ 400, counting staged lines (`git diff --cached --numstat`)
- [ ] The step's gates pass (check-steps, check-specs, check-premises, check-ledger, check-audit, check-defects, whichever apply)
- [ ] No secrets, tokens or connection strings in the diff
- [ ] This PR does one step of one change
- [ ] Every open item I took has its O-ID cited, and every new one has an owner

<!-- Keep this attribution when Codex creates or updates the PR description. -->
🤖 Generated with [Codex](https://openai.com/codex/)
