"""Read-only localhost dashboard. Run: python -m redline.dashboard [--github]."""

import argparse
import hashlib
import json
import math
import random
import re
import subprocess
import threading
from collections import Counter
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from urllib.parse import urlsplit

import yaml

from redline.lines import is_generated
from redline.links import HEADING
from redline.order import contents, git
from redline.runner import markers, runner_for
from redline.start import scan
from redline.track import TESTS
from redline.usage import usage

VERSION = 3
KINDS = ("spec", "context", "production", "tests", "tooling")
CLAIMS = ("Oversized", "Redline-Departure", "Redline-Track", "Redline-Rigor", "Redline-Manual", "Redline-Relabel")
ISSUE = re.compile(r"^- (O-[\w-]+) \[([^\]]+)\]: (.*)", re.M)
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]{3,}")
TOKENS = re.compile(r"(\d[\d,]*) tokens,? (?:and )?(\d+) tool calls?")
OWNER = re.compile(r"^([\w.-]+) (\w+):")
SOURCE = {".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".sh", ".yml", ".yaml", ".toml"}


def checked(repo, *args):
    result = git(repo, *args)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout


def category(path):
    if path.startswith(("docs/dashboard", "src/redline/dashboard_assets")) or path.endswith("dashboard.py"):
        return "tooling"
    if path == "plan.md" or path.startswith(("specs/", "redline/specs/")) or "/specs/" in path or path == "docs/design.md":
        return "spec"
    if path.endswith(".md"):
        return "context"
    if path.startswith("tests/") or runner_for(path) and is_generated(path, list(TESTS)):
        return "tests"
    if path.startswith(("scripts/", ".github/")):
        return "tooling"
    return "production"


def is_spec(path):
    return path.endswith(".md") and category(path) == "spec"


def names(text, spec=False):
    if spec:
        text = " ".join(re.findall(r"`([^`\n]+)`", text))
    else:
        text = "\n".join(line for line in text.splitlines()
                         if not line.lstrip().startswith(("#", "//", "/*", "*", "<!--")))
    return Counter(IDENT.findall(text))


def overlap(spec, code, known):
    a, b = {n for n in known if spec.get(n)}, {n for n in known if code.get(n)}
    return (len(a & b) / len(a) if a else None,
            len(a & b) / len(a | b) if a | b else None, len(b - a))


def angle(a, b):
    norm = math.sqrt(sum(x*x for x in a) * sum(x*x for x in b))
    return math.degrees(math.acos(max(-1, min(1, sum(x*y for x, y in zip(a, b)) / norm)))) if norm else None


def gap_metrics(spec, code, known):
    vocabulary = sorted(known)
    a = [math.log1p(spec.get(n, 0)) for n in vocabulary]
    b = [math.log1p(code.get(n, 0)) for n in vocabulary]
    gap = angle(a, b)
    if gap is None:
        return None, None, None
    rng, samples = random.Random(0), []
    shuffled = sorted(b)
    for _ in range(200):
        rng.shuffle(shuffled)
        samples.append(angle(a, shuffled))
    samples.sort()
    return gap, sum(samples)/len(samples), [samples[4], samples[194]]


def histories(repo, ref):
    """One raw log builds every first-parent tree; one batch reads unique text blobs."""
    log = checked(repo, "log", "--first-parent", "--reverse", "--raw", "-z", "--root", "--no-renames",
                  "--no-abbrev", "--diff-merges=first-parent", "--format=%x01%H%x1f%cI%x1f%s", ref)
    snapshots, tree = [], {}
    for entry in log.split("\x01")[1:]:
        header, *records = [p for p in entry.split("\0") if p not in ("", "\n")]
        sha, date, title = header.strip().split("\x1f", 2)
        tree = dict(tree)
        for meta, path in zip(records[::2], records[1::2]):
            _, mode, _, blob, _ = meta.split()
            tree.pop(path, None)
            if mode not in ("000000", "160000"):
                tree[path] = blob
        snapshots.append({"sha": sha, "date": date[:10], "title": title, "tree": tree})
    wanted = {blob for row in snapshots for path, blob in row["tree"].items()
              if Path(path).suffix in SOURCE | {".md"}}
    return snapshots, contents(repo, sorted(wanted))


def step_history(repo, ref):
    log = checked(repo, "log", "--reverse", "--topo-order",
                  "--format=%H%x1f%P%x1f%(trailers:key=Redline-Step,valueonly,separator=|)", ref)
    states = {}
    for line in log.splitlines():
        if not line.strip():
            continue
        sha, parents, trailers = line.split("\x1f", 2)
        states[sha] = set().union(*(states[p] for p in parents.split()))
        states[sha].update(t.strip() for t in trailers.split("|") if t.strip())
    return states


def token_history(repo, ref):
    """Agent runs recorded as "N tokens, M tool calls" in any reachable commit message."""
    log = checked(repo, "log", "--reverse", "--topo-order", "--format=%x01%H%x1f%P%x1f%B", ref)
    runs, states = {}, {}
    for entry in log.split("\x01")[1:]:
        sha, parents, body = entry.split("\x1f", 2)
        states[sha] = set().union(*(states[p] for p in parents.split()))
        subject = body.strip().split("\n", 1)[0]
        owner = OWNER.match(subject)
        for i, m in enumerate(TOKENS.finditer(" ".join(body.split()))):
            kind = "relabel" if "relabel" in subject.lower() else "audit" if "audit" in subject.lower() else "other"
            runs[f"{sha}:{i}"] = {"sha": sha, "subject": subject, "kind": kind,
                                  "change": owner[1] if owner else None, "step": owner[2] if owner else None,
                                  "tokens": int(m[1].replace(",", "")), "calls": int(m[2])}
            states[sha].add(f"{sha}:{i}")
    return states, runs


def churn_history(repo, ref):
    log = checked(repo, "log", "--first-parent", "--reverse", "--numstat", "--root", "--no-renames",
                  "--diff-merges=first-parent", "--format=%x01%H", ref)
    output = {}
    for block in log.split("\x01")[1:]:
        sha, *lines = block.strip().splitlines()
        output[sha] = []
        for line in lines:
            parts = line.split("\t", 2)
            if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
                output[sha].append((parts[2], int(parts[0]) + int(parts[1])))
    return output


def read_yaml(text, label, warnings):
    try:
        data = yaml.safe_load(text)
        if data is not None and not isinstance(data, dict):
            raise ValueError("expected a mapping")
        return data or {}
    except (yaml.YAMLError, ValueError) as error:
        warnings.append(f"{label}: invalid YAML ({str(error).splitlines()[0]})")
        return {}


def notes(repo):
    listing = git(repo, "notes", "--ref=redline-ci", "list")
    pairs = [line.split() for line in listing.stdout.splitlines() if len(line.split()) == 2]
    blobs = contents(repo, [p[0] for p in pairs]) if pairs else {}
    return {commit: blobs[blob] for blob, commit in pairs}


def note_summary(text, warnings):
    if text is None:
        return {"status": "missing", "confirmed": False}
    data = read_yaml(text, "CI note", warnings)
    return {"status": "recorded" if data.get("result") in ("pass", "fail") else "malformed",
            "result": data.get("result"), "run": data.get("run"), "confirmed": False,
            "claims": data.get("claims") if isinstance(data.get("claims"), list) else [],
            "outcomes": "recorded" if isinstance(data.get("outcomes"), dict) else "unavailable"}


def snapshot_details(texts, steps, warnings):
    changes, evidence, defects, declarations = [], [], [], {}
    for path, text in texts.items():
        match = re.fullmatch(r"redline/changes/([^/]+)/steps.md", path)
        if not match:
            continue
        change = match[1]
        parsed, bad, _ = scan(text)
        warnings.extend(f"{change}: {b}" for b in bad)
        done = [s.name for s in parsed if f"{change}/{s.name}" in steps]
        item_rows = [{"id": m[1], "step": m[2], "text": m[3], "closed": m[2] in done}
                     for m in re.finditer(r"^- (\S+) \[([^\]]+)\]: (.*)", text, re.M)]
        proposal = texts.get(f"redline/changes/{change}/proposal.md", "")
        level = re.search(r"^Rigor: (\w+)", proposal, re.M)
        changes.append({"name": change, "steps": [{"name": s.name, "goal": s.goal} for s in parsed],
                        "done": done, "items": item_rows, "rigor": level[1] if level else "default",
                        "next": next((s.name for s in parsed if s.name not in done), None)})
        closed = "C" in done
        for delta, source in texts.items():
            if delta.startswith(f"redline/changes/{change}/specs/") and not closed:
                for line in source.splitlines():
                    if m := HEADING.match(line):
                        declarations[m[1]] = m[2]
        ledger = read_yaml(texts.get(f"redline/changes/{change}/ledger.yaml", ""), change + " ledger", warnings)
        scenarios = ledger.get("scenarios", {})
        if not isinstance(scenarios, dict):
            warnings.append(f"{change} ledger: scenarios is not a mapping")
            scenarios = {}
        for sid, entries in scenarios.items():
            entries = entries if isinstance(entries, dict) else {}
            cells = {key: entries.get(key) if isinstance(entries.get(key), dict) else None
                     for key in ("red", "green", "break")}
            recorded = [v.get("result") for v in cells.values() if v]
            state = ("recorded fail" if "fail" in recorded else "recorded pass"
                     if recorded and all(v == "pass" for v in recorded) else "unconfirmed" if recorded else "missing")
            evidence.append({"change": change, "scenario": str(sid), "state": state, **cells})
        log = texts.get(f"redline/changes/{change}/defects.md", "")
        for block in re.split(r"(?=^## D\d+:)", log, flags=re.M):
            title = re.match(r"## (D\d+): (.*)", block)
            if title:
                cause = re.search(r"^Cause: (.*)", block, re.M)
                found = re.findall(r"^Found-by: (.*)", block, re.M)
                defects.append({"change": change, "id": title[1], "title": title[2],
                                "cause": cause[1] if cause else "unclassified", "found": found})
    for path, text in texts.items():
        if path.startswith("redline/specs/"):
            for line in text.splitlines():
                if m := HEADING.match(line):
                    declarations.setdefault(m[1], m[2])
    lock = read_yaml(texts.get("redline/contracts/lock.yaml", ""), "contract lock", warnings)
    locked = sum(len(tests) for change in lock.values() if isinstance(change, dict)
                 for tests in change.values() if isinstance(tests, dict))
    return changes, evidence, defects, declarations, locked


def saved(repo, name):
    """A JSON file the dashboard keeps in the git directory, outside tracked files."""
    return Path(checked(repo, "rev-parse", "--path-format=absolute", "--git-path", name).strip())


def collect(repo: Path, ref="main", github=False, logs=None):
    """github: True asks GitHub now, "saved" attaches the last answer; logs: where usage reads
    session logs (default: this user's), or False to skip them."""
    repo = Path(repo).resolve()
    head = checked(repo, "rev-parse", "--verify", f"{ref}^{{commit}}").strip()
    note_ref = git(repo, "rev-parse", "--verify", "refs/notes/redline-ci").stdout.strip()
    key = hashlib.sha256(f"{VERSION}:{head}:{note_ref}".encode()).hexdigest()
    cache = saved(repo, "redline-dashboard.json")
    cached = None
    try:
        cached = json.loads(cache.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    if cached and cached.get("key") == key:
        data = cached["data"]
    else:
        snapshots, blobs = histories(repo, head)
        completed, churn, recorded_notes = step_history(repo, head), churn_history(repo, head), notes(repo)
        spent, token_runs = token_history(repo, head)
        analysis, marker_cache, rows, known, ever, cumulative = {}, {}, [], set(), set(), Counter()
        for snap in snapshots:
            warnings, spec, code, production, texts, linked = [], Counter(), Counter(), Counter(), {}, set()
            for path, blob in snap.pop("tree").items():
                if blob not in blobs:
                    continue
                text = blobs[blob]
                if path.endswith(".md") or path.startswith("redline/") and path.endswith(".yaml"):
                    texts[path] = text
                spec_file, kind = is_spec(path), category(path)
                if spec_file or Path(path).suffix in SOURCE and kind != "tooling":
                    if (blob, spec_file) not in analysis:
                        analysis[blob, spec_file] = names(text, spec_file)
                    counts = analysis[blob, spec_file]
                    (spec if spec_file else code).update(counts)
                    if not spec_file and kind == "production":
                        production.update(counts)
                if runner := runner_for(path):
                    try:
                        if (blob, runner.name) not in marker_cache:
                            marker_cache[blob, runner.name] = markers(runner, path, text)
                        linked.update(m.sid for m in marker_cache[blob, runner.name])
                    except RuntimeError as error:
                        warnings.append(str(error))
            known.update(spec)
            coverage, jaccard, kept = overlap(spec, code, known)
            prod_coverage, _, _ = overlap(spec, production, known)
            gap, chance, band = gap_metrics(spec, code, known)
            issue_source = texts.get("specs/12-open-problems.md", texts.get("docs/design.md", ""))
            issues = []
            for match in ISSUE.finditer(issue_source):
                owner = match[2]
                build = re.search(r"\bbuild (\d+)", owner)
                issues.append({"id": match[1], "closed": owner.startswith("closed"),
                               "build": int(build[1]) if build else None, "owner": owner, "text": match[3]})
            changes, evidence, defects, declared, locked = snapshot_details(texts, completed[snap["sha"]], warnings)
            work, edits = dict.fromkeys(KINDS, 0), {}
            for path, count in churn.get(snap["sha"], []):
                work[category(path)] += count
                if is_spec(path):
                    edits[path] = count
            cumulative.update(work)
            new_steps = completed[snap["sha"]] - (completed[rows[-1]["sha"]] if rows else set())
            new_runs = spent[snap["sha"]] - (spent[rows[-1]["sha"]] if rows else set())
            pr = re.search(r"(?:pull request #|\(#)(\d+)", snap["title"])
            row = {**snap, "pr": int(pr[1]) if pr else None, "steps": sorted(new_steps),
                   "kind": "close" if any(s.endswith("/C") for s in new_steps) else
                           "spec" if any(s.endswith("/S") for s in new_steps) else
                           "code" if new_steps else "other",
                   "issues": {"closed": sum(i["closed"] for i in issues), "open": sum(not i["closed"] for i in issues)},
                   "issue_list": issues, "coverage": coverage, "production_coverage": prod_coverage,
                   "jaccard": jaccard, "gap": gap, "chance": chance, "band": band,
                   "names_kept": kept, "names_retired": len((set(spec) - set(code)) & ever),
                   "work": work, "cumulative": dict(cumulative), "spec_edits": edits,
                   "test_ratio": cumulative["tests"] / cumulative["production"] if cumulative["production"] else None,
                   "tokens": [token_runs[k] for k in sorted(new_runs)], "changes": changes, "evidence": evidence, "defects": defects, "locked": locked,
                   "links": {"declared": len(declared), "linked": len(set(declared) & linked),
                             "manual": sum(k == "manual" for k in declared.values()),
                             "unlinked": sorted(s for s, kind in declared.items() if kind != "manual" and s not in linked),
                             "unknown": sorted(linked - set(declared))},
                   "note": note_summary(recorded_notes.get(snap["sha"]), warnings), "warnings": warnings}
            rows.append(row)
            ever.update(code)
        data = {"repo": repo.name, "ref": ref, "head": head,
                "generated": datetime.now(timezone.utc).isoformat(), "rows": rows,
                "method": {"chance_draws": 200, "cache_version": VERSION}, "github": {"status": "disabled"}}
        try:
            cache.write_text(json.dumps({"key": key, "data": data}, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass  # read-only checkout still works; caching is optional
    data["ref"] = ref
    behind = git(repo, "rev-list", "--count", f"{head}..origin/main")
    data["behind"] = int(behind.stdout) if not behind.returncode and ref != "origin/main" else 0
    data["usage"] = {"status": "disabled", "rows": []}
    if logs is not False:
        try:
            data["usage"] = {"status": "read", "rows": usage(repo, logs, saved(repo, "redline-usage.json"))}
        except (OSError, ValueError) as error:
            data["usage"] = {"status": f"unreadable: {error}", "rows": []}
    if github == "saved":
        try:
            last = json.loads(saved(repo, "redline-github.json").read_text(encoding="utf-8"))
            data["github"] = {**last["github"], "saved": True}
            if last["sha"] == data["rows"][-1]["sha"]:
                data["rows"][-1]["note"] = last["note"]
        except (OSError, ValueError, KeyError, TypeError):
            data["github"] = {"status": "enabled", "saved": True, "runs": [], "open_prs": []}
    elif github:
        enrich(repo, data)
    return data


def enrich(repo, data):
    """Bounded network enrichment; offline recorded passes never become confirmed."""
    from redline.ledger import ci_result
    from redline.pr import GitHub
    data["github"] = {"status": "enabled", "checked": datetime.now(timezone.utc).isoformat(), "runs": [], "open_prs": []}
    for resource, args in (("runs", ["run", "list", "--limit", "100", "--json", "databaseId,headSha,headBranch,conclusion,status,event,url,displayTitle"]),
                           ("open_prs", ["pr", "list", "--state", "open", "--limit", "100", "--json", "number,title,url,headRefName"])):
        try:
            result = subprocess.run(["gh", *args], cwd=repo, capture_output=True, encoding="utf-8", timeout=30)
            if result.returncode:
                raise RuntimeError(result.stderr.strip())
            data["github"][resource] = json.loads(result.stdout)
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
            data["github"]["status"] = "partial"
            data["github"].setdefault("warnings", []).append(f"{resource}: {error}")
    # Check the latest note only: Redline's seam validates the run, not just a green run-list row.
    row = data["rows"][-1]
    if row["note"]["status"] == "recorded":
        try:
            result = ci_result(repo, row["sha"], GitHub(repo))
            row["note"]["confirmed"] = result in ("pass", "fail")
            row["note"]["confirmation"] = result
        except (OSError, RuntimeError) as error:
            data["github"]["warnings"] = data["github"].get("warnings", []) + [str(error)]
    try:
        saved(repo, "redline-github.json").write_text(json.dumps(
            {"sha": row["sha"], "note": row["note"], "github": data["github"]}, ensure_ascii=False), encoding="utf-8")
    except (OSError, RuntimeError):
        pass  # the page still shows this answer; only the next start loses it


def make_server(repo, port=8765, ref="main", github=False, logs=None):
    lock, asking = threading.Lock(), threading.Lock()  # GitHub's slow answer never holds up local data

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.headers.get("Host") not in (f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"):
                self.send_error(403, "Loopback host required")
                return
            origin = self.headers.get("Origin")
            if origin and origin not in (f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"):
                self.send_error(403, "Same-origin requests only")
                return
            path = urlsplit(self.path).path
            try:
                if path == "/api/data":
                    with lock:
                        payload = json.dumps(collect(repo, ref, github and "saved", logs), ensure_ascii=False).encode("utf-8")
                    mime = "application/json; charset=utf-8"
                elif path == "/api/github" and github:
                    with asking:
                        data = collect(repo, ref, True, False)
                    payload = json.dumps({"github": data["github"], "sha": data["rows"][-1]["sha"],
                                          "note": data["rows"][-1]["note"]}, ensure_ascii=False).encode("utf-8")
                    mime = "application/json; charset=utf-8"
                elif path in ("/", "/dashboard.js", "/dashboard.css"):
                    asset = "index.html" if path == "/" else path[1:]
                    payload = files("redline").joinpath("dashboard_assets", asset).read_bytes()
                    mime = {"index.html": "text/html", "dashboard.js": "text/javascript", "dashboard.css": "text/css"}[asset] + "; charset=utf-8"
                else:
                    self.send_error(404)
                    return
            except (RuntimeError, OSError, ValueError) as error:
                self.send_error(500, str(error))
                return
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(payload)

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--ref", default="main", help="local merged ref to report (default: main)")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--github", action="store_true", help="read GitHub runs/PRs and confirm the latest CI note")
    parser.add_argument("--no-usage", action="store_true", help="skip token usage from local Claude Code and Codex logs")
    parser.add_argument("--export", type=Path, help="write a JSON snapshot instead of serving")
    args = parser.parse_args(argv)
    try:
        if args.export:
            args.export.write_text(json.dumps(collect(args.repo, args.ref, args.github, False if args.no_usage else None), ensure_ascii=False), encoding="utf-8")
            print(args.export.resolve())
            return 0
        server = make_server(args.repo, args.port, args.ref, args.github, False if args.no_usage else None)
        print(f"Redline dashboard: http://127.0.0.1:{server.server_port} | ref {args.ref}", flush=True)
        print("Ctrl+C to stop. Refresh reads local refs; it does not fetch or run tests.", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
    except (OSError, RuntimeError, ValueError) as error:
        print(f"Dashboard: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
