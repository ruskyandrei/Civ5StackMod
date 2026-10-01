# Inline completion gates for disabled tactical sampling

`PlanSampleScope` is called throughout hot combat and planning paths. Sampling
is off by default; most individual scopes are also unselected when it is on.
The destructor and explicit `Finish()` now test their existing `sampled` flag
inline. Only selected scopes call the unchanged completion implementation.
This removes out-of-line completion calls for scopes doing no timing work.

The constructor, cadence, TLS/epoch ownership checks, clocks, counters, logging
format and selected completion body are unchanged. An explicit finish followed
by destruction still records once. No gameplay rule or search budget changes.

`work/prepare-inline-plan-finish.py` stages the narrow patch from frozen DLL77.
`work/test-inline-plan-finish.py --production` pins the complete adopted source
files and compiles their actual header gates and sampled implementations with
VC9. The existing cadence/lifecycle fixture passes89 checks covering disabled
and ineligible scopes, cadence counts, nested/foreign threads, resets/toggles,
exceptions, duplicate completion and clock failures. Deterministic services
verify accounting, not native performance. A same-save native replay must
establish timing and retained action/census equivalence before claiming a win.
