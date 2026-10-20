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
  return {
    test(name, fn, timeout) {
      if (options.new && typeof test.failing !== "function") {
        throw new Error("a new scenario needs test.failing: Jest 28.1 or later, with jest-circus");
      }
      const run = options.new ? test.failing : test;
      return (only && (options.new || only !== id) ? test.skip : run)(name, fn, timeout);
    },
  };
}

module.exports = { spec };
