// Redline's Jest helper, written by `redline install jest`; every Redline gate fails if it is edited.
// A test links a scenario with spec(<ID>).test(name, fn). With spec(<ID>, { new: true }) the scenario
// has no code yet: the test runs as test.failing, so a new test that passes fails the run. Under
// REDLINE_SPEC=<ID>, only the tests linked to that ID without new run. See Redline's design, section 5.
"use strict";

function spec(id, options = {}) {
  if (typeof id !== "string" || !id || Object.keys(options).some((key) => key !== "new")) {
    throw new Error("spec takes a scenario ID and, for a new scenario, { new: true }");
  }
  const only = process.env.REDLINE_SPEC;
  const frame = new Error().stack.split("\n").find(s => /:\d+:\d+\)?$/.test(s) && !s.includes(__filename));
  const location = frame && frame.match(/(?:\(|at )(.*):(\d+):(\d+)\)?$/);
  function register(name, fn, timeout) {
      if (options.new && typeof test.failing !== "function") {
        throw new Error("a new scenario needs test.failing: Jest 28.1 or later, with jest-circus");
      }
      const run = options.new ? test.failing : test;
      const meta = {id, new: !!options.new, location: location && location.slice(1), body: "missing"};
      function body(...args) {
        const passed = value => {meta.body = "pass"; return value;};
        const failed = error => {meta.body = "error"; throw error;};
        if (fn.length) {
          const done = args[0];
          args[0] = Object.assign(error => {meta.body = error ? "error" : "pass"; done(error);}, done);
        }
        try {
          const value = fn.apply(this, args);
          return value && typeof value.then === "function" ? value.then(passed, failed) : fn.length ? value : passed(value);
        } catch (error) { return failed(error); }
      }
      Object.defineProperty(body, "length", {value: fn.length});
      body.redline = meta;
      return (only && (options.new || only !== id) ? test.skip : run)(name, body, timeout);
  }
  register.each = (...table) => require("jest-each").bind(register)(...table);
  return {test: register};
}

module.exports = { spec };
