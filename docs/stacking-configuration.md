# Stacking configuration

The user-facing configuration files are:

* `(1) Community Patch/Database Changes/StackingConfig.xml`: capacity, technology progression, roles, collateral, fortifications and AI tuning.
* `(2) Vox Populi/Database Changes/StackingVPConfig.xml`: VP's existing siege attack-strength modifier against land units, initially **-33%**. This updates `PROMOTION_SIEGE_INACCURACY` in `UnitPromotions_Domains`; it does not multiply final damage or change the siege city bonus.

`StackingSchema.sql` creates the custom tables before the first XML file loads. Both modinfo files and ModBuddy projects register their files. The rules compile into the existing VP gamecore DLL; a separate competing DLL is not needed.

## When changes apply

Edit the source XML, restage/deploy the mod files, fully restart Civilization V, activate the mods, and start a fresh test game. No DLL rebuild is needed for XML changes. A fresh game is the reliable way to apply changed database rules: existing VP saves may retain their saved gameplay database. Editing XML while a game is running does not refresh its database or these caches. Multiplayer participants must use identical DLLs and database settings.

Only database rules and resolved IDs are cached. `CvGlobals::cacheGlobals()` and `deleteInfoArrays()` invalidate that cache when gameplay data changes. Technologies, promotions and city building counts are read from current game state each time; acquiring technology, loading a later-era start, gaining a promotion or capturing/removing a building does not need a separate saved stacking counter.

If the schema is absent, the new rules are disabled. With the schema present, missing scalar settings use the documented defaults. Unknown references/roles/settings and clamped values are reported through VP's `CustomMods.log` diagnostic logging. Type references are resolved after the gameplay database has loaded, so CP's configuration can refer to VP units and buildings loaded later.

## Scalar settings

All these rows are in `Stacking_Settings(Name, Value)` and use integers. The DLL clamps recognized settings to their stated ranges and logs the adjustment. Boolean values are 0 or 1. `SAFE_INTEGER` below is `INT_MAX / 4`, or 536,870,911 in this 32-bit DLL; it is an overflow guard, not a practical gameplay limit.

| Name | Default | Meaning / range |
|---|---:|---|
| Enabled | 1 | Master switch for the new rules. |
| DefenderSelectionEnabled | 1 | Use the stack-aware best-defender comparison. |
| FlankingEnabled | 1 | Enable configured cavalry bypass and interception. |
| CollateralEnabled | 1 | Enable the new limited secondary damage. |
| AIEnabled | 1 | Enable new stack preference scores. At 0, collateral valuation uses neutral weight 100; occupancy, danger and combat rules still apply, so units can still choose useful stacks. |
| BaseCapacity | 2 | Initial combat-unit slots per land/sea domain; 1–SAFE_INTEGER. |
| MaximumCapacity | 9 | Maximum after all capacity additions; 1–SAFE_INTEGER. Values such as 10 require no C++ change. |
| LandCapacityBonus | 0 | Extra land slots before the maximum is applied; 0–SAFE_INTEGER. |
| SeaCapacityBonus | 0 | Extra sea slots before the maximum is applied; 0–SAFE_INTEGER. |
| CityCapacityBonus | 0 | Extra slots inside a city, still limited by MaximumCapacity; 0–SAFE_INTEGER. |
| MinorCapacityBonus | 0 | Additional city-state slots; 0–SAFE_INTEGER. |
| BarbarianCapacityBonus | 0 | Additional barbarian slots; 0–SAFE_INTEGER. |
| CollateralPercent | 20 | Percent of the calculated primary hit used as secondary damage; 0–100. |
| CollateralHPFloorPercent | 50 | Secondary victims retain at least this percentage of their own maximum HP; 0–100. |
| CollateralMinimumDamage | 1 | Minimum after protection/rounding when base collateral is positive and protection is below 100%, before the HP floor; 0–SAFE_INTEGER. |
| CityProtectionMaximumPercent | 90 | Cap on additive building protection; 0–100. A value of 100 deliberately permits complete protection. |

Capacity is `min(MaximumCapacity, BaseCapacity + domain bonus + city bonus + player-category bonus + researched technology bonuses)`. It uses the moving unit's owning team, never the plot owner's technology. City-states and barbarians use their own team's researched technologies plus their separate optional bonus. Civilian/support/air capacity rules remain separate. Callers retain VP's foreign-occupant legality checks.

Capacity and integer additions are bounded internally at `INT_MAX / 4` to prevent signed overflow. This is an arithmetic safeguard rather than a practical balance limit. Very large XML caps are not a promise of acceptable AI performance or UI usability.

### Technology rows

`Stacking_Technologies(TechType, CapacityBonus)` has one row per technology. Bonuses are clamped to 0–SAFE_INTEGER and are cumulative, independent of acquisition order. With the defaults:

| Technology | Bonus | Capacity if previous listed technologies are also owned |
|---|---:|---:|
| Start | — | 2 |
| TECH_IRON_WORKING | 1 | 3 |
| TECH_GUNPOWDER | 2 | 5 |
| TECH_MILITARY_SCIENCE | 2 | 7 |
| TECH_ROBOTICS | 2 | 9 |

There is no requirement to use those four technologies. Removing a row removes that bonus. Adding a row requires only a valid final-database technology Type. Primary keys prevent double-counting the same technology.

## Unit role mappings

These tables all contain the reference column below plus `Role` and integer `Value`:

| Table | Reference column |
|---|---|
| Stacking_UnitCombatRoles | UnitCombatType |
| Stacking_UnitClassRoles | UnitClassType |
| Stacking_PromotionRoles | PromotionType |
| Stacking_UnitRoles | UnitType |

Supported role names are case-sensitive:

* `FLANK`: Value 1 permits bypass. The attacker must still be a land combat unit capable of melee attack, not cargo. Mounted ranged skirmishers do not become melee flankers.
* `ANTI_CAVALRY`: Value 1 identifies a potential interceptor. Combat resolution still checks actual defense eligibility and chooses the best eligible interceptor.
* `FLANK_TARGET`: Value 1 identifies a vulnerable land combat unit. Archer and siege combat classes are the defaults.
* `COLLATERAL_LIMIT`: Value is the maximum secondary victims, from 0 to 32. Zero disables collateral for that mapping. Actual resolution also observes available engine damage-member slots.

Boolean role values (`FLANK`, `ANTI_CAVALRY`, `FLANK_TARGET`) are clamped to 0–1; `COLLATERAL_LIMIT` is clamped to 0–32.

Precedence is deterministic: combat-class default → class replacement → maximum of inherited value and all owned promotion values → explicit unit replacement. Thus an explicit `Stacking_UnitRoles` row with Value 0 can disable a role even if a promotion grants it. Promotion rows grant/increase roles; they do not remove them. A class Value 0 disables the combat-class default, but an owned promotion can still grant it.

Unique units in an existing class inherit its rules. Distinct unique classes inherit their combat-class defaults unless a class or unit row overrides them. For example:

```xml
<Stacking_UnitRoles>
  <Row UnitType="UNIT_HORSEMAN" Role="FLANK" Value="0" />
</Stacking_UnitRoles>
```

Default anti-cavalry mappings include spear/pike/tercio/rifle classes and Formation I, Formation II and Anti-Tank promotions. Mounted and armor combat classes receive the flanker role, subject to the melee requirement.

Default collateral limits are Catapult/Trebuchet 2, Cannon/Great Bombard 3, Field Gun 4, Artillery/Rocket Artillery 5; Liburna/Galleass 2, Frigate 3, Cruiser/Dreadnought 4, Battleship/Missile Cruiser 5; WWI Bomber 3, Bomber 4, Stealth Bomber 5. Unlisted siege/naval-ranged/bomber classes inherit 2/2/3 respectively.

`Stacking_CollateralDomains(DomainType, Enabled)` clamps Enabled to 0–1. Defaults enable DOMAIN_LAND and disable DOMAIN_SEA and DOMAIN_AIR. Enabling DOMAIN_SEA permits eligible naval victims, including ship-to-ship collateral from a configured ranged attacker. Domain permission does not bypass other eligibility checks: civilians, trade units, cargo, aircraft, primary defenders, non-enemies and embarked land targets are excluded. Consequently DOMAIN_AIR=1 does not currently make aircraft eligible. Bombing must reach the target: a successful positive-damage interception aborts the strike before new collateral. Air sweeps and nuclear attacks do not use the new bombing-collateral path. Existing VP adjacent-plot splash effects remain separate.

## City protection

`Stacking_BuildingClassProtection(BuildingClassType, ProtectionPercent)` gives every building of a class the specified protection. `Stacking_BuildingProtection(BuildingType, ProtectionPercent)` optionally replaces that inherited value for a specific building, including replacement by zero. Both protection tables clamp each percentage to 0–100. A building is counted once at its effective value, not once for the class and again for the override. Current real/free building counts are included. Multiple sources add before the overall cap.

Defaults are Walls 10%, Castle 15%, Arsenal 20%, Military Base 25%, and the Bomb Shelter class 30%, subject to the 90% combined cap. These are initial tunable values. A modded bunker can be added by its building or building-class Type; the configuration does not assume a nonexistent `BUILDING_BUNKER` identifier.

Protection applies to new collateral, not ordinary city damage or existing garrison absorption. The secondary HP floor is independent and is applied after ordinary garrison absorption. CollateralPercent=0 disables new secondary damage; a 100% floor leaves no secondary allowance; a 0% floor permits secondary casualties. CityProtectionMaximumPercent=100 permits complete new-collateral immunity at full city HP even when CollateralMinimumDamage is positive. With CityProtectionScalesWithHP=1, damaged cities receive proportionally less protection. The damage base is the calculated primary hit after combat modifiers but before overkill clamping. For example, a calculated primary hit of 30 yields base collateral 6. At 75% city protection this becomes 1 after integer rounding; a target with 53/100 HP can lose at most 3 HP, and a target already at 50/100 HP loses none.

## AI tuning

All AI tuning rows are in `Stacking_Settings`. The DLL uses the individual nonnegative ranges below.

| Name | Default | Range | Unit / purpose |
|---|---:|---:|---|
| AIStackProtectionWeight | 20 | 0–10000 | Score weight for protected composition. |
| AIStackJoinBonus | 12 | 0–10000 | Score points for joining a useful stack. |
| AIStackLeaveProtectorPenalty | 30 | 0–10000 | Score penalty for exposing a stack by leaving. |
| AIStackAntiFlankBonus | 12 | 0–10000 | Score points for relevant anti-cavalry protection. |
| AIStackCollateralWeight | 100 | 0–10000 | Percentage weight on forecast secondary damage; 100 is neutral. |
| AIStackConcentrationPenalty | 10 | 0–10000 | Score penalty per surplus member under collateral threat. |
| AIStackPairRecruitBonus | 25 | 0–10000 | Score bonus retaining protector/ranged pairs during recruitment. |
| AIStackConcentrationFreeUnits | 2 | 0–100 | Eligible stack members before concentration penalties begin. |
| AIStackPairRecruitRange | 1 | 0–10 | Hex distance when retaining protector/ranged pairs in recruitment. |

Existing tactical search limits remain bounded at their upstream defaults rather than scaling with stack capacity. These values tune preferences; shared eligibility, capacity, defender selection and damage forecasting establish which actions are legal.

## Military allocation settings

All 36 controls below are `Stacking_Settings` rows in the same XML file. These defaults are an initial test policy, not calibrated long-campaign balance. `AIEnabled` and `AIMilitaryAllocationEnabled` must both be enabled; ordinary human units and barbarians keep their existing controllers.

| Setting | Default | DLL range | Meaning |
|---|---:|---:|---|
| AIMilitaryAllocationEnabled | 1 | 0–1 | Enable this allocation policy; 0 restores legacy allocation hooks while retaining correctness fixes. |
| AICityApproachRadius | 6 | 1–8 | Hex radius of visible nearby enemies; this is proximity, not path reach. |
| AICityApproachWeight | 35 | 0–100 | Percent strength credit for nearby enemies absent from the immediate attack map. |
| AICitySafeDefenders | 1 | 0–10 | Land defenders in a safe ordinary city; early expansion can release this baseline. |
| AICityMaximumDefenders | 3 | 1–10 | Maximum reserved land defenders on the city tile, also limited by stack capacity. |
| AICityEmergencyDefenders | 2 | 1–10 | Minimum when the city reports siege or danger of falling, capped by available capacity. |
| AICityMaximumNavalDefenders | 2 | 0–10 | City-held naval reserve cap when visible naval pressure exists; zero without naval pressure. |
| AICityStrengthCreditPercent | 50 | 0–100 | Percent of health-adjusted city strength credited against required land defense. |
| AICityDefenseStrengthPercent | 120 | 50–300 | Percent of assessed enemy strength desired before city-strength credit. |
| AICapitalDefensePercent | 125 | 100–300 | Multiplier on a threatened capital's remaining strength requirement. |
| AIGarrisonRangedBonus | 20 | 0–100 | Additive strength-score bonus for ranged, non-siege defenders. |
| AIGarrisonReplacementPercent | 20 | 0–100 | Minimum percentage improvement for a replacement at an already adequately defended threatened city. |
| AIAssemblyNoProgressTurns | 3 | 1–10 | Stationary turns before clearing the path; twice this interval before releasing a straggler. |
| AIFailedAssignmentCooldown | 3 | 0–10 | Future turns before retrying the same failed objective (also blocks the release turn). |
| AIRecruitmentReviewTurns | 5 | 1–30 | Operation age before considering an incomplete but viable formation. |
| AIAssemblyMinimumCombatUnits | 4 | 2–20 | Minimum members for relaxed formation readiness. |
| AIAssemblyRequiredPercent | 75 | 50–100 | Percentage of required slots filled for relaxed readiness. |
| AIAssemblyMaximumMissing | 1 | 0–3 | Maximum missing required slots for relaxed readiness. |
| AIAssemblyMinimumRanged | 2 | 0–10 | Required ranged support count for relaxed readiness, in addition to a capturer. |
| AIAssemblyStrengthPercent | 150 | 100–300 | Minimum own strength percentage relative to the visible city and nearby defenders. |
| AIAssemblyStallReviewTurns | 12 | 6–40 | Consecutive observed turns without added members or shorter furthest-member distance before abort/reassignment. |
| AIReassignmentCooldown | 3 | 0–10 | Retention window for transfer intent/inbound credits; not a hard ban on emergency reassignment. |
| AIReassignmentContinuityBonus | 40 | 0–300 | Score preference for continuing the same reinforcement goal. |
| AIReinforcementUnitsPerTurn | 8 | 0–32 | Maximum successful strategic reserve transfers per player/game turn; 0 disables. |
| AIReinforcementPathQueriesPerTurn | 32 | 0–128 | Maximum strategic target ETA queries per player/game turn; execution revalidates the selected path. |
| AIReinforcementMaximumTargets | 8 | 1–32 | Maximum prioritized demands considered per candidate unit. |
| AIReinforcementMaximumTurns | 12 | 1–30 | Maximum estimated travel turns; native-domain paths forbid embarkation. |
| AIReinforcementTravelWeight | 15 | 1–100 | Demand score penalty per estimated travel turn. |
| AIReinforcementDefensePriority | 300 | 1–1000 | Base score for a local city-defense strength deficit. |
| AIReinforcementAttackPriority | 200 | 1–1000 | Base score for reinforcement of an active offensive army. |
| AIRearCityPlotScore | 6 | 0–12 | Tactical position score for healthy surplus troops in cities at least three enemy-distance bands from contact. |
| AIRearCityHealthyPercent | 70 | 1–100 | HP percentage above which rear-city preference is reduced. |
| AICityAssaultMinimumSiege | 1 | 0–4 | Desired nearby bombard-role units before an otherwise dominant land siege stops requesting that role. |
| AIPatrolCurrentZoneBonus | 20 | 0–1000 | Bounded current-zone preference instead of unconditional acceptance. |
| AIOffensiveOperationsPerDomain | 2 | 0–6 | Maximum concurrent offensive operations separately for land and sea; mixed naval operations use sea. |
| AIOffensiveReserveMinimumUnits | 4 | 1–20 | Minimum eligible healthy unassigned units in that domain before a new operation is considered. |

Assessment reuses VP's immediate attack map, plus currently visible enemies in a bounded proximity band. Strength is a health-adjusted base combat/ranged proxy for strategic allocation, not predicted combat damage. Existing tactical simulation still evaluates actual defender, flank and collateral rules. A capital bonus only applies when an enemy threat is observed. No full multi-turn invasion/air campaign model is added.

City defenders are reconsidered against the units actually present. An adequate rear city stops seeking redundant replacements; wounded/army-bound units can be freed when another defender is adequate. Strategic transfers retain civilian escorts, healing troops, engaged units and necessary nearby field defenders. A transfer arrival means within the existing two-hex native-domain staging tolerance, not that the unit attacked or joined a formation. Successful arrivals enter normal local/operational selection on later turns.

Incomplete-formation readiness additionally requires a currently visible target city and a city-capturing unit. It advances to gathering, with ordinary movement/access/cohesion rules still applied. No deadline alone authorizes an assault. Per-unit progress uses position and ETA; active danger, healing and already assembled units receive grace. Whole assembly recovery is separate and only affects recruiting/gathering offensive operations.

Planning histories contain owner/ID references, not retained unit pointers. They are bounded, transient and reset on load, including same-process reloads. Old saves keep their format, but timers/intent start fresh after load. The per-turn threat snapshot is conservative after enemies are destroyed and can lag discoveries later in that turn. Broader memory of threats, role-specific multi-front allocation, naval landings and air coordination remain follow-up work.

## Engine constraints and diagnostics

The existing `CvCombatInfo` interface has 32 damage-member entries. This layout is shared with the closed game executable and is not enlarged. Collateral selection must stop at available slots, merge a pre-existing garrison entry and preserve the HP floor. The numeric role validator therefore caps victim limits at 32. This is an engine-layout constraint, distinct from the XML default stack cap of 9.

No new serialized unit, player or team fields are introduced by the configuration layer. The unit/team technology and city building state already saved by VP reconstruct capacity and protection after load.

The `Core Files/Stacking/*Tests.lua` helpers are manual imports, not automatically executed UI add-ins. Importing/loading the AirWave helper only defines functions; its setup must be explicitly invoked in a disposable game. Never use destructive scenario setup against a valued save.

## Stack UI settings

These `Stacking_Settings` values control the optional stack roster and Move Stack action. Dimensions and offsets use Civ V UI coordinates; their physical size depends on interface/display scaling. Restart the game after editing.

| Setting | Default | DLL range | Effective UI behavior |
|---|---:|---:|---|
| UIStackEnabled | 1 | 0–1 | Enable the stack panel/compact flags. |
| UIStackMoveMinimumUnits | 2 | 2–10000 | Owned members needed for Move Stack; Lua also enforces minimum 2. |
| UIStackRosterWidth | 360 | 1–10000 | Width in UI coordinates; Lua enforces minimum 260. |
| UIStackRosterRowHeight | 38 | 1–10000 | Requested minimum row height; initial Lua minimum 32, populated rows at least 40 for a 32px icon plus padding, and taller when measured text needs room. |
| UIStackRosterMaximumHeight | 430 | 1–10000 | Scroll viewport cap; at least the initial row-height setting, and constrained by remaining screen height. Rows remain scrollable. |
| UIStackRosterOffsetX | 110 | 0–10000 | Panel horizontal offset in UI coordinates. |
| UIStackRosterOffsetY | 220 | 0–10000 | Baseline vertical offset in UI coordinates. When combat preview is visible, the roster rises above its measured bounds and the viewport shrinks to fit. |
| UIStackFlagCollapseThreshold | 3 | 2–10000 | Occupant count before compact flags; Lua also enforces minimum 2. |
| UIStackResultDelayMilliseconds | 250 | 0–10000 | Delay before reporting group-move results; Lua converts milliseconds to seconds. |

The Lua UI reads raw database values rather than the DLL's clamped settings cache. Keep UI edits within the documented DLL ranges as well as the effective layout minimums above; out-of-range values are not guaranteed to behave identically in Lua and C++. Layout padding, icon size and text measurement are rendering constraints, not combat-balance settings. Restart after editing; full in-game UI hot reload has not been reliable with this VP/EUI setup.

## Built-in autoplay diagnostics

In observer mode or during autoplay, click Diagnostics near the top center of the map for Off, Summary or Verbose. The button hides during normal play. Press **Ctrl+Shift+D** on the map to open the same controls in normal play, select Summary/Verbose/Off, then press the shortcut again or Escape to close them. `UIStackDiagnosticsHotkeyEnabled=0` disables this shortcut. XML DiagnosticsLevel or the Game Lua bindings can also enable logging there. Returning to normal play does not change the logging level. Runtime overrides apply to the loaded session; after loading/restarting, XML defaults apply. Logging does not issue orders, consume RNG, or change gameplay search budgets. Existing VP AI logging remains a separate facility.

| XML setting | Default | Valid values | Meaning |
|---|---:|---:|---|
| DiagnosticsLevel | 0 | 0–2 | Off / Summary / Verbose; runtime menu overrides this until reload. |
| DiagnosticsSummaryInterval | 1 | 1–10000 | Sample each player's units before and after the first unit-AI pass on these game turns, once per phase/player/turn. Operation snapshots use the same interval. |
| DiagnosticsDetailInterval | 10 | 0–10000 | Verbose unit/city snapshots; 0 disables scheduled detail. |
| DiagnosticsMemoryInterval | 10 | 0–10000 | Process virtual-memory sample once on matching turns; 0 disables. |
| DiagnosticsPlayer | -1 | -1–63 | Player ID filter; -1 includes all. Session/configuration/memory records are global. |
| DiagnosticsMaxFileKB | 4096 | 64–65536 | Maximum approximate size per rolling segment, including record overhead. |
| DiagnosticsMaxFiles | 8 | 1–32 | Segments retained per loaded session; reuse overwrites the oldest segment. |
| DiagnosticsMaxRowsPerTurn | 4096 | 32–65536 | Global event-row budget, followed by one TRUNCATED marker. Configuration headers are separate. |
| DiagnosticsHistogramMaxStack | 32 | 1–256 | Final histogram bucket includes this size and all larger sizes. This does not limit legal stacks. |
| DiagnosticsLongPlanThreshold | 256 | 0–10000 | Warn before an unusually long tactical history grows further; repeats at multiples. 0 disables. No action is blocked. |

The native logger writes bounded-buffered, live-readable `Stacking-<UTC>-p<PID>-r<session>-<slot>.log` files in the game's Logs directory. Each segment identifies its run, monotonically increasing segment number and build. A configuration fingerprint is resolved in the first CONFIG record and carried by later segment headers. CONFIG_RAW rows record the stacking tables in database order; effective values still follow the validation/clamping described above. Off/on continues the same session and rolling budget. Reloads/new sessions have distinct prefixes; old sessions are retained for manual archiving/removal.

Summary includes unit/stack statistics, memory measurements, city-attack gates, recruitment counts, chosen-plan size/search time and long-history anomalies. Summary now also includes compact combat outcomes/city-health changes, observed combat captures, operation staffing/production status, and first-unit-AI-pass logging cost. Verbose adds unit/city identities, recruitment rejections, chosen assignments and score components, operation messages, and before/after combat participants with explicit inflicted-versus-received damage labels. Combat uses saved owner/ID lookups after resolution so captured/deleted units are handled safely. Unit composition is not a forecast of safety, an attempted-city-attack message is not proof an attack occurred, and missing units can have non-combat removal causes. No extra danger calculation is performed solely to populate logs.

Record timing and sampling duration include diagnostic overhead; bounded output can omit events, and TRUNCATED must be treated as incomplete evidence. Rotated records are not recoverable from the current session. The logger does not retain a whole-game history in memory and has no injected Lua observer. These limits control diagnostics only.

## Observer notification lifetime

`UIObserverNotificationLifetimeTurns` in `Stacking_Settings` defaults to **3**; **0** disables automatic dismissal. The VP EUI notification panel clamps it to an integer from 0 to 10000. This is a UI-only setting, not a DLL tuning value. It operates independently of the stack roster toggle.

In observer mode or autoplay, displayed notifications become eligible for ordinary dismissal when the current game turn minus their saved creation turn reaches the configured lifetime. A message from turn 280 is eligible at turn 283. Reloading a save or switching the observed view does not renew a message's age. Individual older entries are removed from bundles while newer entries remain. The notification history is retained by VP's ordinary notification system.

Normal play is unaffected. Native mandatory-choice notifications retain the same restrictions as manual right-click dismissal. The check is event-driven and throttled by active player/game turn; it sends no gameplay orders. Restart into the modded game after changing the XML/UI files. The implementation targets this prototype's tested VP EUI compatibility panel; non-EUI and network observer behavior have not been validated.

### Diagnostic efficiency, filters and hidden access

| Setting | Default | Range | Behavior |
|---|---:|---|---|
| DiagnosticsImmediateFlush | 0 | 0–1 | 1 restores unbuffered per-record output for crash investigations; 0 enables batching. |
| DiagnosticsBufferKB | 64 | 4–256 | Active CRT file buffer size. Fixed storage has a 256 KiB maximum; no unbounded queue or background thread. |
| DiagnosticsFlushEveryRows | 256 | 1–8192 | Flush after this many pending writes; CRT buffer capacity can flush earlier. |
| DiagnosticsFlushIntervalMilliseconds | 1000 | 0–60000 | Check elapsed time on each write and flush if due. 0 disables this time trigger, not boundary/row-trigger flushing. |
| DiagnosticsCategoryMask | 63 | 0–63 | Sum evidence-family bits listed below. Metadata and safety anomalies remain available. |
| DiagnosticsVerboseStartTurn | -1 | -1–536870911 | First inclusive game turn for level-2 events; -1 leaves the lower bound open. |
| DiagnosticsVerboseEndTurn | -1 | -1–536870911 | Last inclusive game turn for level-2 events; -1 leaves the upper bound open. Summary continues outside the window. |
| DiagnosticsCombatSummary | 1 | 0–1 | One compact outcome per combat at Summary/Verbose. 0 skips compact outcomes; Verbose brackets can still be enabled. |
| DiagnosticsPerformanceInterval | 1 | 0–10000 | Record logger costs and elapsed time for the first unit-AI pass on these turns. 0 disables cost records. |
| UIStackDiagnosticsHotkeyEnabled | 1 | 0–1 | Enable Ctrl+Shift+D map shortcut; the normal-play button remains hidden. |

`DiagnosticsCategoryMask` uses: **1** unit/stack/city snapshots; **2** military allocation, objectives, capture plans and operation status; **4** tactical recruitment and chosen plans; **8** compact/detailed combat and observed captures; **16** performance/cost; **32** virtual-memory samples. Add the bits you want: **63** keeps all families, **26** selects military + combat + cost, and **2** isolates military decisions. Disabled snapshot/combat families skip their extra collection; disabled tactical assignment detail skips enumeration. When produced, critical LONG_PLAN/ANOMALY records retain their existing level/player rules regardless of this mask; disabling a collection pass also disables anomalies detected only by that pass. Configuration, level, and truncation metadata are not category-filtered.

Output is flushed at player sampling/AI-pass boundaries, combat boundaries, rotation, level changes and explicit `Game.FlushStackingDiagnostics()`. Detailed pre-combat brackets and long-plan/anomaly warnings are flushed immediately. Threshold checks happen during logging, without an idle timer. A process crash can lose the last pending batch outside those boundaries; use `DiagnosticsImmediateFlush=1` when reproducing a crash. Flushing the CRT buffer makes data readable by live tools; it does not request an OS-level disk durability barrier.

For a long autoplay, start with **Summary**, all categories, and buffered output. If snapshots are expensive, set `DiagnosticsSummaryInterval=5`; both structural snapshots and operation snapshots honor it. Event decisions/combat still record each relevant event. For a specific issue, use Verbose with `DiagnosticsPlayer` and a bounded turn window. The selected player filter now includes combat where that player is a defender or bystander; `attackerOwner` preserves the actual aggressor.

`OPERATION_STATUS` records current state, stored target/muster waypoints, formation occupancy, queued and in-training counts, and age. A naval target waypoint can be a water hex beside the city. It never refreshes production requests or runs pathfinding. `COMBAT_SUMMARY` records rolled primary/retaliation damage, bystander totals, observed HP loss for still-present identities, missing identity count, city HP/ownership and pre-hit fortification protection. Bystanders include ordinary garrison absorption; their total is not isolated collateral damage. Missing identities are not asserted deaths. `CITY_CAPTURE` records an observed combat ownership change on a city plot; it does not cover gifts, trades or every possible transfer.

`DIAGNOSTIC_COST` measures elapsed time and logger record/byte/drop/explicit-flush counters between before/after hooks for the **first unit-AI pass**. It excludes the structural snapshots, its own row and later passes; it is not complete turn time or pure AI CPU time. Millisecond ticks are coarse, `writeMs` can include CRT buffer flushes, and other threads can contribute to the shared logger counters. These observations help select a live profiling window without adding AI calculations.

For console/tool use in any game mode:

```lua
Game.SetStackingDiagnosticsLevel(1) -- Summary; 2 Verbose, 0 Off
Game.FlushStackingDiagnostics()    -- Publish pending records without changing level
```

### Military allocation diagnostic records

Summary adds `CITY_DEFENSE`, `OPERATION_BUDGET`, `OPERATION_READINESS`, `OPERATION_ASSEMBLY`, `ASSEMBLY_STALL`, `GARRISON_ASSIGN`, `REINFORCEMENT`, `SIEGE_REINFORCE` and `DECISION_SUMMARY`. The last observes the first completed unit-AI pass, not final end-turn state; its counts overlap. Verbose adds retention/recruitment reasons, stationary-unit history, blocked transfers and periodic `UNIT_DECISION` snapshots. The existing row and file bounds still apply; Summary is recommended for continuous autoplay, Verbose for detailed problem windows.

The offline summarizer's `military.players` output keeps city/operation identities separate per player, shows actual moved/unchanged/absent garrison outcomes, reinforcement moving/arrived/failure counts, unique observed arrival units and assembly ages/recovery actions. An absent unit is not automatically a casualty. Missing/truncated/rotated records are never treated as proof that no action occurred.


## Offensive continuity and damaged fortifications (2026-09-29)

All controls remain in `StackingConfig.xml`. The new pass keeps the tactical 13-unit / 6,000-state limits unchanged.

| Setting | Default | Range | Meaning |
|---|---:|---|---|
| CityProtectionScalesWithHP | 1 | 0–1 | Scale capped fortification protection by city HP before the hit; 0 restores legacy behavior. |
| UIStackCombatPreviewGap | 8 | 0–100 | Gap above the measured combat panel, including its outcome banner, in UI coordinates. |
| AIOffensiveSupportEnabled | 1 | 0–1 | Enable this offensive continuity pass; requires AIEnabled and AIMilitaryAllocationEnabled. |
| AIWarPreparationEnabled | 1 | 0–1 | Gate voluntary city-attack declarations on readiness and retain the prepared army through declaration. |
| AIWarOpeningMaximumTurns | 3 | 1–10 | Approximate potential-war route horizon using army path length and unit base movement. |
| AIWarOpeningMinimumUnits | 4 | 2–20 | Minimum healthy units within opening range. |
| AIWarOpeningReadyPercent | 75 | 50–100 | Minimum fraction of the army within opening range. |
| AIWarOpeningMinimumRanged | 1 | 0–10 | Minimum ranged members in the staged core. |
| AIWarOpeningStrengthPercent | 150 | 100–300 | Staged strength relative to visible target city and nearby defenders. |
| AIOffensiveSupportMaximumObjectives | 8 | 1–24 | Maximum remembered city/domain objectives per player. |
| AIOffensiveSupportMemoryTurns | 12 | 2–40 | Expire a handed-off objective after this many turns without a tactical siege observation. |
| AIOffensiveSupportMinimumUnits | 6 | 2–24 | Baseline desired force, bounded by the maximum. |
| AIOffensiveSupportMaximumUnits | 18 | 4–40 | Hard cap on assigned, local, travelling and in-training combat-unit credit per objective/domain. |
| AIOffensiveSupportReserveUnits | 2 | 0–8 | Extra desired reserves above the largest observed core. |
| AIOffensiveSupportStrengthPercent | 150 | 100–400 | Desired strength relative to visible defenders before the reserve allowance. |
| AIOffensiveSupportReservePercent | 25 | 0–100 | Base strength reserve allowance. |
| AIOffensiveSupportTravelReservePercentPerTurn | 2 | 0–10 | Extra reserve percent for each approximate turn from staging to target. |
| AIOffensiveSupportMaximumReservePercent | 60 | 0–200 | Cap on the base plus travel reserve allowance. |
| AIOffensiveSupportMinimumCapturers | 2 | 1–6 | Desired melee capture-capable units; actual siege feasibility separately checks paths. |
| AIOffensiveSupportMinimumRanged | 2 | 0–8 | Desired ranged support units. |
| AIOffensiveSupportLocalRadius | 4 | 2–6 | Radius for field-force credit and the front_arrival diagnostic; not proof of combat contribution. |
| AIOffensiveSupportStallTurns | 5 | 2–20 | Expire a unit reservation when it has made no movement/ETA progress beyond this interval. |
| AIOffensiveSupportRolePriority | 80 | 0–300 | Extra demand priority for a missing capture or ranged role. |
| AIOffensiveProductionMaximumUnits | 2 | 0–6 | Maximum pending production requests plus units in training for a moving formation; 0 disables new requests. |
| AIOffensiveProductionMaximumTurns | 12 | 1–30 | Maximum production plus approximate travel lead time for a moving formation request. |
| AICapturePlanMaximumTurns | 6 | 1–15 | Actual unit-path horizon to a native-domain tile adjacent to a city, with safe embark paths allowed for assessment. |
| AICapturePlanPathQueriesPerTurn | 32 | 1–128 | Per-player cap on capture path queries; exhausted budget means unknown, not impossible. |
| AICapturePlanMinimumHPPercent | 60 | 1–100 | Health floor for counting a capture-capable unit. |
| AISiegeNoCaptureReviewTurns | 8 | 2–30 | Missing-capture grace period before reviewing futile fire. |
| AISiegeNoCaptureLowHPPercent | 25 | 0–100 | Only suppress city fire below this city-health threshold when no viable capturer or useful collateral exists. |
| AIOperationRouteRetryTurns | 6 | 0–30 | Target/domain retry cooldown after LostPath or moving-phase timeout; 0 disables it. |
| AIOperationRouteRepairCandidates | 4 | 0–16 | Maximum distinct actual army-unit origins to try after a centroid route fails. |
| AIOperationMovingStallTurns | 12 | 4–40 | No-improvement deadline for a march away from its deployment area. |
| AIOperationContactStallTurns | 20 | 6–60 | Longer no-improvement deadline after an actual opportunity attack. |
| AIOperationContactHoldPercent | 50 | 0–100 | Hold the core if this fraction remains exposed after opportunity combat; otherwise unused safe members can advance. |

Fortification timing is **before each hit**. Sum building protection, cap it, then multiply by current city HP / maximum HP and round down. Simulated prior city damage is included in offensive and defensive multi-hit forecasts. The primary shot has not yet reduced protection for its own collateral. A 90% cap gives 90/45/0 protection at full/half/zero city HP. The unit HP floor, existing siege penalty, normal garrison absorption and city damage are independent.

Native `WAR_READINESS`, `WAR_DECLARATION`, `OPERATION_ROUTE`, `OPERATION_PROGRESS`, `OPERATION_CONTACT`, `CAPTURE_PLAN`, `CAPTURE_CANDIDATE`, `SIEGE_REASSESS`, `OFFENSIVE_OBJECTIVE` and `OFFENSIVE_SUPPORT` are Summary records. Candidate route rejections and per-candidate `OFFENSIVE_DEMAND` are Verbose. The existing logger limits and player filter apply. `joined_formation` is distinct from a front/staging arrival; neither alone proves useful combat.

Readiness uses intended-enemy army routes (respects third-party borders), not a precise future movement simulation. Capture assessment uses legal unit paths and simulated retaliation against a softened city. Strategic dispatch remains native-domain/no-embark; safe crossings may be recognized without this pass constructing an escorted landing. Existing VP naval/combined invasions and tactical landing code remain responsible for that movement.

Objective, failed-route, progress and free-unit reservation histories are transient and reset on load. Active operations reconstruct objectives; tactical siege observations reconstruct handed-off objectives. A reload can therefore change retry timing or free-reserve choices; no exact replay equivalence is claimed. Existing operation production reservations remain serialized by VP. Completed production uses VP's existing army assignment path. This pass does not create a separate production queue beyond formation slots, a full attrition predictor, or a wounded-unit rotation scheduler.
