"""Invocation-local pytest discovery and phase reports; consumers belong to later steps."""
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


def snapshot(repo):
    from redline.runner import python_tests
    expected, kinds = [], {}
    for base in (repo / "redline/specs", repo / "redline/changes"):
        for path in sorted(base.rglob("*.md")):
            for sid, kind in re.findall(r"^#### Scenario (\S+) \[(new|hold|manual)\]:", path.read_text(encoding="utf-8"), re.M):
                kinds[sid] = kind
    paths = []
    for directory, children, names in os.walk(repo):
        children[:] = sorted(c for c in children if not c.startswith(".") and c not in ("node_modules", "__pycache__"))
        paths.extend(Path(directory) / name for name in sorted(names) if name.endswith(".py"))
    for path in paths:
        try:
            for name, _, marks in python_tests(path.relative_to(repo).as_posix(), path.read_text(encoding="utf-8")):
                if marks:
                    entry = row(f"{path.relative_to(repo).as_posix()}::{name}", [(m.sid, m.new) for m in marks])
                    entry["declarations"] = {sid: kinds.get(sid, "unavailable") for sid in entry["links"]}
                    expected.append(entry)
        except (OSError, UnicodeError, RuntimeError):
            expected.append(dict(row(path.relative_to(repo).as_posix(), []), unavailable=True))
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
    expected, observed, diagnostics = payload["expected"], payload["observed"], payload["diagnostics"]
    for entry in source:
        instances = [r for r in expected if (r["identity"] == entry["identity"] or r["identity"].startswith(entry["identity"] + "["))]
        if not instances:
            expected.append(entry)
        for instance in instances:
            instance["source"] = entry["identity"]
            instance["declarations"] = entry.get("declarations", {})
    expected = sorted(expected, key=lambda r: r["identity"])
    if not expected:
        diagnostics.append(diagnostic("empty", "pytest", "no linked instances discovered"))
    for entry in expected:
        if entry.get("unavailable"):
            diagnostics.append(diagnostic("collection-error", entry["identity"], "source inventory unavailable"))
    by_id = {}
    for record in observed:
        by_id.setdefault(record["identity"], []).append(record)
    for entry in expected:
        identity = entry["identity"]
        records = by_id.get(identity, [])
        if not records:
            diagnostics.append(diagnostic("missing", identity, "expected instance did not execute"))
            observed.append(dict(entry, outcome="missing", phases={}, strict_new=False))
        if len(records) > 1:
            diagnostics.append(diagnostic("duplicate", identity, "repeated execution"))
        for record in records:
            if record["outcome"] == "skip":
                diagnostics.append(diagnostic("skip", identity, "test skipped"))
            if set(record["phases"]) != {"setup", "call", "teardown"}:
                diagnostics.append(diagnostic("missing-phase", identity, "expected all three phases"))
    scenarios = {}
    for sid in sorted({sid for r in expected for sid in r["links"]}):
        wanted = [r for r in expected if sid in r["links"]]
        actual = [r for r in observed if sid in r["links"]]
        ids = {r["identity"] for r in wanted}
        complete = bool(wanted) and not any(d["identity"] in ids or d["identity"] not in by_id for d in diagnostics)
        red = all(r["new"] and r["strict_new"] and r["outcome"] == "expected-failure" and
                  r["phases"].get("setup") == r["phases"].get("teardown") == "pass" for r in actual)
        green = all(not r["new"] and not r.get("unrelated_xfail") and r["outcome"] == "pass" for r in actual)
        scenarios[sid] = {"expected": sorted(ids), "observed": sorted(r["identity"] for r in actual),
            "complete": complete, "qualification": ("red" if red else "green" if green else "nonqualifying") if complete else "nonqualifying"}
    return {"version": 1, "complete": bool(expected) and not diagnostics, "expected": expected,
            "observed": sorted(observed, key=lambda r: r["identity"]), "scenarios": scenarios,
            "diagnostics": sorted(diagnostics, key=lambda d: (d["code"], d["identity"], d["reason"]))}
