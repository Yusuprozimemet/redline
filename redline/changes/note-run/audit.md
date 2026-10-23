# Audit: note-run
Model: claude-opus-5-5
Round: 3
Audited: 9ce15fd2809974d5bd86984f4bbe1a09bee28786

## F1 [closed]: no scenario pins the requirement's "in this repository"; a run looked up where the note's URL points meets every THEN
Resolution: the requirement now asks for the run in the checkout's own repository, by its id alone (`redline/changes/note-run/specs/ledger/delta.md:6-7`). S2 reads `unconfirmed` for a note naming another repository's run that GitHub has there, with every field as in S1 and the note's `run:` as its `html_url` (`redline/changes/note-run/specs/ledger/delta.md:21-22`).

## F2 [closed]: S4 and S5 rest on telling a 404 from other errors, which no premise states and only the fake will show
Resolution: P13 states what `gh api` gives for a run GitHub doesn't have (`redline/changes/note-run/specs/ledger/delta.md:79`). O2 reads such a run for real in `tests/test_github.py`, and O1 leaves those reads to GitHub (`redline/changes/note-run/steps.md:15-16`). S4 asks GitHub about each run once in a rebuild, however many entries read its note (`redline/changes/note-run/specs/ledger/delta.md:37`). F9 covers what else a 404 can mean.

## F3 [closed]: no THEN pins the note a failed break really writes, so a real failure may read `unconfirmed`
Resolution: S3 now reads `result: pass` with a `break:` entry `fail` and the job's `failure` as `pass`, with that break `fail` (`redline/changes/note-run/specs/ledger/delta.md:30`). It reads a run with no `redline` job as `unconfirmed` (`redline/changes/note-run/specs/ledger/delta.md:27-28`). As written, that clause is too wide: see F8.

## F4 [closed]: the requirement's "any other note reads as `unconfirmed`" contradicts S5, and a malformed note is left open
Resolution: the requirement now makes any failure to read GitHub other than a 404 an error. It makes a `result:` that is neither `pass` nor `fail` an error too, before GitHub is asked (`redline/changes/note-run/specs/ledger/delta.md:7-9`). S5 pins exit 2 naming the commit, with GitHub not asked (`redline/changes/note-run/specs/ledger/delta.md:45`). P15 states today's error (`redline/changes/note-run/specs/ledger/delta.md:81`).

## F5 [closed]: the workflow's `actions: read` is in scope but in no scenario, and no test reads it
Resolution: a requirement and S7 [new] now say the `redline` and `runners` jobs hold `actions: read`, and that no job, nor the workflow's default, holds `actions: write` (`redline/changes/note-run/specs/ledger/delta.md:55-64`). S7 fails today, since neither job holds `actions` (`.github/workflows/redline.yml:22-25`, `.github/workflows/redline.yml:95-98`). P16, which describes the tests, is F11.

## F6 [closed]: rigor `standard` is too low: the change authenticates CI's evidence and changes a public API; raise it to `critical`
Resolution: the proposal now says `Rigor: critical` (`redline/changes/note-run/proposal.md:3`), with the blind relabel as O6 [C] (`redline/changes/note-run/steps.md:20`).

## F7 [closed]: the scenarios assume `gh` wherever a ledger is rebuilt; no premise says so, and the README says otherwise
Resolution: P14 states what happens without `gh` (`redline/changes/note-run/specs/ledger/delta.md:80`). S5 makes it exit 2, saying `gh` is needed, with no traceback (`redline/changes/note-run/specs/ledger/delta.md:44`). O5 [G1] gives the README's Install and CI sections `gh` and `actions: read` (`redline/changes/note-run/steps.md:18`).

## F8 [closed]: any failing `break:` entry excuses a failed job, so a forged note still turns a failed run into `pass`, and S3 pins this
Resolution: S3 now reads `unconfirmed` for a note on a green's merge, which the ledger reads no break from, that says `result: pass` with H's entry `fail` beside the job's `failure` (`redline/changes/note-run/specs/ledger/delta.md:33-34`). Forgery 2 is pinned at `redline/changes/note-run/specs/ledger/delta.md:32` and forgery 3 at `redline/changes/note-run/specs/ledger/delta.md:35`. Each forgery F8 names now reads `unconfirmed` or `fail`, and an implementation that counts a failing entry for any of the change's `hold` scenarios fails S3. What that THEN says of H's break in the green's case is F18.

## F9 [closed]: a 404 doesn't only mean GitHub lacks the run, so a reader that can't see the repository reads every note `unconfirmed`, reported as not matching its run
Resolution: the rebuild reads the checkout's own repository once, before any run, and a 404 there is an error naming that repository, with no run asked for (`redline/changes/note-run/specs/ledger/delta.md:10-13`, `redline/changes/note-run/specs/ledger/delta.md:49`). P13 states that GitHub answers that 404 for a repository it doesn't show the token (`redline/changes/note-run/specs/ledger/delta.md:87`), and §4 says why the repository is read (`docs/design.md:351-355`). That read doesn't cover the fork-only clone F9 also named, and that case isn't kept open. It needs the notes fetched into a clone whose `gh` resolves `{owner}/{repo}` to a fork, and it fails closed, since CI's check-ledger rejects the ledger that clone writes. What's left is a misleading line in that one local setup.

## F10 [closed]: a note CI really wrote can read `unconfirmed` for good, and the only remedy the spec gives, a re-run, isn't always possible
Resolution: §4's "What it doesn't prove" names all three cases (`docs/design.md:361-366`), as O-NOTE3, owned by build 11 (`docs/design.md:2118-2121`, `docs/design.md:1904-1907`). The proposal makes them a non-goal (`redline/changes/note-run/proposal.md:63-64`). Wherever a re-run is the remedy, it now comes with GitHub's 30 days (`redline/changes/note-run/proposal.md:46-48`, `docs/design.md:357-359`, `docs/design.md:1125-1128`, `docs/design.md:1433-1436`).

## F11 [closed]: P16 is wrong: the workflow's tests read more than each job's `contents`
Resolution: P16 now names what those tests read: the default's and the `note` job's permissions as a whole (`tests/test_ci.py:278`, `tests/test_ci.py:280`), every other job's `contents` (`tests/test_ci.py:299`), the `redline` job's `pull-requests` (`tests/test_approval.py:206`), and the `runners` job's permissions as equal to the `redline` job's (`tests/test_approval.py:216`), at `redline/changes/note-run/specs/ledger/delta.md:90`. Its clause on the push step is still loose: see F17.

## F12 [closed]: two readings of an untrusted note are left open: a note that isn't YAML, and a hold scenario's missing entry in a note that doesn't check out
Resolution: a note that isn't YAML is now an error before GitHub is asked (`redline/changes/note-run/specs/ledger/delta.md:11-13`). S5 pins exit 2 naming its commit, with no traceback (`redline/changes/note-run/specs/ledger/delta.md:51`), and P15 states today's uncaught `yaml.YAMLError` (`redline/changes/note-run/specs/ledger/delta.md:89`). S3 reads H's break as `unconfirmed` in a note that doesn't check out, also when the note has no entry for H (`redline/changes/note-run/specs/ledger/delta.md:33`), as §4 does (`docs/design.md:350-351`).

## F13 [closed]: an adopting repository's workflow file name, job name and `--run-url` now decide whether any of its notes check out, and nothing tells it
Resolution: O5 has the README say that a note checks out only from a push run of `.github/workflows/redline.yml` whose `redline` job runs `redline ci push` with `--run-url` set to its own run's URL (`redline/changes/note-run/steps.md:18`). The second requirement and S7 pin the same in Redline's own workflow (`redline/changes/note-run/specs/ledger/delta.md:61-65`, `redline/changes/note-run/specs/ledger/delta.md:67-70`).

## F14 [closed]: a `hold` scenario dropped from the delta after R makes CI's own R note `unconfirmed`
Resolution: §4 now says a delta that drops a `hold` scenario after R still reads its R note when that scenario's break passed, and reads it `unconfirmed` when the break failed (`docs/design.md:343-346`). O-NOTE3 names the failed case (`docs/design.md:2126-2128`), and so does the proposal's non-goal (`redline/changes/note-run/proposal.md:64-66`). F14's first paragraph also named a retag, which this text doesn't cover: see F21.

## F15 [closed]: the requirement makes any answer about a run other than a 404 an error, which S1 and S5 contradict
Resolution: the requirement now ends "and any other failure to read a run than a 404" (`redline/changes/note-run/specs/ledger/delta.md:12-13`).

## F16 [closed]: S1–S3 rest on what GitHub gives for Redline's real push runs, and no premise states it
Resolution: P18 states what run 39848744114 gave on 2026-10-23: its URL as `html_url`, `push`, b41ea41, `main`, `.github/workflows/redline.yml`, and a job named `redline` concluded `success`. It cites the job's key, which has no `name:`, at `.github/workflows/redline.yml:20` and the push step's `--run-url` at `.github/workflows/redline.yml:63` (`redline/changes/note-run/specs/ledger/delta.md:94`).

## F17 [closed]: P16 says the tests read only `--note` of the push step; they read its token and its command too
Resolution: P16 now says "of the push step's options only `--note`" (`redline/changes/note-run/specs/ledger/delta.md:92`).

## F18 [closed]: S3's THEN makes H's break `unconfirmed` when the note is on a green's merge, which the ledger reads no break from
Resolution: S3's first WHEN now gives H's entry as `pass` or none beside the job's `failure` (`redline/changes/note-run/specs/ledger/delta.md:31`). Its last clause keeps the R merge's note on its own run with H's entry `pass`, reads the green's result as `unconfirmed`, and reads H's break as `pass` (`redline/changes/note-run/specs/ledger/delta.md:38`). Today's code reads that green's note as `pass` (`src/redline/ledger.py:52-53`), so the clause fails today, as a `[new]` one must.

## F19 [closed]: the proposal still says an entry for any other scenario makes the note `unconfirmed`, the rule F14 replaced
Resolution: the scope now says an entry for any other scenario counts for nothing, so it can't excuse a failed job (`redline/changes/note-run/proposal.md:26-28`). The requirement (`redline/changes/note-run/specs/ledger/delta.md:6-8`) and §4 (`docs/design.md:342-343`) say the same.

## F20 [closed]: S5 names the repository GitHub answered 404 for, but no premise says how Redline learns which repository `gh` asked
Resolution: S5 now says only that GitHub doesn't show the checkout's repository to the token, F20's third fix (`redline/changes/note-run/specs/ledger/delta.md:51`). The proposal says the same (`redline/changes/note-run/proposal.md:33-34`). §4 says it too, with the reason that `gh`'s 404 names no repository (`docs/design.md:358-359`).

## F21 [closed]: O-NOTE3 and the non-goal name a `hold` scenario dropped from the delta, not one retagged, which the ledger treats the same way
Resolution: §4 now says "a delta that drops or retags a `hold` scenario after R" (`docs/design.md:352-355`), O-NOTE3 says "a later step drops from the delta or retags" (`docs/design.md:2168-2170`), and the proposal's non-goal says the same (`redline/changes/note-run/proposal.md:64-66`).

## F22 [closed]: a note that checks out, says `result: fail` and has no entry for H: the requirement reads H's break `fail`, §4 reads it `unverified`, and S3 doesn't say which
Resolution: S3 now reads H's break `fail` from a `result: fail` note beside the job's `failure`, "whatever its entry says, or with none" (`redline/changes/note-run/specs/ledger/delta.md:34`). The requirement reads a break as `fail` from such a note, "entry or none" (`redline/changes/note-run/specs/ledger/delta.md:8-9`). §4 now gives `unverified` for a missing entry only from a note that checks out and says `result: pass` (`docs/design.md:301-305`), and says "entry or none" again at `docs/design.md:355-357`. Today a missing entry reads `unverified`, and an entry `pass` reads `pass`, whatever the note's `result:` says (`src/redline/ledger.py:54-56`). So the clause fails today, as a `[new]` one must.
