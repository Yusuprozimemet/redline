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

`pr` runs check-lines and check-plan always, check-steps at every step (on the step's change and each change whose
`steps.md` or deltas the PR changes, its form and what left it since the merge-base, §4), check-premises and check-audit at S (on the step's own change: an
older change's premises may go stale as the code moves on), and check-links and check-order from
the R step on (at S the delta's scenarios have no tests yet; check-order skips `hold` scenarios,
which have no red by design), check-break at the R step only, check-lock at every step (on the
whole lock, by test, against `main`'s; G steps with `--base main`, §5), check-track at G steps (§5), check-close at the C step, check-specs at every step (at S, R and G, that `redline/specs/` is untouched; at C, against the delta, §5), check-defects and check-relabel at every step on the
step's change (the log is required only at C, the relabel only at C and critical), and the rigor
check at every step (§7). A departure, an `Oversized` trailer or a manual check doesn't refuse:
the PR and its labels don't exist yet, so `pr` prints that CI will need the label, one note per
claim (§7). Only when every gate
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
