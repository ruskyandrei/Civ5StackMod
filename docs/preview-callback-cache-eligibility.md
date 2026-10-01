# Callback eligibility for preview caches

Combat previews may use Lua movement/loading hooks that inspect or mutate live
state. A cache hit must preserve those hooks rather than return a prior result.
The owned preview now installs an explicit native capability provider. It checks
the actual core lock and enabled movement, rebase, range-attack, city-bombard,
airlift, sealift and unit-action hooks. A pure live-world scan runs once per
validated scene generation; cached eligibility is rechecked and invalidated
when the scene, ownership, nesting or support changes.

The scan examines current AIR melee base strength, including negative nonzero
values that the native defender predicate accepts, and current non-AIR
interceptors with heavy-charge or morale capabilities. Standard zero-base
ranged aircraft retain cache support when the complete callback graph permits
it. AIR preview actors and unsupported callback graphs use the original
calculations. A zero proof flag with no completed scan is unknown support,
not evidence of eligibility.

Danger rebuilding and AIR fallback legality suspend preview caching and
invalidate before and after execution. This covers legacy CanLoadAt calls,
which exist even when modern rebase hooks are disabled. City blockade can
consult custom AIR defenders; an AIR danger-source list alone is insufficient.
The numeric combat formulas, candidate order, FIFO and cache/search limits
remain unchanged. There is no new result table or save-format change.

The actual adopted five files pass46,072 capability/lifecycle/source-predicate
and formatter checks, plus140,042 unchanged full combat-math checks. Negative
controls demonstrate callback skipping in the prior compatibility case. These
are deterministic source tests, not proof about every mod or a native speed
result. Existing PLAN_PERF records add callbackProofScans,
callbackProofFlags, callbackValidationBypasses and callbackSuspensions.
Native overhead and recorded decisions must be checked on the preserved save.

Reproduction: work/stage-preview-callback-capability.py,
work/test-preview-callback-capability.py --production,
and work/test-full-melee-preview-callback-provider.py --production.
