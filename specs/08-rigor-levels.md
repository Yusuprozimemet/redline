## 8. Rigor levels (on top of the invariants)

| Level | Adds |
|---|---|
| **lite** | Nothing; S and R may share one PR |
| **standard** (default) | Mutation testing on the touched files, and a defect log |
| **critical** | Contract lock covers what each test reaches, timing included (§4, §5), one track per Green PR, a plan-auditor at the start and end of each phase, blind relabelling of defects, independent end-of-initiative auditors |

The proposal declares its level. The auditor may raise it (auth, payments, data migrations,
public APIs are critical) but never lower it. Nor may a step: lowering a change's level once its
proposal is on `main` is the rigor claim, a maintainer's decision (§7, Approvals).
