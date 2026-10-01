# Parent roster preparation prototype

Work only, pinned to DLL91 `e8b5bd3e6`. No production source has been changed.
Generate with `work/prepare-parent-stack-preparation.py`; run the VC9 x86
actual-source fixture with `work/test-parent-stack-preparation.py`. Its optional
`--production` mode binds both complete candidate files and sixteen unchanged
Unit/Combat/Danger/Strength/Rules/Plot/Player/UnitClasses dependencies to the
frozen source, before compiling. The stager reverses its entire delta and
asserts exact equality to both original files.

The change reuses ordered fixed/movable roster membership and the original
first-match friendly-wound reads through one parent's const preferred-unit
batch. Each destination is built once. Arrival units are appended only when
their pointer was absent, and their exact projected wound value overwrites the
first matching ID exactly as before. Fixed/movable duplicates, raw ID aliases,
missing stats, zero/negative/over-maximum projected wounds retain their original
meaning. No result, serialized key, quantized hash or outcome is cached here.

The original query's fresh owned scratch loan is the admission witness. Private,
busy, foreign and unsupported queries use the unchanged builder. The view ends
before child expansion. Its only child witness comes from the actual
GetNextPosition EFD-only helper and checks the same player and all five CoW
roster/stat containers. A stat/roster CoW write, unknown child, nested lexical
view, revision or scene change rejects preparation reuse. Native source hazards,
enemy wounds, city state and full key serialization are still read by the
original scalar helper on every call. The existing Context, key-scratch capacity,
cache hit/miss/admission/FIFO gates are unchanged.

Warmed reuse performs vector copies and native GetID/GetPlotIndex field getters
after the caller's existing fresh Context. It adds no extra interlocked scene
read to that path. The initial native base build gets a fresh epoch check before
publication. No live gameplay or assignment-history mutation occurs in the
enclosed const batch; this is a lexical proof, not a mutation token intended for
arbitrary public callers. A scene/nested invalidation during the optional build
discards its cell and delegates to the original builder.

Physical footprint is **16,332 bytes** of fixed metadata in the actual VC9 x86
fixture. Dynamic candidate/damage capacities are accounted by exact per-cell
deltas, including inactive retained cells, and are bounded by the existing
forecast payload ceiling (624,000 bytes with the tested configuration). Hitting
255 metadata cells or the payload ceiling falls back without changing search
limits. Temporary vector growth before the ceiling check can exceed the retained
ceiling; it is released before fallback. The existing native forecast
estimatedBytes statistic does **not** include this separate preparation storage.
It should be considered separately until a measured adoption extends that
estimate. Allocation failure releases all optional retained payload before the
original builder retries. Outer search teardown releases every retained vector.

The actual-source old/new fixture passed **295,462 checks, zero failures**.
Its deterministic native math and forecast backend substitutes verify exact
serialized keys, key scratch capacities, Context counts, scalar hit/miss graphs,
sentinel clamping, CoW/first-match/EFD/arrival behavior, source invalidation,
private/foreign/nested/off/fixed fallbacks, allocation failures and exception
unwinding. The complete scalar/danger/preview/query/key-builder bodies are
extracted from the frozen source; the original scalar body is unchanged. A
full-sum oracle checks retained capacity accounting after every randomized
parent and the failure cases. Fixture peak retained preparation payload was
396 bytes; that is test-shape evidence, not a prediction for the real game.

There is no native speed claim. DLL91's keyed-unit repeat observations motivate
this first preparation step but do not predict its runtime gain. Resident-key
elision is a separate possible next stage: it would additionally need a live
resident token, a still-owned key scratch loan and the original warmed capacity
preflight contract. This prototype does not consume the observer's mutation
tokens or the separate resident-handle API.
