## 3. Units

```
Initiative  (optional)   plan.md: goal, phases, stopping points
  └─ Change              redline/changes/<id>/: proposal, delta spec, ledger
       └─ Step           ONE PR ≤ 400 lines = ONE session
```

An initiative is work too big for one change: a goal, reached in phases, each phase a set of
changes. A phase ends at a **stopping point**, where every change of the phase is complete and
`main` is coherent enough to stop for good: the initiative may end there and leave nothing half
done. Whether to go on is the maintainer's call. A change belongs to at most one phase of at most
one initiative. Most changes belong to none.
