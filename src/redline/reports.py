"""Invocation-local discovery, execution detail and cross-runner report production."""
import copy
import json
import os
import re
from pathlib import Path

import pytest


def diagnostic(code, identity, reason):
    return {"code": code, "identity": identity, "reason": reason}


def row(identity, marks):
    return {"runner": "pytest", "identity": identity.replace("\\", "/"),
            "links": sorted({sid for sid, _ in marks}),
            "markers": sorted([{"scenario": sid, "new": bool(new)} for sid, new in marks], key=lambda m: m["scenario"]),
            "new": any(new for _, new in marks)}


def snapshot(repo, runner=None):
    from redline.runner import PYTEST
    runner = runner or PYTEST
    expected, kinds = [], {}
    for base in (repo / "redline/specs", repo / "redline/changes"):
        for path in sorted(base.rglob("*.md")):
            for sid, kind in re.findall(r"^#### Scenario (\S+) \[(new|hold|manual)\]:", path.read_text(encoding="utf-8"), re.M):
                kinds[sid] = kind
    paths = []
    for directory, children, names in os.walk(repo):
        children[:] = sorted(c for c in children if not c.startswith(".") and c not in ("node_modules", "__pycache__"))
        paths.extend(Path(directory) / name for name in sorted(names) if any(Path(name).match(p) for p in runner.paths))
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
            for name, body, marks in runner.tests(path.relative_to(repo).as_posix(), text):
                if marks:
                    entry = row(f"{path.relative_to(repo).as_posix()}::{name}", [(m.sid, m.new) for m in marks])
                    entry["declarations"] = {sid: kinds.get(sid, "unavailable") for sid in entry["links"]}
                    entry["runner"] = runner.name
                    if runner.name == "jest":
                        offset = text.index(body)
                        entry["location"] = [path.relative_to(repo).as_posix(), marks[0].line, offset - text.rfind("\n", 0, offset)]
                    expected.append(entry)
        except (OSError, UnicodeError, RuntimeError):
            expected.append(dict(row(path.relative_to(repo).as_posix(), []), runner=runner.name, unavailable=True))
    return expected


def attach(config):
    """Claim a fresh sink once per process/session; nested pytest.main cannot reuse it."""
    sink = config.getoption("redline_report")
    if not sink:
        return
    try:
        with Path(sink).with_name(f"session-{os.getpid()}").open("x", encoding="utf-8"):
            pass
    except FileExistsError:
        return
    config.pluginmanager.register(Collector(config), "redline-report-collector")


class Collector:
    def __init__(self, config):
        self.config = config
        self.sink = Path(config.getoption("redline_report"))
        self.expected, self.observed, self.diagnostics = [], [], []
        self.phases, self.workers, self.finished = {}, set(), set()
        self.inventories = []

    @pytest.hookimpl(hookwrapper=True, tryfirst=True)
    def pytest_collection_modifyitems(self, items):
        self.expected = [row(i.nodeid, [(m.args[0], m.kwargs.get("new", False))
                         for m in i.iter_markers("spec")]) for i in items if list(i.iter_markers("spec"))]
        # Persist the pre-filter inventory even if a worker dies during execution.
        worker = getattr(self.config, "workerinput", {}).get("workerid", "local")
        self.sink.with_name(worker + ".json").write_text(json.dumps(self.expected, ensure_ascii=False), encoding="utf-8")
        yield

    def pytest_deselected(self, items):
        for item in items:
            if list(item.iter_markers("spec")):
                self.diagnostics.append(diagnostic("deselected", item.nodeid, "removed by selection"))

    def pytest_collectreport(self, report):
        if report.failed:
            self.diagnostics.append(diagnostic("collection-error", report.nodeid, str(report.longrepr)))

    @pytest.hookimpl(hookwrapper=True, tryfirst=True)
    def pytest_runtest_makereport(self, item, call):
        outcome = yield
        report = outcome.get_result()
        marks = [(m.args[0], m.kwargs.get("new", False)) for m in item.iter_markers("spec")]
        if not marks:
            return
        effective = next(item.iter_markers("xfail"), None)
        own = effective is not None and effective.kwargs.get("strict") is True and effective.kwargs.get("reason", "").startswith("new scenario ")
        report.redline_record = row(item.nodeid, marks)
        report.redline_record.update(phase=report.when, status=("expected-failure" if hasattr(report, "wasxfail") else
            "unexpected-pass" if report.failed and str(report.longrepr).startswith("[XPASS(strict)]") else
            {"passed": "pass", "failed": "error", "skipped": "skip"}[report.outcome]),
            strict_new=bool(own and call.excinfo and call.excinfo.typename != "XFailed" and hasattr(report, "wasxfail")),
            unrelated_xfail=bool(effective and not own))

    def pytest_runtest_logreport(self, report):
        record = getattr(report, "redline_record", None)
        if record is None:
            return
        identity = record["identity"]
        phases = self.phases.setdefault(identity, [])
        phases.append(record)
        if report.when == "teardown":
            result = {k: v for k, v in record.items() if k not in ("phase", "status")}
            result["phases"] = {r["phase"]: r["status"] for r in phases}
            call = next((r for r in phases if r["phase"] == "call"), {})
            result.update(outcome=call.get("status", "error"), strict_new=call.get("strict_new", False))
            if any(r["status"] != "pass" for r in phases if r["phase"] != "call"):
                result["outcome"] = "skip" if any(r["status"] == "skip" for r in phases) else "error"
            self.observed.append(result)
            self.phases.pop(identity)

    @pytest.hookimpl(optionalhook=True)
    def pytest_configure_node(self, node):
        self.workers.add(node.gateway.id)

    @pytest.hookimpl(optionalhook=True)
    def pytest_testnodedown(self, node, error):
        self.finished.add(node.gateway.id)
        self.diagnostics.extend(getattr(node, "workeroutput", {}).get("redline_diagnostics", []))
        if error:
            self.diagnostics.append(diagnostic("missing-worker", node.gateway.id, str(error)))

    @pytest.hookimpl(optionalhook=True)
    def pytest_xdist_node_collection_finished(self, node, ids):
        self.inventories.append(ids)
        if ids != self.inventories[0]:
            self.diagnostics.append(diagnostic("inventory-conflict", node.gateway.id, "worker collections differ"))

    def pytest_sessionfinish(self, session, exitstatus):
        if hasattr(self.config, "workerinput"):
            self.config.workeroutput["redline_diagnostics"] = self.diagnostics
            return
        inventories = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(self.sink.parent.glob("*.json"))]
        if inventories:
            self.expected = inventories[0]
            if any(rows != self.expected for rows in inventories):
                self.diagnostics.append(diagnostic("inventory-conflict", "pytest", "pre-filter inventories differ"))
        for worker in sorted(self.workers - self.finished):
            self.diagnostics.append(diagnostic("missing-worker", worker, "worker did not finish"))
        for identity in self.phases:
            self.diagnostics.append(diagnostic("missing-phase", identity, "execution did not finish"))
        if exitstatus not in (0, 1, 5):
            self.diagnostics.append(diagnostic("abort", "pytest", f"session exit {exitstatus}"))
        self.sink.write_text(json.dumps({"expected": self.expected, "observed": self.observed,
            "diagnostics": self.diagnostics}, ensure_ascii=False), encoding="utf-8")


def finish(source, payload):
    payload = copy.deepcopy(payload)
    expected, observed, diagnostics = payload["expected"], payload["observed"], payload["diagnostics"]
    for entry in source:
        instances = [r for r in expected if r["runner"] == entry["runner"] and (
            r.get("location") == entry["location"] if "location" in entry else
            r["identity"] == entry["identity"] or r["identity"].startswith(entry["identity"] + "["))]
        if not instances:
            expected.append(entry)
        for instance in instances:
            instance["source"] = entry["identity"]
            instance["declarations"] = entry.get("declarations", {})
        for record in observed:
            if any(all(record.get(k) == r.get(k) for k in ("runner", "identity", "location")) for r in instances):
                record["source"] = entry["identity"]
    expected = sorted(expected, key=lambda r: r["identity"])
    if not expected:
        diagnostics.append(diagnostic("empty", "pytest", "no linked instances discovered"))
    for entry in expected:
        if entry.get("unavailable"):
            diagnostics.append(diagnostic("collection-error", entry["identity"], "source inventory unavailable"))
    wanted = {(r["runner"], r["identity"]) for r in expected}
    for record in observed:
        if (record["runner"], record["identity"]) not in wanted:
            diagnostics.append(diagnostic("extra", record["identity"], "execution absent from inventory"))
    by_id = {}
    for record in observed:
        by_id.setdefault((record["runner"], record["identity"]), []).append(record)
    observed_ids = {r["identity"] for r in observed}
    for entry in expected:
        identity = entry["identity"]
        records = by_id.get((entry["runner"], identity), [])
        if sum(r["runner"] == entry["runner"] and r["identity"] == identity for r in expected) > 1:
            diagnostics.append(diagnostic("duplicate", identity, "repeated inventory identity"))
        if not records:
            diagnostics.append(diagnostic("missing", identity, "expected instance did not execute"))
            observed.append(dict(entry, outcome="missing", phases={}, strict_new=False))
        if len(records) > 1:
            diagnostics.append(diagnostic("duplicate", identity, "repeated execution"))
            if any(r != records[0] for r in records):
                diagnostics.append(diagnostic("conflicting", identity, "execution records disagree"))
            if entry.get("location") and sum(r.get("location") == entry["location"] and r["identity"] == identity for r in expected) > 1:
                diagnostics.append(diagnostic("ambiguous", identity, "parameter identity is not unique"))
        for record in records:
            if any(record[k] != entry[k] for k in ("links", "new", "markers")):
                diagnostics.append(diagnostic("conflicting", identity, "inventory and execution markers differ"))
            if record["outcome"] == "skip":
                diagnostics.append(diagnostic("skip", identity, "test skipped"))
            if set(record["phases"]) != {"setup", "call", "teardown"}:
                diagnostics.append(diagnostic("missing-phase", identity, "expected all three phases"))
    scenarios = {}
    for sid in sorted({sid for r in expected for sid in r["links"]}):
        wanted = [r for r in expected if sid in r["links"]]
        actual = [r for r in observed if sid in r["links"]]
        ids = {r["identity"] for r in wanted}
        if len({r["new"] for r in wanted}) > 1 or any(len({m["new"] for m in r["markers"]}) > 1 for r in wanted):
            diagnostics.append(diagnostic("mixed-markers", sid, "linked new/hold states differ"))
        affected = ids | {r["identity"] for r in actual}
        complete = bool(wanted) and not any(d["identity"] in affected or d["identity"] not in observed_ids for d in diagnostics)
        red = all(r["new"] and r["strict_new"] and r["outcome"] == "expected-failure" and
                  r["phases"].get("call") == "expected-failure" and
                  r["phases"].get("setup") == r["phases"].get("teardown") == "pass" for r in actual)
        green = all(not r["new"] and not r.get("unrelated_xfail") and r["outcome"] == "pass" and
                    r["phases"].get("call") == "pass" and
                    r["phases"].get("setup") == r["phases"].get("teardown") == "pass" for r in actual)
        scenarios[sid] = {"expected": sorted(ids), "observed": sorted(r["identity"] for r in actual),
            "complete": complete, "qualification": ("red" if red else "green" if green else "nonqualifying") if complete else "nonqualifying"}
    return {"version": 1, "complete": bool(expected) and not diagnostics, "expected": sorted(expected, key=lambda r: json.dumps(r, sort_keys=True)),
            "observed": sorted(observed, key=lambda r: r["identity"]), "scenarios": scenarios,
            "diagnostics": sorted(diagnostics, key=lambda d: (d["code"], d["identity"], d["reason"]))}


def aggregate(reports, *, commit):
    """Revalidate every runner's detail; never trust cached qualification or complete flags."""
    payload = {"expected": [], "observed": [], "diagnostics": []}
    for report in reports:
        code = "malformed"
        try:
            if not isinstance(report, dict):
                raise ValueError("report must be a mapping")
            if type(report.get("version")) is not int or report["version"] != 1:
                code = "unsupported"
                raise ValueError("report version is not 1")
            for section in ("expected", "observed", "diagnostics"):
                if not isinstance(report[section], list):
                    raise ValueError("report lists required")
            for record in report["expected"] + report["observed"]:
                if (not isinstance(record["identity"], str) or not isinstance(record["links"], list)
                        or not all(isinstance(s, str) for s in record["links"]) or not isinstance(record["new"], bool)
                        or record["runner"] not in ("pytest", "jest") or not isinstance(record["markers"], list)):
                    raise ValueError("invalid execution identity or markers")
                if any(not isinstance(m["scenario"], str) or not isinstance(m["new"], bool) for m in record["markers"]):
                    raise ValueError("invalid marker state")
            for record in report["observed"]:
                if (not isinstance(record["strict_new"], bool) or record["outcome"] not in
                        ("pass", "expected-failure", "unexpected-pass", "skip", "deselected", "error", "missing")
                        or not isinstance(record["phases"], dict)):
                    raise ValueError("invalid execution outcome or phases")
            if not isinstance(report["complete"], bool):
                raise ValueError("complete must be boolean")
            details = copy.deepcopy(report)
            details["diagnostics"] = [{**d, "identity": d.get("identity", d.get("runner", "report"))} for d in details["diagnostics"]]
            if any(not all(isinstance(d[k], str) for k in ("code", "identity", "reason")) for d in details["diagnostics"]):
                raise ValueError("invalid diagnostic")
            if not report["complete"] and not details["diagnostics"]:
                details["diagnostics"].append(diagnostic("abort", "report", "runner did not complete"))
            for section in payload:
                payload[section].extend(details[section])
        except (KeyError, TypeError, ValueError, AttributeError) as error:
            payload["diagnostics"].append(diagnostic(code, "report", str(error)))
    for section in payload:
        payload[section].sort(key=lambda r: json.dumps(r, sort_keys=True))
    return dict(finish([], payload), commit=commit)
