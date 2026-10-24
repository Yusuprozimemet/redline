## 9. Roles

| Role | Model | Can |
|---|---|---|
| Maintainer (a person) | — | Merge; approve waivers, departures, `Oversized` |
| Main session | Strong | Specs, briefs, review, breaks, PRs |
| Auditor | Strongest (Fable, else Opus at max), fresh context | Read and report only |
| Plan-auditor | The same, fresh context | Read and report on an initiative's phase, at its start and end |
| Relabeller | The same, fresh context | Label defects from their text, blind to the first label |
| End-of-initiative auditors (3) | The same, fresh context each | Read and report on a whole initiative, each from one side, none reading another |
| Implementer | Cheaper | Code from a brief; never commits |

The CLI holds the rules; each AI tool gets thin skills or commands, as in OpenSpec.

For Claude Code the auditor is `.claude/agents/redline-auditor.md`: tools `Read, Grep, Glob` only,
`model: fable` and `effort: max`. Claude Code
can't limit Write to one file, so the auditor stays read-only and replies with the whole
`audit.md`, which the main session writes unedited. A re-run reads the old `audit.md`, keeps
every finding and closes only what it has checked. The `Waived-by:` line is the maintainer's.

**Rounds.** A change's spec gets at most one audit round at lite, two at standard and three at
critical. Each answer to a finding is new text, which the next round can open
a finding on, so without a limit the rounds never end, and each one cost a fresh read of
everything. `redline audit-brief <change>` prints the auditor's whole prompt: `Audit <change>`,
`Round: <n> of <limit>`, `Audited: <HEAD>` and `Since: <commit>`, then `git diff <since> HEAD`
without `audit.md`. The main session gives the agent that text alone, and the agent refuses any
prompt without a `Round:` and an `Audited:` line. `n` is the old `audit.md`'s `Round:` plus one,
1 without one; `Since:` is its `Audited:`, or `none` on the first round or when that commit is no
longer in HEAD's history, as after a rebase. An `audit.md` from before the limit, with no `Round:`
line, gets one last round, `n` the limit, `Since:` the parent of the last commit that changed it.
The brief refuses a working tree with uncommitted changes, since the agent reads the tree and
`Audited:` names a commit, and refuses once round `n` of the limit has run: each finding still
open is then the maintainer's, waived, or deferred to an open problem with an owning step. With
`Since: none` the agent audits the whole spec; otherwise it checks each open finding and the
changed text, with what that text cites or contradicts, and doesn't re-check a closed finding.
Each round's commit message records the agent's token and tool-call counts, as its result gives
them, so the cost of each audit stays in `git log`.

What it doesn't prove: that the main session gave the agent the brief unchanged, and wrote back
the reply's `Round:` as the agent gave it, which is its word, as an unedited reply is, though
`git log` of `audit.md` shows each round (§12, Judgments); and that a re-round missed nothing outside the
changed text, which is the reason for the first round's full read.

**Initiative rounds (O-AUDIT3, build 9 part 32).** Each phase-start, phase-end and
end-of-initiative side has its own three-round budget: these audits run only at critical.
`redline plan-audit-brief <initiative> <target>` prints the prompt; target is
`phase-<n>-start`, `phase-<n>-end`, `security`, `architecture` or `process`.
It validates the phase, names the current plan blob, `Round:`, `Audited:` and `Since:`,
and refuses dirty tracked files or a fourth round. A changed plan never resets the budget.
The first round reads the existing scope in §4; later rounds read only their own previous
reply, open findings and the diff since its `Audited:` commit, following citations or
contradictions as needed. The diff excludes this initiative's audit directory, preserving
side independence. A missing ancestor falls back to a full read without resetting the round.
The process side still receives the current `redline claims` text separately each round.
Agents refuse prompts without round/commit metadata and copy those lines into their reply.
At exhaustion, a maintainer waives or defers each open finding using the existing syntax;
model, resolution, deferral and plan-currentness checks still apply.
Legacy replies with neither metadata line remain readable; their next brief is the final
round, diffing from the parent of their last edit. Once either metadata field appears,
start/check-plan require both valid fields and a round at most three. Malformed metadata
is refused, not treated as legacy. The same trust limits as change rounds apply.

**When Fable isn't available**, as when its usage runs out, the main session runs the agent with
Opus instead (the Agent tool's `model: opus`), and the definition's `effort: max` keeps the
highest effort. The agent refuses any model but a Claude Fable or Opus one, replying `REFUSED:`,
so below Opus the work still stops. Its reply's header, before the first finding, has a `Model:`
line naming the model it ran on, as its system prompt gives it. check-audit fails an audit with no
such line, or one that names neither Fable nor Opus; the plan and end-of-initiative audits are
read by the same function, `read_findings` in `redline/audit.py`, so they fail the same way. The
relabeller's is a `# Model:` comment, which check-relabel reads. A Fable audit once Fable is back
is welcome, a re-run like any other, but no gate asks for it: a gate that did would hold the work
up as long as Fable is gone.

What it doesn't prove: that Fable was unavailable, which is the main session's word, though the
`Model:` line shows which model ran; that the agent ran at max effort, which the definition sets
and no agent can see; and that the `Model:` line is true, since the agent writes it as it writes
its findings, and the main session writes the reply unedited (§12, Judgments).

The relabeller (§4, blind relabelling) is `.claude/agents/redline-relabeller.md`, the same way:
tool `Read` only, `model: fable`, `effort: max`, and the same fallback. It is given the text `redline blind`
prints and, on a re-run, the old `relabel.yaml`, whose entries it keeps unchanged. It labels
only from the entries' text, reads no other file, and replies with the whole `relabel.yaml`.

The plan-auditor (§4, plan audits) is `.claude/agents/redline-plan-auditor.md`: tools `Read,
Grep, Glob`, `model: fable`, `effort: max`, the same fallback. It is given `<initiative> phase <n> start|end
with plan <blob>`, reads the old audit file on a re-run with the auditor's rules, and replies with
the whole file, its `Plan:` line the blob it was given, and its `Model:` line after it.

The end-of-initiative auditors (§4) are `redline-security-auditor.md`,
`redline-architecture-auditor.md` and `redline-process-auditor.md`, the same way: `Read, Grep,
Glob`, `model: fable`, `effort: max`, the same fallback. Each is given `<initiative> with plan <blob>`, reads no
other audit file but its own, and replies with the whole `initiative-<side>.md`, `Plan:` and
`Model:` lines too.
The process auditor is also given the text `redline claims <initiative>` prints (§4), and without
it opens a finding: the record's claims are out of its sight.
