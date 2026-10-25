# Local dashboard

Run `python -m redline.dashboard` from an installed checkout. The server binds only to
127.0.0.1 and serves packaged assets and a read-only JSON snapshot; no repository files,
commands, credentials or mutation endpoints are exposed. Refresh reloads local refs, not the
network. `--github` explicitly enables read-only GitHub enrichment through gh: the page renders
local data with GitHub's last saved answer, then asks GitHub again (/api/github) and updates. No deployment.

The dashboard follows main's first-parent history, including squash and direct commits. Step
completion comes from reachable Redline-Step trailers, not branch names or prose. Historical
metrics read each commit's tree, never today's tree. Blob analysis is reused during each build;
everything the dashboard saves is JSON in the repository's git directory, outside tracked files: the
history snapshot (redline-dashboard.json), each session log's token totals (redline-usage.json) and
GitHub's last answer (redline-github.json). Deleting them only costs the next load its speed. Cache versions and the main and
note ref identities invalidate stale results. Working-tree edits are not merged progress.

Charts: open/closed O-items, roadmap, change step lanes, spec/code identifier gap and seeded
chance band, gap deltas, coverage and Jaccard, retained/retired names, spec edit heatmap, work
distribution, cumulative churn, test/production churn ratio, daily commit activity, declared
versus merged steps, scenario evidence, CI history, claims, defects and recorded token usage. A merge scrubber and
replay select the historical snapshot for all detail views.

Identifier metrics are experimental lexical diagnostics, not semantic drift or correctness.
Use only names known at each snapshot; distinguish production-only coverage from all-source
coverage. Empty denominators are null. Chance bands are permutation percentiles, not measurement
confidence intervals. File moves count as delete/add churn. Historical specs moved from
docs/design.md to specs/; both locations count, with no inferred original build completion.

Ledgers are caches and their pass values are labelled recorded, never independently verified.
CI notes are similarly unconfirmed offline; GitHub enrichment checks the note run's repository,
commit, event, workflow, branch and redline job outcome using Redline's existing ci_result seam.
Fetching notes is an explicit shell action, not a dashboard refresh. No detailed scenario execution
is invented from suite success.

Token usage per model, date and branch comes from the session logs on this machine: Claude Code
transcripts under ~/.claude/projects/<repository path> (subagents and worktrees included) and Codex
rollouts under ~/.codex/sessions whose working directory is the repository (redline/usage.py).
Only totals are served, never prompt or reply text; they are read again on each refresh, outside
the history cache, with unchanged log files reused from redline-usage.json, which also keeps the
totals of logs the tools have since deleted. A Claude reply counts once, from its last
streamed line, keyed by message and request id; a Codex step counts as the difference between its
running session totals. Logs from other machines, or deleted after cleanupPeriodDays, are absent.
`--no-usage` skips them.

Commit messages that record an agent run as "N tokens, M tool calls" (the audit and relabel
commits do) are shown separately. Every reachable commit is read, so runs on PR branches count at the
merge that brings them to the main line; the subject's "<change> <step>:" prefix attributes them,
and "audit" or "relabel" in it gives the kind. Sessions with no recorded count are not estimated.

Test files are those matching a runner's test-file globs (as check-track reads them) or under
tests/; other source is production. The source box warns when the ref is behind origin/main.

Verification uses synthetic histories with renamed specs, deleted files, side-branch trailers,
missing notes, malformed YAML, cache invalidation and malicious display text, plus local HTTP
route/host checks and the existing suite. Oversize is explicitly authorized by the maintainer for
this one dashboard implementation; it does not change Redline's 400-line gate or approval rules.
