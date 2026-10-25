// Invocation-private circus event collector. Preserve the project's environment and its event hook.
"use strict";
const fs = require("fs"), path = require("path"), crypto = require("crypto");
module.exports = target => async function(globalConfig, config, environment, runtime, testPath, sendMessage) {
  const report = {expected: [], observed: [], diagnostics: []}, rows = new Map();
  const relative = path.relative(target.root, testPath).split(path.sep).join("/");
  const issue = (code, identity, reason) => report.diagnostics.push({code, identity, reason});
  function inventory(block, parents = []) {
    for (const child of block.children) {
      if (child.type === "describeBlock") { inventory(child, [...parents, child.name]); continue; }
      const meta = child.fn && child.fn.redline;
      if (!meta) continue;
      const identity = relative + "::" + [...parents, child.name].join(" ");
      const location = meta.location;
      const row = {runner: "jest", identity, links: [meta.id], new: meta.new,
        markers: [{scenario: meta.id, new: meta.new}],
        location: location && [relative, Number(location[1]), Number(location[2])]};
      report.expected.push(row);
      rows.set(child, {...row, phases: {setup: "pass", call: "missing", teardown: "pass"}, strict_new: false});
    }
  }
  const previous = environment.handleTestEvent;
  environment.handleTestEvent = async (event, state) => {
    if (previous) await previous.call(environment, event, state);
    if (event.name === "run_start") inventory(state.rootDescribeBlock);
    const test = event.test, row = rows.get(test);
    if (event.name === "hook_failure") {
      if (row) row.phases[event.hook.type === "beforeEach" ? "setup" : "teardown"] = "error";
      else issue("collection-error", relative, "beforeAll/afterAll hook failed");
    }
    if (row && ["test_done", "test_skip", "test_todo"].includes(event.name)) {
      const meta = test.fn.redline;
      row.outcome = event.name !== "test_done" ? "skip" : test.errors.length ?
        (meta.new && meta.body === "pass" && row.phases.setup === row.phases.teardown ? "unexpected-pass" : "error") :
        meta.new && test.failing && meta.body === "error" ? "expected-failure" : meta.body === "pass" ? "pass" : "error";
      row.strict_new = row.outcome === "expected-failure";
      row.phases.call = row.outcome;
      report.observed.push({...row, phases: {...row.phases}});
    }
    if (event.name === "run_finish" && state.unhandledErrors.length) issue("abort", relative, "unhandled circus errors");
  };
  try {
    const circus = require(require.resolve("jest-circus/runner", {paths: [config.rootDir]}));
    const result = await circus(globalConfig, config, environment, runtime, testPath, sendMessage);
    if (result.testExecError) issue("collection-error", relative, "file execution failed");
    return result;
  } catch (error) {
    issue("collection-error", relative, String(error));
    throw error;
  } finally {
    environment.handleTestEvent = previous;
    // A missing sink is diagnosed by runner.py; report transport cannot change Jest's result.
    try { fs.writeFileSync(path.join(target.sink, crypto.randomUUID() + ".part"), JSON.stringify(report)); } catch (_) {}
  }
};
