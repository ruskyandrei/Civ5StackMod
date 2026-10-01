# Read-only path-query performance candidates

Source inspected at DLL79 (`CvAStar.cpp` is legacy VP code). No core, diagnostic, rule or build changes made for this audit. The earlier turn253 residuals—operations about5.6s, homeland2.7s, city production3s—are enclosing wall remainders after subtracting planning spans, not attribution to these specific path routines.

## What is already cached

`CvAStar.cpp:924` `UpdateNodeCacheData` returns immediately when a node's `iGenerationID` equals the finder's current generation. The stacking check at985 is therefore normally once per physical node per query, not once per incoming edge. `NodeAddedToPath:1738` eagerly updates neighboring nodes; subsequent parents reuse the generation stamp. Partial-stop node creation at3030 also computes cache data and subsequently copies the current node cache at3047. A second broad stacking-result cache would mostly duplicate existing behavior.

`CvUnit.cpp:29465` `CanStackUnitAtPlot` has a foreign combat blocker scan, then `CountStackingUnitsAtPlot:29389` and `GetStackingLimit:29455`. These scans have different rules: the foreign blocker skips both dead/delayed units and cares about owner plus domain; the counter skips delayed death but preserves its separate neutral/enemy/cargo/special-unit rules. Merging them casually can change behavior.

There is no linked-list indexing quadratic trap here: `CvPlot.h:880` stores `m_units` in `FFastSmallFixedList`; its `getAt` in `FirePlace/include/FireWorks/FFastVector.h:869` indexes its backing vector directly. `CvPlot.cpp:13359` `getUnitByIndex` also preserves a multiplayer stale-ID desync-report side effect. Replacing it with a hand-written traversal would need to preserve that side effect and is not a demonstrated large win.

Capacity has only owner/domain/city dependence under stacking (`CvStackingRules.cpp:519`), but its technology/settings arithmetic is already small, and query-local capacity reuse needs callback/reload invalidation. Measure it before adding another cache.

## Concrete legacy duplicate: clear-node terrain/borders

`UpdateNodeCacheData:1020–1023` caches intermediate/permanent terrain and border eligibility. `PathValid:1588` immediately rejects when cached intermediate eligibility is false. On a visible node with no enemy/neutral occupant, it then calls `canEnterTerritoryAndTerrain:1524` again at1598 using the same node flags. This repeats the native border and terrain routines per incoming edge.

The two routines are not always trivial: `CvUnit.cpp:4621` can recurse through a city-state ally's border checks, and `canEnterTerrain:4712` examines unit/player traits, embarkation, sea/city/fort access, impassable terrain and promotion permissions. They contain no direct callbacks for ordinary land/sea terrain, but air terrain can call loading hooks.

Do not delete the live call on the strength of the generation cache alone. `CvAStar::VerifyPath:804` reuses `PathValid` after `Configure` and unit initialization without a fresh normal-search generation/cache build. Its cached booleans can be old while the live terrain/borders legitimately changed. Query siblings can also dispatch events through other node checks, so even a fresh generation is not a complete world-invariance proof.

## Stronger candidate: repeated raw end-turn danger

`PathEndTurnCost:1190` calls `pUnit->GetDanger(pToPlot)` at1293 whenever this query does danger checks. The raw danger call does **not** take turns-in-future or path-cost flags; those affect the later cost scale and abort decision. Multiple incoming edges reaching the same end-turn plot call it via `PathCost:1464`. Downstream cost updates at731 can call `PathCost` again, and voluntary stop nodes invoke `PathEndTurnCost` at3025 for their current plot.

The comment immediately above the raw call says the last danger is cached for each plot, but the current dispatch contains no such memo:

- `CvUnit::GetDanger:8354` forwards to its owner's `GetPlotDanger`.
- `CvPlayer::GetPlotDanger:46885` refreshes dirty danger and calls `CvDangerPlots::GetDanger`.
- `CvDangerPlots::GetDanger:503` calls the plot's `CvDangerPlotContents::GetDanger` directly.
- `CvDangerPlotContents::GetDanger:881` reconstructs real friendly membership/wounds and simulates stack danger for a combat unit. This lies outside the tactical search's scalar/packet wrapper, so current tactical packet memoization does not solve it.

This can duplicate a complete physical stack forecast for the same actor and target plot within one synchronous path query, rather than merely repeating a small getter. Its frequency and time are not yet measured; there is no native saved-time claim.

## Lifecycle and callback conditions before a reuse patch

The public path wrappers (`GetPath:3226`, `GetPlotsInReach:3307`, `GetMultiplePaths:3364`) hold or acquire the gamecore lock. `FindPathWithCurrentConfiguration:346` increments its generation, initializes query metadata and runs a synchronous search. No explicit gamecore yield was found inside AStar. However, callback paths and recursively invoked path queries still matter:

- `PathDestValid:1134` and occupied-node `PathValid:1604` can dispatch `CanMoveInto`.
- Node metadata calls `getAirliftFromPlot` and `getSealiftFromPlot`, with `MOD_EVENTS_AIRLIFT`/`MOD_EVENTS_SEALIFT` handlers (`CvUnit.cpp:8423`/`8640`). An event on another neighbor can mutate an earlier node's world dependencies.
- Air `canEnterTerrain` calls `canLoad`; `CvUnit.cpp:6512` has both `MOD_EVENTS_REBASE` and legacy `CanLoadAt` dispatch. Simply disabling one modern flag does not eliminate the legacy hook. An initial reuse scope should exclude air queried units and retain air/loading as original paths.
- Dirty danger rebuild at `CvPlayer:46885` can perform nested path queries, ranged eligibility and city bombard-range checks. `MOD_EVENTS_UNIT_RANGEATTACK` and `MOD_EVENTS_CITY_BOMBARD` can create mutation paths; callback-enabled configurations require fallback.
- Stack danger includes probabilistic air interception, physical HP and city/garrison effects. A raw value must retain `INT_MAX` city-fall semantics. It must not reuse a result after source-map, HP, hazard, city protection/damage or stack-membership changes, even if an incomplete old epoch/key would happen to match.
- Existing scene invalidation covers dirty danger, movements and many unit mutations, but it is not a proven universal world stamp: do not use scene equality alone as a new raw-world memo key. Callback-free synchronous immutability must be established, and full relevant physical guards remain prudent.
- `VerifyPath` must stay separate unless the same full live-query proof is built there. It cannot inherit a search's raw memo or node data by pointer/generation alone.
- Nested queries need separate scope ownership and must invalidate/suppress parent reuse if ownership or dependencies become uncertain. No entry may be admitted after a callback/yield/reset/nested operation changed the captured context. Do not retain raw source-vector pointers across lazy refresh.

## First measurement proposal

Add a default-off, sampled **query** profile before any raw reuse if the CPU share is uncertain. Identify unit/player, path type, exact flags, start/destination, generation and normal-search versus verify origin. Keep the existing route order, cost arithmetic, node counts, capacities and stop-node policy intact.

For selected queries only, count node-cache hits/builds, stack checks, `PathValid` clear-terrain live checks, end-turn-cost calls and raw danger calls. Count repeated raw danger plots within the same actor/query using bounded diagnostic state; distinguish dirty/nested/event-enabled calls and callback-free eligible repetitions. Record true fresh calls versus observed repeat opportunities. Sample timings around raw danger and clear-terrain helper only when the query/part is selected; no clock/settings/map/log operations on the default-off hot path. Use one bounded summary per sampled outer query (or per-player aggregation), never per-node rows. Nested timings are inclusive and cannot be added to parent phase totals.

Tie per-query results to the existing phase chronology to distinguish operation/home/city callers and PLAN overlap. Require actual raw-danger time and eligible repeat count before promising an improvement. Preserve exact flags and node visits, and report profiler overhead/coverage rather than treating a sampled estimate as saved time.

## Actual-source fixture plan for a bounded reuse candidate

Extract full old/new `PathEndTurnCost` and its `PathCost`/stop-node call context, together with actual `UnitPathCacheData`, `CvUnit::GetDanger`, `CvPlayer::GetPlotDanger`, danger dispatch and real-stack membership construction. Reuse the existing stack-outcome fixture service model for combat physics; retain actual cache eligibility/lifecycle and original dispatcher callback order. State explicitly that engine/physics services are fixtures, not a whole-game proof.

Compare returned costs/abort decisions and raw `INT_MAX` handling across repeated same-plot calls with different turns/flags, same actor plus different owner-local ID aliases, land/sea/civilian/air/cargo, physical HP and projected self-damage, hazards, friendly/enemy cities and fortification protection, stack occupants, changed sources with and without an epoch, dirty refresh and null metadata. Include callbacks changing world state or killing/replacing the actor, scripted movement/airlift/sealift/range/bombard/loading paths, nested search/finder reuse, generation/reset/exception/foreign-thread cases and `VerifyPath` after real world changes. No accepted hit may skip a callback/refresh that the original would perform. Compare full path sequences, edge/cost/stop-node counts and final assignment consequences in a matched native replay after the isolated fixture.

Memory must be bounded and released with the local query. Do not add an unconditional large record to every node of every persistent finder without quantifying the x86 footprint, and do not preserve results across movement/execution or player turns. A cache capacity limit may force original computation, never reject a path or alter the search budget.
