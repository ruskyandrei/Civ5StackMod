# Typed lookup for hot stacking settings

`CvStacking::GetIntByKey` reads24 frequently used XML settings through fixed value/presence arrays in the existing `RulesCache`. Known constant calls in capacity rules, combat selection/collateral and tactical stack scoring use this path. It removes repeated tree traversal and text comparisons. The existing string map already avoided temporary-string allocations; the typed lookup adds no heap storage for queries or forecast-cache entries.

The public string `GetInt(const char*,int)` body remains unchanged. Dynamic callers retain null, empty, unknown, case-sensitive and UTF-8 name behavior and their caller-specific fallbacks. All24 settings keep their XML names, defaults, ranges and override rules. The enum is an internal C++ lookup key; it is not serialized or used as an XML ID.

| Purpose | XML settings |
| --- | --- |
| Selection and feature switches | `DefenderSelectionEnabled`, `FlankingEnabled`, `CollateralEnabled`, `DisableCityRangedAttacks`, `AIEnabled` |
| Capacity | `BaseCapacity`, `MaximumCapacity`, `LandCapacityBonus`, `SeaCapacityBonus`, `CityCapacityBonus`, `MinorCapacityBonus`, `BarbarianCapacityBonus` |
| Collateral | `CollateralPercent`, `CollateralHPFloorPercent`, `CollateralMinimumDamage` |
| City protection | `CityProtectionMaximumPercent`, `CityProtectionScalesWithHP` |
| Tactical scoring | `AIStackCollateralWeight`, `AIStackProtectionWeight`, `AIStackJoinBonus`, `AIStackAntiFlankBonus`, `AIStackConcentrationFreeUnits`, `AIStackConcentrationPenalty`, `AIStackLeaveProtectorPenalty` |

The original database loader populates and clamps the string map first. It finalizes the indexed arrays only after its existing last log call. Reentrant queries during schema checks, row processing and logging therefore delegate once to the original string getter and observe its exact partial state. Missing-schema completion records absent settings, preserving each typed caller's fallback. A missing database remains retryable. Invalid enum keys follow the original null-name/fallback path. Reset clears readiness and every value/presence cell, and the next load rebuilds them from XML.

Only database settings are mirrored. Capacity still reads current technology unlocks; role checks still read current promotions; city protection still reads current buildings and city HP. Unit movement, combat arithmetic, candidate order, search limits and cache capacities remain unchanged. The mirror's raw value/presence/readiness fields occupy121 bytes before structure padding and add no save-game fields. It follows the existing cache's loading/thread contract; it does not add a new concurrency guarantee.

`work/test-hot-stacking-settings.py --production --no-benchmark` binds the four affected production files to the exact reviewed mirror-only delta from commit `8aac77ca7`. It compiles the current loader, reset and getter bodies with genuine x86 VC9 and deterministic database services. **3,985 checks** and **24,075 reentrant probes** passed. Coverage includes all defaults/min/max XML clamps, Enabled mirroring, database/schema failures, reload/reset, transient row-text lifetime, pointer aliases, unknown names, invalid enum values and caller-specific missing-setting fallbacks. The production binding does not repeat timing.

The separate staged, uninstrumented benchmark used another translation unit without link-time inlining. Across three rounds of four million warmed calls, string lookup took96.6–100.3ms and indexed lookup took5.94–6.38ms, with equal results. That is roughly23ns per call in this synthetic workload—about half a second for22million calls alone. It establishes a modest computational opportunity, not an in-game turn-time result. Matched native actions, censuses and timing remain the validation for the deployed DLL.

Production binding result: `work/hot-stacking-settings-production-regression/result.json`. Historical staged timing: `work/hot-stacking-settings-regression/result.json`.
