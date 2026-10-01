# Raw path-danger measurements

The existing tactical-sampling opt-in now measures path queries as well as
combat planning. It remains off by default. This adds diagnostics, with no
danger-result reuse, path-cost changes or reduced search limits.

One in eight outer queries is selected; one in sixteen raw-danger/clear-terrain
calls is timed. Each selected query emits one `PATH_SAMPLE` row identifying
its actor/unit, path type, search or verification, generation, flags, endpoints
and source epochs. It reports call counts, sampled ticks and node-cache counts.
Nested queries suppress their own rows; measured wall intervals can overlap
other queries and PLAN. They must not be added as independent CPU costs.

Repeat observations use128 fixed TLS slots and at most16 probes per call.
Saturation/collisions are counted as untracked work. Matching plot, scene and
actor HP describes a bounded opportunity, not a validated cache hit. It does
not prove stable attack sources, interceptor counters, promotions, hazards or
city/garrison state. Legacy loading callbacks are not excluded by the event
mask. Future memoization requires an independent dependency/lifecycle proof.

Disabled node probes perform no extra getters, clocks, allocations, settings,
locks or logging. An off-query observation is made under the diagnostics lock
then mirrored per thread; Reset/load, level changes and sampling toggles
invalidate it through the existing atomic epoch. Source constructors use
already available query fields. Ordinary path verification stays unchanged.

The production-bound actual-source fixture passes101 checks. It binds all
three entire current core files, keeps its DLL79 control in Git, and compiles
complete original/current FindPath and VerifyPath bodies alongside the sampler.
ON/OFF results, callback counts, generations, returns, exceptions, nested/
foreign scopes, reset/toggle, bounds and clock failures are covered. The
44-argument formatter matches44 fields; worst fixture row is1426 bytes.
Deterministic path services are substituted; this is not a full engine proof.

The parser/anchor fixture passes33 checks. Both wall and CPU helpers exclude
`PATH_SAMPLE` from legacy first-event anchors, retaining comparable round
windows. The reader reports missing successful samples as unknown timing,
and never scales observed repeats into saved time. Native OFF/ON replay checks
must verify behavior and quantify instrumentation cost before interpretation.

Reproduction: `work/prepare-path-query-profile.py`,
`work/test-path-query-profile.py --production`, and
`work/test-profile-path-queries.py --production`. Analyze an archived run with
`work/profile-path-queries.py <native-folder> --run <exact-run> --turn 253
--output <report.json>`. No per-node rows or per-turn Lua observer are needed.
