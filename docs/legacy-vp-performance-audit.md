# Original VP performance audit and phase timing

Investigation note. The user asked to consider costs that predate stacking, not only our new helpers. No legacy gameplay optimization is implemented by this note. The associated code adds sampled, top-level diagnostic timing only; it preserves existing logging settings and gameplay call order.

## Why measure beyond tactical searches

Archived DLL47 turn250 took68.000s, with125 recorded PLAN searches consuming38.471s and29.529s outside those PLAN durations. Outside-PLAN time is not automatically stacking overhead, pure computation, or even all AI time: it can include player preparation, other AIs, city/unit turns, existing logging, callbacks, and engine waits. PLAN phases can themselves include yields. The new timers identify which larger scopes merit a deeper profile before choosing optimizations.

## New timing contract

`CvStackingDiagnostics::TurnPhaseScope` records `TURN_PHASE` at summary level when performance category bit16, `DiagnosticsPlayer`, and a nonzero `DiagnosticsPerformanceInterval` permit it. There are no leaf, unit-loop, city-loop, or zone-loop timers. Disabled/filtered/unsampled scopes do not read the clock or open a file. The timer performs no game/database scans; numeric logging settings retain their existing lazy, cached configuration resolution.

Each row contains phase, startTick, endTick, elapsedMs, thread and `semantics=inclusive`. Nested phases and PLAN overlap. **Do not sum every phase row to obtain a complete round.** Use chronological containment and the documented hierarchy, or subtract the union of child intervals from a parent. GetTickCount is coarse and wraps; unsigned elapsedMs handles a single wrap. Phase timing includes time spent waiting/yielding within its interval and is not a CPU profile.

Explicit `Finish()` closes a contiguous region without restructuring its gameplay code. Destruction closes early-return/unwind paths and cannot duplicate an already finished region. Reset/level change and a game-turn transition invalidate an in-flight timer rather than attributing it to another session/turn. Names are string literals at all production call sites.

### Main boundaries

- `player_doTurn`: the actual CvPlayer function; it may contain synchronous `player_post_diplomacy` or defer that work for diplomatic input. Its other children include `ai_turn_pre`, `grand_strategy_ai`, and `diplomacy_ai`.
- `player_post_diplomacy`: includes `player_prepare`, `cities_and_production`, `player_yields_research_culture`, `ai_turn_post`, `player_unit_turn`, and other player-turn work. These are not disjoint with every enclosing scope.
- `player_prepare`: includes visible-world/area refresh, `player_danger_update`, `military_stats`, `economic_ai`, `military_ai`, `religion_trade_specialization_league_ai`, and applicable `minor_civ_ai`. Its remainder contains the unsplit preparation work.
- `ai_turn_pre`: includes `unit_power_sort` and `annex_raze_ai`.
- `ai_turn_post`: includes applicable `great_people_ai`, `espionage_ai`, and `trade_ai_post`.
- `player_unit_turn`: includes `unit_cleanup_pre`, aggregate `unit_doTurn_calls`, and `unit_promotions_garrison_post`. `unit_heal_reset` is measured wherever the separate unit-reset function is called.
- `unit_ai_update`: records real processing passes after the busy-unit/city guard. It includes existing diagnostic observation, `tactical_ai` or human visibility work, `homeland_ai`, and cleanup. It does not instrument animation polling or the pre-update Lua hook before the guard; remaining wall-clock gaps may need engine/callback analysis.
- `tactical_ai`: includes `tactical_visibility`, `tactical_targets`, `tactical_recruit`, `immediate_city_opportunities`, and `tactical_dominance`.
- `tactical_dominance`: includes `tactical_high_priority` (which contains `tactical_operations` and its `stacking_offensive_moves` child), aggregate `tactical_zone_attacks`, `tactical_reinforcements`, `tactical_mid_priority`, and `tactical_low_priority`, followed by unassigned-unit review. PLAN intervals can occur inside several of these children.

The replay should report per-player phase totals and inclusive maxima, distinguish repeated unit-AI passes, and retain unattributed time instead of forcing every millisecond into an AI label. Keep the same diagnostics/logging configuration and compare semantic decision/census outputs independently of new timer rows.

## Original VP work worth checking

### Unit sorting: exact repeated power evaluation

`CvPlayerAI::AI_doTurnPre` sorts `m_units` with `CompareUnitPowerAscending`. For unequal-power units, a comparison calls each unit's `GetPower()` twice: once for inequality, again for ordering. `CvUnit::GetPower` around7722 is a calculated value involving unit-info power, base combat/ranged strength, level, wounded modifiers, traits and currentHP; it is not just a stored integer read.

An exact candidate is computing power once per unit for the duration of this one sort and retaining the existing descending-power/ascending-ID order. Do not use a persistent power cache without complete health/promotion/owner invalidation. First inspect `unit_power_sort`; if it is negligible, adding a map/cache is unnecessary. A useful fixture compares the actual old/new sorting behavior over tied power, wounded units, different promotions and unit types, with game state unchanged during the synchronous sort. The root/forecast review is evaluating this separately; no sorting change is made here.

### Full-map preparation and visibility

`CvPlayer::UpdatePlots` scans the world to rebuild owned plots and update water flags. `UpdateAreaEffectPlots` can scan the world for a trait improvement and again for natural wonders. `UpdateAreaEffectUnits` scans the player's units and then updates city strength. `CvTacticalAI::UpdateVisibility` clears known visibility across the map, then scans the map again, deriving border and unit visibility. These are original routines; their existence is not evidence they dominate this map.

If `player_prepare` remainder or `tactical_visibility` is large, inspect exact reuse opportunities and existing ownership/visibility dirty tracking. Preserve captured/razed/transferred plots, improvements, natural-wonder effects, teams, delayed visibility and combat changes. Avoid skipping a refresh merely because it was also called earlier in the turn. A turn can contain relevant state changes between callers.

### Danger reconstruction and pathfinding

`CvPlayer::UpdateDangerPlots` invokes `CvDangerPlots::UpdateDanger`. The implementation has its own dirty/update policy, iterates other players and eligible units, and builds reachability through `GetAllPlotsInReachThisTurn`. Large campaigns can therefore spend time in original reach/path work outside PLAN searches.

If `player_danger_update` is dominant, profile rebuild counts, unit/plot expansions, and repeated equivalent source queries before designing a memo. Any reuse must preserve exact movement/ZOC, visibility, diplomacy, path flags, current terrain/roads, promotions and ignored/killed-plot state. A path key that omits those inputs can silently change military decisions. The earlier borrowed reachable-key optimization removed query copying while retaining full keys; it did not prove that every other path query is redundant.

### Economy and legacy logging

`CvEconomicAI::DoTurn` begins with LogMonitor, LogCityMonitor, LogBuildingYields, and LogReligionBeliefYields, then performs recon/antiquity and strategy evaluation. The building/religion logging functions immediately return when `MOD_SQLITE_LOGGING` is disabled. When enabled, they deliberately generate detailed city/building/yield or belief attribution records, including batched SQLite work. Do not assume these functions are enabled or blame their function names without `economic_ai` measurements and the active configuration.

If enabled legacy logging proves significant, optimize duplicated calculations, statement preparation or batching while preserving configured records and existing flags. Disabling existing logging would change the user's observability and would not constitute an exact gameplay-plus-logging optimization. Native stacking diagnostic format/write counters do not account for all other VP logging.

### Military planning and target evaluation

`CvMilitaryAI::DoTurn` scans barbarians, updates unit/base/defense data and strategies, evaluates attack targets, updates operations, makes eligible emergency purchases, and considers disbanding obsolete units. It also performs existing status/available-force logging. Current stack objective review is one additional child inside this older pipeline.

If `military_ai` is high, split its largest legacy functions in a subsequent bounded profile. Examine repeated immutable metadata/strength calculations and equivalent target/path evaluations; keep diplomacy, resource, health, army membership, city ownership and danger changes as invalidation boundaries. Avoid changing target budgets, strategic priorities or operation timing under the label of performance.

### City production, yields and ordinary unit turns

Aggregate `cities_and_production` covers ordinary city turns and production selection, including the existing spaceship/utopia override. City-specific AI can repeatedly evaluate buildings/units, flavor weights, supply and resources, production turns, religion and yields. City turns can finish production, capture/raze cities or alter policies/resources, so indiscriminate caching across cities or turns is unsafe. No city-level timer was inserted into this loop.

`player_yields_research_culture` separates treasury, culture/policy, science, espionage and faith/league work from city turns. `unit_doTurn_calls`, `unit_cleanup_pre`, `unit_promotions_garrison_post` and `unit_heal_reset` isolate original unit maintenance and promotion/reset routines. `homeland_ai` includes recruiting idle/civilian units, improvement planning, worker distribution, target selection and movement. Expensive worker/path behavior can be outside tactical combat even when a screenshot focuses on military units.

## Next decision after one measured replay

Rank exclusive parent remainders and large legacy child scopes for the preserved late-game position. Choose a small exact repeated calculation only where the measured phase justifies it. Verify actual source behavior and invalidation/lifetime assumptions offline, then compare a matched native replay's decisions, combat/captures and census. A speedup claim requires that replay; code inspection and fixture allocation/call-count reductions are supporting evidence only.

New timer fixture:26 actual-source VC9 checks. Existing diagnostic core75, events22 and global scheduling31 checks pass; prior broken scheduling/objective controls remain rejected. These confirm diagnostic plumbing and preserved tested scheduling, not complete-game equivalence or timer overhead in a native campaign.
