"""The local dashboard reports snapshots; it never upgrades recorded data to proof."""
import json
import subprocess
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def history(tmp_path):
    git(tmp_path, "init", "-b", "main")
    git(tmp_path, "config", "user.email", "dashboard@example.test")
    git(tmp_path, "config", "user.name", "Dashboard test")

    def commit(files, message):
        for name, text in files.items():
            path = tmp_path / name
            path.parent.mkdir(parents=True, exist_ok=True)
            if text is None:
                path.unlink()
            else:
                path.write_text(text, encoding="utf-8")
        git(tmp_path, "add", ".")
        git(tmp_path, "commit", "-m", message)
        return git(tmp_path, "rev-parse", "HEAD")

    first = commit({"docs/design.md": "`alpha_name`\n- O-A [build 8]: pending\n",
                    "src/app.py": "alpha_name = 1\n",
                    "redline/changes/demo/steps.md": "## S: Specify\n## R: Red\n## G1: Green\n## C: Close\n",
                    "redline/changes/demo/ledger.yaml": "scenarios:\n  DEMO.S1:\n    red: null\n    green: null\n    break: null\n"}, "initial\n\nRedline-Step: demo/S")
    git(tmp_path, "switch", "-c", "work")
    commit({"src/app.py": "alpha_name = 2\n"}, "red\n\nRedline-Step: demo/R")
    git(tmp_path, "switch", "main")
    git(tmp_path, "merge", "--no-ff", "work", "-m", "Merge <script>alert(1)</script>")
    last = commit({"docs/design.md": None,
                   "specs/12-open-problems.md": "`alpha_name` `future_name`\n- O-A [closed, build 8]: fixed\n",
                   "src/app.py": "future_name = 3\n"}, "move design")
    return tmp_path, first, last, commit


def test_historical_metrics_and_reachable_steps(history):
    from redline.dashboard import collect
    repo, first, last, _ = history
    data = collect(repo)
    assert [r["sha"] for r in data["rows"]][::2] == [first, last]
    assert data["rows"][0]["coverage"] == 1
    assert data["rows"][-1]["coverage"] == .5
    assert data["rows"][0]["issues"] == {"closed": 0, "open": 1}
    assert data["rows"][-1]["issues"] == {"closed": 1, "open": 0}
    assert data["rows"][0]["changes"][0]["done"] == ["S"]
    assert data["rows"][-1]["changes"][0]["done"] == ["S", "R"]
    assert data["rows"][-1]["names_retired"] == 1
    assert data["rows"][-1]["note"]["status"] == "missing"
    assert "specs/12-open-problems.md" in data["rows"][-1]["spec_edits"]
    assert data["rows"][-1]["evidence"][0]["state"] == "missing"


def test_cache_notes_and_malformed_data_do_not_invent_passes(history):
    from redline.dashboard import collect
    repo, _, last, commit = history
    before = collect(repo)
    git(repo, "notes", "--ref=redline-ci", "add", "-m", "result: pass\nrun: https://example.test/untrusted", last)
    after = collect(repo)
    assert before["rows"][-1]["note"]["status"] == "missing"
    assert after["rows"][-1]["note"]["status"] == "recorded"
    assert after["rows"][-1]["note"]["confirmed"] is False
    commit({"redline/changes/demo/ledger.yaml": "scenarios: [broken"}, "malformed cache")
    assert collect(repo)["rows"][-1]["warnings"]
    assert collect(repo)["rows"][-1]["evidence"] == []


def test_server_only_exposes_assets_and_data(history):
    from redline.dashboard import make_server
    repo, *_ = history
    server = make_server(repo, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with urlopen(base + "/api/data") as response:
            assert json.load(response)["rows"]
        with urlopen(base + "/") as response:
            assert "Redline" in response.read().decode()
        for path in ("/.git/config", "/../pyproject.toml", "/api/run", "/api/github"):
            with pytest.raises(HTTPError) as error:
                urlopen(base + path)
            assert error.value.code == 404
        with pytest.raises(HTTPError) as error:
            urlopen(Request(base + "/api/data", headers={"Host": "evil.example"}))
        assert error.value.code == 403
    finally:
        server.shutdown()
        server.server_close()


def test_empty_metrics_are_unknown():
    from redline.dashboard import overlap
    assert overlap({}, {}, set()) == (None, None, 0)


def test_items_with_change_owners_are_not_silently_dropped(history):
    from redline.dashboard import collect
    repo, _, _, commit = history
    commit({"specs/12-open-problems.md": "- O-CUSTOM [owner: demo/R, maintainer]: pending\n"}, "change owner")
    row = collect(repo)["rows"][-1]
    assert row["issues"] == {"closed": 0, "open": 1}
    assert row["issue_list"][0]["build"] is None


def test_installed_assets_have_no_external_dependencies():
    from importlib.resources import files
    root = files("redline").joinpath("dashboard_assets")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    assert 'src="/dashboard.js"' in html
    assert 'href="/dashboard.css"' in html
    assert "https://" not in html


def test_recorded_token_runs_count_at_the_merge_that_brings_them(history):
    from redline.dashboard import collect
    repo, _, _, commit = history
    git(repo, "switch", "-c", "audit")
    commit({"redline/changes/demo/audit.md": "x\n"}, "demo S: the first audit\n\nThe auditor ran: 215,227 tokens, 47 tool calls.")
    commit({"redline/changes/demo/relabel.yaml": "x: 1\n"}, "demo C: relabel.yaml\n\nIt used 24,167 tokens and 1 tool call.")
    git(repo, "switch", "main")
    commit({"src/other.py": "x = 1\n"}, "no record, 12 tokens")
    git(repo, "merge", "--no-ff", "audit", "-m", "Merge audit")
    rows = collect(repo)["rows"]
    assert all(not r["tokens"] for r in rows[:-1])
    assert sorted((t["change"], t["step"], t["kind"], t["tokens"], t["calls"]) for t in rows[-1]["tokens"]) == [
        ("demo", "C", "relabel", 24167, 1), ("demo", "S", "audit", 215227, 47)]


def test_source_files_are_production_not_tests():
    from redline.dashboard import category
    assert category("src/redline/pr.py") == "production"
    assert category("tests/test_pr.py") == "tests"
    assert category("web/app.test.js") == "tests"
    assert category("web/app.js") == "production"


def test_usage_counts_each_reply_once_per_model_from_both_tools(tmp_path_factory):
    import re
    from redline.usage import usage
    import redline.usage as usage_module
    tmp_path = tmp_path_factory.mktemp("u")  # the log folder repeats the repository's path: stay under MAX_PATH
    repo = tmp_path / "repo"
    repo.mkdir()
    claude = tmp_path / "claude" / re.sub(r"[^A-Za-z0-9]", "-", str(repo.resolve()))
    (claude / "subagents").mkdir(parents=True)
    reply = lambda out, model="claude-opus-5-5-20261001": json.dumps({
        "type": "assistant", "requestId": "r1", "timestamp": "2026-10-20T12:00:00Z", "gitBranch": "demo-S",
        "message": {"id": "m1", "model": model, "usage": {"input_tokens": 5, "cache_creation_input_tokens": 10,
                                                          "cache_read_input_tokens": 100, "output_tokens": out}}})
    (claude / "a.jsonl").write_text(reply(1) + "\n" + reply(40) + "\n{broken\n", encoding="utf-8")
    (claude / "subagents" / "b.jsonl").write_text(reply(40), encoding="utf-8")  # a resumed copy: once
    (tmp_path / "claude" / "other-repo").mkdir()
    (tmp_path / "claude" / "other-repo" / "c.jsonl").write_text(reply(999), encoding="utf-8")
    codex = tmp_path / "codex" / "2026" / "10"
    codex.mkdir(parents=True)
    count = lambda i, c, o: json.dumps({"timestamp": "2026-10-21T09:00:00Z", "type": "event_msg", "payload": {
        "type": "token_count", "info": {"total_token_usage": {"input_tokens": i, "cached_input_tokens": c, "output_tokens": o}}}})
    lines = [json.dumps({"type": "session_meta", "payload": {"cwd": str(repo), "git": {"branch": "demo-S"}}}),
             json.dumps({"type": "turn_context", "payload": {"model": "gpt-6.1-sol"}}),
             count(100, 80, 7), count(100, 80, 7), count(250, 200, 10)]
    (codex / "rollout.jsonl").write_text("\n".join(lines), encoding="utf-8")
    (codex / "elsewhere.jsonl").write_text(lines[0].replace("repo", "other") + "\n" + count(9, 0, 9), encoding="utf-8")
    where, store = {"claude": tmp_path / "claude", "codex": tmp_path / "codex"}, tmp_path / "usage.json"
    rows = usage(repo, where, store)
    assert json.loads(store.read_text(encoding="utf-8"))["files"][str(codex / "elsewhere.jsonl")][1][1] == []
    (claude / "a.jsonl").unlink()  # Claude Code's cleanup: the saved totals stay
    usage_module._files.clear()
    assert usage(repo, where, store) == rows
    assert [(r["tool"], r["model"], r["branch"], r["input"], r["cache_write"], r["cache_read"], r["output"], r["replies"])
            for r in rows] == [("Claude Code", "claude-opus-5-5", "demo-S", 5, 10, 100, 40, 1),
                               ("Codex", "gpt-6.1-sol", "demo-S", 50, 0, 200, 10, 2)]


def test_saved_github_answer_is_shown_until_a_fresh_one(history):
    from redline.dashboard import collect, saved
    repo, _, last, _ = history
    saved(repo, "redline-github.json").write_text(json.dumps({"sha": last, "note": {"status": "recorded", "confirmed": True},
                                                              "github": {"status": "enabled", "checked": "then", "runs": []}}))
    data = collect(repo, github="saved", logs=False)
    assert data["github"]["saved"] and data["github"]["checked"] == "then"
    assert data["rows"][-1]["note"]["confirmed"] is True
    assert collect(repo, logs=False)["github"]["status"] == "disabled"
