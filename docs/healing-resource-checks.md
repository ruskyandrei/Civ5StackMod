# Avoiding a repeated healing resource check

The full-movement tactical scorer checked resource eligibility twice: first in
`IsCannotHeal(true)`, then immediately inside `ActualHealRate(false)` through
`canHeal`. The outer gate now checks the unit's intrinsic healing prohibition
with `IsCannotHeal(false)` and leaves the resource check to the existing inner
path. Resource shortages still prevent healing. The partial-movement branch is
unchanged because its flat-healing path can bypass `ActualHealRate`.

No heal rate, movement rule, search budget, resource quantity or result cache
changes. The source fixture binds the production file to this one-predicate
delta from DLL69. It compiles the actual healing scorer block and complete
`IsCannotHeal`, `canHeal`, `ActualHealRate` and `HasResourceForNewUnit` functions
with x86 VC9. Its61,660 checks pass, covering partial/full movement, shortages,
projected damage, engine callback order and mutations to both players' resource
state. The unchanged religion/aura/trait heal-rate arithmetic is represented by
a configurable service; this is not a whole-scorer or full-engine proof.

Eligible full-movement healing uses one resource scan instead of two. Shortage
cases still use one. Native timing and action/census comparisons are required
before claiming an in-game improvement. Regression command:
`work/test-healing-resource-gate.py --production`.
