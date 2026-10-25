I've completed my audit. Let me verify my findings are sound by reviewing what I've established:

**Model gate:** I run on a Claude Opus model, which is a permitted auditor — proceeding.

**Premises — all tested against the code:**
- Ledger P1 (`ledger.py:44-68`): confirmation requires `event=push`/`head_sha=commit` (lines 61-64); `failed` counts only `counted` breaks (line 58). **True.**
- Ledger P2 (`pr.py:92-107`): single jobs page (line 104, no paginate), lossy name→conclusion map (line 105), cached by run id (line 102). **True.**
- Ledger P3 (`test_note_run.py:95-200`, `test_github.py:54-58`): CRAFTED event/identity + DISAGREE fixtures + real-API `push_run` test. **True.**
- CI P2 (`ci.py:168-206`): `--note`→`to` writes file and returns before git writes (lines 198-200); records result/run/break/claims/outcomes; CLI exposes `--note`/`--run-url` (`cli.py:110-112`, `479`). **True.**
- CI P3 (`test_ci.py:408-466`, `test_install_workflow.py:91-107,149`): workflow git-script harness with races/large files; `core()` own/template comparison. **True.**
- CI P4 (`approval.py:26`, `pr.py:149-150`): `MAINTAINER=("admin","maintain")`; collaborator permission API. **True.**
- CI P1: push/PR-only triggers (`redline.yml:4-9`) **true**; but the **producer** citation is wrong (finding below).

**Tags:** All `[new]` recovery scenarios fail today (no `recovery.py`, no dispatch/recovery jobs exist). `LEDGER.RUN.S2 [new]` justified (recovery-accept clause fails today though rejections already pass). `H1 [hold]` passes today. No `[manual]` scenarios to challenge; S2/S6 are automatable with fakes/YAML parsing, correctly `[new]`.

**THEN clauses:** all observable. **Rigor:** `critical` correctly declared (authorization + evidence integrity + dispatch API); cannot be lowered. **Cross-refs:** base `LEDGER.RUN.S1/S3/S5/S6` exist and the cited semantics (exit 2, check-close) match. **Ownership:** all 8 delta scenarios owned across R/G1/G2/G3.

# Audit: note-recover
Model: claude-opus-4-1
Round: 1
Audited: 304da840d44c377fa70c4a883346ec6148bb0dfc

## F1 [open]: ci/delta.md P1 miscites the "read-only producer"; it is the `redline` job, outside the cited `redline.yml:129-181`
P1 claims the current workflow "has separate read-only producer and file writer" and cites `.github/workflows/redline.yml:129-181`. That range holds only the file writer — the `note` job (`redline.yml:127-149`, the sole `contents: write` job) — and the read-only `runners` job (`redline.yml:151-181`), which produces no note. The read-only producer that runs `redline ci push ... --note "$RUNNER_TEMP/note"` is the `redline` job (`redline.yml:55-125`), specifically its push step at `redline.yml:108-110`, with read-only permissions at `redline.yml:59-63`; its artifact upload is at `redline.yml:118-125`. The architectural claim is true, but the "read-only producer" is not within the cited lines (the range begins at line 129, after the producer). Cite `redline.yml:108-110` (or the `redline` job, 55-125) for the producer.