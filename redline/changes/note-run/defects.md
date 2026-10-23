# Defects: note-run

## D1: a failing `break:` entry for any scenario excused a failed job, so a forged note turned a failed run into `pass`
Cause: spec
Found-by: note-run/S
The committed S3 read a note as agreeing with a failed `redline` job whenever any `break:` entry
said `fail`, and pinned that reading. The auditor's F8 showed a note naming a scenario the change
never held could excuse any failure; now only a `hold` scenario whose break the ledger reads from
that note counts.

## D2: a `hold` scenario dropped from the delta after R made CI's own R note `unconfirmed`
Cause: spec
Found-by: note-run/S
With the rule from D1, an R note whose failed break named a scenario a later step dropped no longer
counted that failure, so the note CI really wrote no longer matched its failed job (F14). §4 and
O-NOTE3 now say which case reads `unconfirmed`, and F21 added the retag.

## D3: the requirement made every answer about a run other than a 404 an error, while S1 and S5 read answers as results
Cause: spec
Found-by: note-run/S
A run GitHub has but whose fields differ is an answer, read as `unconfirmed` in S2, yet the
requirement's last sentence made it an error (F15). It now ends "any other failure to read a run
than a 404".

## D4: S1 to S3 rested on the fields GitHub gives for Redline's real push runs, and nothing cited them
Cause: premise
Found-by: note-run/S
The scenarios named `html_url`, `event`, `head_sha`, `head_branch`, `path` and a job named
`redline` as GitHub gives them, but no line of the delta said a real run had been read (F16). P18
now records run 39848744114 as GitHub gave it on 2026-10-23.

## D5: P16 said the workflow's tests read only `--note` of the push step
Cause: premise
Found-by: note-run/S
The tests also read the step's token and command (F17), after F11 had already corrected the same
line once. P16 now says "of the push step's options only `--note`".

## D6: S3 made H's break `unconfirmed` from a green's note, which the ledger reads no break from
Cause: spec
Found-by: note-run/S
S3's THEN covered every note on the change's merges, the green's too, so a green's note with a
forged entry would have changed H's break (F18). S3 now keeps H's break `pass` from its R note and
reads only the green's result `unconfirmed`.

## D7: the proposal kept the rule D1 replaced after the delta and §4 moved on
Cause: handoff
Found-by: note-run/S
The proposal's scope still said an entry for any other scenario made a note `unconfirmed` (F19),
so the brief for R would have carried a rule no scenario held.

## D8: S5 named the repository GitHub answered 404 for, which Redline has no way to learn
Cause: premise
Decided: changed from spec to the relabel's premise; S5 said nothing wrong about the behaviour
wanted, it rested on an unchecked belief that `gh`'s 404 names the repository it asked, a claim
about the tool the scenario was written against.
Found-by: note-run/S
`gh`'s 404 names no repository (F20), so S5's error message could not be written as specified. It
now says only that GitHub doesn't show the checkout's repository to the token.

## D9: a `result: fail` note with no entry for H read H's break `fail` in the requirement and `unverified` in §4
Cause: spec
Found-by: note-run/S
The two texts disagreed and S3 pinned neither (F22). S3 and §4 now both read it `fail`, entry or
none.
