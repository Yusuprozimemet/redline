## 2. Seven invariants (always on, at every rigor level)

1. **The spec comes before the code.** No code PR exists without a merged spec for it.
2. **Red before green, proved on `main`.** A test for a `new` scenario lands as a *strict expected
   failure*, and CI confirms it really fails.
3. **Every PR is ≤ 400 changed lines.** Specs and tests count; lockfiles and generated files
   (declared in config, as it is at the merge-base with `main`, §7) don't. A bigger PR needs an `Oversized: <reason>` trailer on one of its
   commits and a maintainer's `redline:oversized` label (§7).
4. **One session per step.** A step is one PR. A merge ends the session.
5. **An independent audit before code.** A read-only agent in a fresh context, on the strongest
   model, Fable; when Fable isn't available, on Opus at its highest effort, and never on a weaker
   one: below that the work stops. Each audit records the model that wrote it (§9).
6. **The CLI observes; the agent never certifies.** Evidence is whatever CI ran.
7. **Nothing is silent.** Every departure, waiver or deferral is a recorded line with an owner.
