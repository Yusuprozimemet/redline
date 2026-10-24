## 10. Learning loop

`redline retro` at each close groups the change's defects by cause and proposes rule changes to
`redline/config.yaml`, each as a normal small PR.

A rule is a line under its cause in the config's `rules:`, and every brief prints all of them, so
every later session sees what earlier defects taught:

```yaml
rules:
  premise:
    - Cite where a value is stored, not only where it is read
```

`redline retro <change>` reads the change's `defects.md` (it refuses unless check-defects passes,
whatever the level) and the config's `rules:`. It prints, for each cause with defects, most
first: the count, the IDs and headings, and how many rules the cause has already. Then one
proposal per cause: add a rule under `rules.<cause>` against those defects. With no defects, it
says there is nothing to propose.

It writes nothing. The wording of a rule is a judgment, so the session or the maintainer writes
it, one cause per PR, and the maintainer reviews it like any other change. On its own, `retro`
never:

- **edits `redline/config.yaml`**, commits, pushes or opens a PR;
- **edits `defects.md`**: a tool that rewrote causes would bias any later relabelling;
- **proposes removing or weakening** anything: no rule removed, no rigor lowered. A change's level
  is its proposal's and its auditor's call (§8), so `retro` doesn't propose one.

Its output is a proposal, never evidence (§7), and CI doesn't run it.
