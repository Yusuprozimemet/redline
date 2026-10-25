# Audit availability and S blocker

Fable at max effort returned a usage-credit error before auditing (zero tokens/tools).
The permitted fallback, fresh read-only Opus at max, completed round 1 against 304da84.
Its complete reply is preserved unedited in audit.md. Runtime modelUsage identifies
claude-opus-4-8; the reply incorrectly reports claude-opus-4-1 and includes a preamble.
A successful independent re-audit must correct that header/format as well as resolve F1.
Usage: 1,754 input + 73,146 cache creation + 299,194 cache read + 40,495 output tokens.
The JSON result exposes 24 CLI turns, not a tool-call count; no count is inferred.

F1's producer/writer citation was corrected in f62766e. All 13 premise citations resolve.
Round 2 received the unchanged generated brief for f62766e, Since 304da84, through a fresh
claude-opus-4-8 session, max effort, tools Read/Grep/Glob only. After 12 tool calls / 13 turns,
the API returned HTTP 429: weekly usage limit, resetting 27 October 2026 at 22:00 Europe/Amsterdam.
Usage: 1,742 input + 40,579 cache creation + 49,103 cache read + 24,484 output tokens.
It returned no completed audit verdict; audit.md remains round 1 with F1 open. A failed
attempt is not an independent finding closure, waiver, or completed second audit round.

Do not merge or treat S as complete. Resume the required round-2 independent audit when
Fable/Opus is available, write its whole reply unedited, then rerun S gates and make the PR ready.
No self-audit, alternative model, invented approval or gate relaxation substitutes for it.
Recovery remains unspecified in code and undispatched; O-NOTE4 is open and O-NOTE3 stays separate.
