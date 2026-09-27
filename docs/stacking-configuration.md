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

Protection applies to new collateral, not ordinary city damage or existing garrison absorption. The secondary HP floor is independent and is applied after ordinary garrison absorption. CollateralPercent=0 disables new secondary damage; a 100% floor leaves no secondary allowance; a 0% floor permits secondary casualties. CityProtectionMaximumPercent=100 permits complete new-collateral immunity even when CollateralMinimumDamage is positive. The damage base is the calculated primary hit after combat modifiers but before overkill clamping. For example, a calculated primary hit of 30 yields base collateral 6. At 75% city protection this becomes 1 after integer rounding; a target with 53/100 HP can lose at most 3 HP, and a target already at 50/100 HP loses none.

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
| UIStackRosterOffsetY | 220 | 0–10000 | Panel vertical offset in UI coordinates; affects remaining viewport height. |
| UIStackFlagCollapseThreshold | 3 | 2–10000 | Occupant count before compact flags; Lua also enforces minimum 2. |
| UIStackResultDelayMilliseconds | 250 | 0–10000 | Delay before reporting group-move results; Lua converts milliseconds to seconds. |

The Lua UI reads raw database values rather than the DLL's clamped settings cache. Keep UI edits within the documented DLL ranges as well as the effective layout minimums above; out-of-range values are not guaranteed to behave identically in Lua and C++. Layout padding, icon size and text measurement are rendering constraints, not combat-balance settings. Restart after editing; full in-game UI hot reload has not been reliable with this VP/EUI setup.

## Built-in autoplay diagnostics

Open Additional Information > Stack diagnostics for Off, Summary or Verbose. Runtime overrides apply to the loaded session; after loading/restarting, XML defaults apply. Logging does not issue orders, consume RNG, or change gameplay search budgets. Existing VP AI logging remains a separate facility.

| XML setting | Default | Valid values | Meaning |
|---|---:|---:|---|
| DiagnosticsLevel | 0 | 0–2 | Off / Summary / Verbose; runtime menu overrides this until reload. |
| DiagnosticsSummaryInterval | 1 | 1–10000 | Sample each player's units before unit AI on these game turns, once per player/turn. |
| DiagnosticsDetailInterval | 10 | 0–10000 | Verbose unit/city snapshots; 0 disables scheduled detail. |
| DiagnosticsMemoryInterval | 10 | 0–10000 | Process virtual-memory sample once on matching turns; 0 disables. |
| DiagnosticsPlayer | -1 | -1–63 | Player ID filter; -1 includes all. Session/configuration/memory records are global. |
| DiagnosticsMaxFileKB | 4096 | 64–65536 | Maximum approximate size per rolling segment, including record overhead. |
| DiagnosticsMaxFiles | 8 | 1–32 | Segments retained per loaded session; reuse overwrites the oldest segment. |
| DiagnosticsMaxRowsPerTurn | 4096 | 32–65536 | Global event-row budget, followed by one TRUNCATED marker. Configuration headers are separate. |
| DiagnosticsHistogramMaxStack | 32 | 1–256 | Final histogram bucket includes this size and all larger sizes. This does not limit legal stacks. |
| DiagnosticsLongPlanThreshold | 256 | 0–10000 | Warn before an unusually long tactical history grows further; repeats at multiples. 0 disables. No action is blocked. |

The native logger writes immediately flushed, live-readable `Stacking-<UTC>-p<PID>-r<session>-<slot>.log` files in the game's Logs directory. Each segment identifies its run, monotonically increasing segment number and build. A configuration fingerprint is resolved in the first CONFIG record and carried by later segment headers. CONFIG_RAW rows record the stacking tables in database order; effective values still follow the validation/clamping described above. Off/on continues the same session and rolling budget. Reloads/new sessions have distinct prefixes; old sessions are retained for manual archiving/removal.

Summary includes unit/stack statistics, memory measurements, city-attack gates, recruitment counts, chosen-plan size/search time and long-history anomalies. Verbose adds unit/city identities, recruitment rejections, chosen assignments and score components, operation messages, and before/after combat participants with explicit inflicted-versus-received damage labels. Combat uses saved owner/ID lookups after resolution so captured/deleted units are handled safely. Unit composition is not a forecast of safety, an attempted-city-attack message is not proof an attack occurred, and missing units can have non-combat removal causes. No extra danger calculation is performed solely to populate logs.

Record timing and sampling duration include diagnostic overhead; bounded output can omit events, and TRUNCATED must be treated as incomplete evidence. Rotated records are not recoverable from the current session. The logger does not retain a whole-game history in memory and has no injected Lua observer. These limits control diagnostics only.
