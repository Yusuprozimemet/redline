"""Tokens spent on a repository, per date, branch and model, from the agents' local session logs.

Claude Code keeps transcripts under ~/.claude/projects/<the repository's path>, subagents
included; Codex keeps rollouts under ~/.codex/sessions, each naming its working directory. Only
totals leave this module, never prompt or reply text. The logs live on this machine alone, and
Claude Code deletes transcripts after cleanupPeriodDays, so the counts cover what is still there.

A Claude reply repeats its usage on every content block it streamed and is complete only on the
last line, so replies are keyed by message and request id and the last line wins, across files
too, as a resumed session copies earlier replies. A Codex rollout records running session totals;
each step counts as the difference from the one before.

Each log's totals are saved to a JSON file (the dashboard keeps it in the git directory), so a new
server reads only logs that changed, and a log the tool has since deleted keeps its last totals.
"""

import glob
import json
import os
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

FIELDS = ("input", "cache_write", "cache_read", "output", "replies")
DATED = re.compile(r"-\d{8}$")
_files = {}  # path -> [[size, mtime], what it holds], so a refresh reads only changed logs
_read = set()  # logs read since the totals were last saved
VERSION = 1


def roots():
    home = Path.home()
    return {"claude": home / ".claude" / "projects", "codex": home / ".codex" / "sessions"}


def _day(stamp):
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone().date().isoformat()


def _cached(path, read):
    try:
        stat = os.stat(path)
    except OSError:
        return _files[path][1] if path in _files else None  # deleted since: keep what it held
    key = [stat.st_size, stat.st_mtime_ns]
    if path not in _files or _files[path][0] != key:
        with open(path, encoding="utf-8", errors="replace") as f:
            _files[path] = [key, read(f)]
        _read.add(path)
    return _files[path][1]


def _load(store):
    try:
        data = json.loads(Path(store).read_text(encoding="utf-8"))
        if data.get("version") == VERSION:
            for path, entry in data["files"].items():
                _files.setdefault(path, entry)
    except (OSError, ValueError, KeyError, AttributeError):
        pass  # no saved totals yet, or unreadable: read the logs


def _logs(root, pattern):
    """Logs under root now, plus saved ones the tool has since deleted."""
    root = os.path.abspath(root)
    found = set(glob.glob(os.path.join(root, pattern), recursive=True))
    return sorted(found | {p for p in _files if p.startswith(root + os.sep)})


def _claude(f):
    replies = {}
    for line in f:
        if '"assistant"' not in line:
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        msg = entry.get("message") if entry.get("type") == "assistant" else None
        usage = msg and msg.get("usage")
        model = msg and DATED.sub("", msg.get("model") or "")
        if usage and model.startswith("claude") and entry.get("timestamp"):
            replies[f'{msg.get("id")} {entry.get("requestId")}'] = [
                _day(entry["timestamp"]), entry.get("gitBranch") or None, model,
                [usage.get("input_tokens", 0), usage.get("cache_creation_input_tokens", 0),
                 usage.get("cache_read_input_tokens", 0), usage.get("output_tokens", 0), 1]]
    return replies


def _codex(f):
    cwd, branch, model, last, steps = None, None, "unknown", (0, 0, 0), []
    for line in f:
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        payload = entry.get("payload") or {}
        if entry.get("type") == "session_meta":
            cwd, branch = payload.get("cwd"), (payload.get("git") or {}).get("branch")
        elif entry.get("type") == "turn_context" and payload.get("model"):
            model = payload["model"]
        elif payload.get("type") == "thread_settings_applied":
            model = (payload.get("thread_settings") or {}).get("model") or model
        elif payload.get("type") == "token_count" and (payload.get("info") or {}).get("total_token_usage"):
            total = payload["info"]["total_token_usage"]
            now = (total.get("input_tokens", 0), total.get("cached_input_tokens", 0), total.get("output_tokens", 0))
            if now != last and entry.get("timestamp"):
                fresh, cached, output = (max(0, a - b) for a, b in zip(now, last))
                steps.append([_day(entry["timestamp"]), branch, model, [max(0, fresh - cached), 0, cached, output, 1]])
            last = now
    return [cwd, steps]


def usage(repo, where=None, store=None):
    """Rows of {tool, date, branch, model, input, cache_write, cache_read, output, replies}.
    store: the JSON file that keeps each log's totals between runs."""
    where = roots() if where is None else where
    if store:
        _load(store)
    repo = os.path.normcase(os.path.abspath(repo))
    totals = defaultdict(lambda: [0] * len(FIELDS))
    # Claude Code names a project's folder after its path, every non-alphanumeric turned into "-";
    # worktrees of the repository get folders that start the same way.
    prefix = re.sub(r"[^A-Za-z0-9]", "-", repo).lower()
    replies = {}
    claude = os.path.abspath(where.get("claude", ""))
    for path in _logs(claude, os.path.join("*", "**", "*.jsonl")):
        if os.path.relpath(path, claude).split(os.sep)[0].lower().startswith(prefix):
            replies.update(_cached(path, _claude) or {})
    for date, branch, model, counts in replies.values():
        row = totals["Claude Code", date, branch, model]
        row[:] = [a + b for a, b in zip(row, counts)]
    for path in _logs(where.get("codex", ""), os.path.join("**", "*.jsonl")):
        cwd, steps = _cached(path, _codex) or (None, [])
        if not cwd or os.path.normcase(os.path.abspath(cwd)) != repo:
            if steps:
                _files[path][1] = [cwd, []]  # another repository's session: keep only that it is
            continue
        for date, branch, model, counts in steps:
            row = totals["Codex", date, branch, model]
            row[:] = [a + b for a, b in zip(row, counts)]
    if store and _read:
        mine = (claude + os.sep, os.path.abspath(where.get("codex", "")) + os.sep)
        try:
            Path(store).write_text(json.dumps({"version": VERSION, "files": {
                p: e for p, e in _files.items() if p.startswith(mine)}}), encoding="utf-8")
            _read.clear()
        except OSError:
            pass  # saving is only for speed
    rows = [{"tool": tool, "date": date, "branch": branch, "model": model, **dict(zip(FIELDS, counts))}
            for (tool, date, branch, model), counts in totals.items()]
    return sorted(rows, key=lambda r: (r["date"], r["tool"], r["model"], r["branch"] or ""))
