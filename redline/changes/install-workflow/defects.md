# Defects: install-workflow

## D1: the proposal set rigor `standard`, though the file it writes holds an adopting repository's evidence, token and gate
Cause: spec
Found-by: install-workflow/S
The proposal said the workflow "decides no evidence" (F1). In an adopting repository its jobs
write every note, its steps hold the token's permissions and the one `contents: write`, its
install chooses the Redline that gates each PR, and the command it adds is public. The proposal
now says `critical`, and C's O4 is the blind relabel.

## D2: no THEN checked that the package ships the template the command writes from
Cause: spec
Found-by: install-workflow/S
The package data held `helpers/*.js` alone, and every suite runs on an editable install, which
reads the template from the tree, so a G1 without the glob passed every scenario and failed every
adopter (F2). S5 now builds the wheel and finds the template in it.

## D3: S1 and S2 didn't say the install runs on a push, or where the project's own install goes
Cause: spec
Found-by: install-workflow/S
An install step with the merge-base's `if` passed both, and every push run would have had no
`redline` and written no note (F3). A comment inside the step's script would have run an
adopter's line in Redline's clone. S1 now says the step has no `if` and pins the comment after
its script.

## D4: nothing kept check-helpers off the written workflow, or `install jest` writing over its helper
Cause: spec
Found-by: install-workflow/S
Registering the workflow in `HELPERS` fails check-helpers in every repository that has the file,
and a refusal of an existing file put in `install` for every runner passed every test (F4). S1
now has check-helpers report nothing, P8 cites it and its callers, and H1 `[hold]` keeps `install
jest` writing over an edited helper.

## D5: §7 said the test compares the workflow line for line, where S2 compares it parsed as YAML
Cause: handoff
Found-by: install-workflow/S
The design text and the delta disagreed (F5); line for line would have tied the template to
Redline's own comments, one of which points at a `docs/design.md` an adopter doesn't have. §7 now
says what S2 tests.

## D6: S2 compared four of the `redline` job's keys, so a `name:` or an `if:` on the job passed it
Cause: spec
Found-by: install-workflow/S
A job `name:` makes the ledger find no job named `redline`, and a job-level `if` that skips a
push leaves no note (F6). S2 now compares the two documents whole once the known differences are
taken out.

## D7: check-break mutated a cited file of a package outside that package, so H1's break reached no mutant
Cause: tooling
Found-by: install-workflow/R
mutmut copied `src/redline/runner.py` into `mutants/src/redline/` with no `__init__.py`, a
namespace portion that lost to the editable install's `redline`, so the test imported unmutated
code and R's CI failed. It was the first `hold` scenario check-break ran on Redline's own code.
Build 9 part 35 (O-MUT3) copies the cited file's outermost package, and R merged after it.

## D8: G1's first push didn't rebuild the ledger after R's note reached main
Cause: handoff
Found-by: install-workflow/G1
G1's first CI run (40033876465, on ed63741) failed check-ledger: the ledger still read every red
null, as S left it, though R's merge on 092e331 had been noted. The commit 0edd591 rebuilt it.
