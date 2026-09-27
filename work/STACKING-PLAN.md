# Civ5StackMod — implementation and verification plan

Prepared 2026-09-26. Implementation authorized and started 2026-09-26. Core configuration, capacity, combat and AI work is active; runtime verification is required before claiming completion.

## Confirmed scope and authorization

- Extend the existing Vox Populi DLL and retain VP's other systems.
- General configuration requirement: expose every new mechanic's tunable numbers and data mappings in XML wherever feasible. This includes limits, percentages, thresholds, bonuses, applicable technologies, unit/building eligibility and progression tables. Changing these settings must not require recompiling the DLL. Document any unavoidable engine constraints or exceptions explicitly.
- XML-configurable combat-unit stacking, starting at 2 and increasing through four technology unlocks to a default maximum of 9. The user's revised bonuses supersede the earlier ten-unit default.
- Capacity is per land/sea domain, including cities. Civilians/support units and aircraft keep their separate rules.
- Ranged units can fire while stacked. Units retain their own HP, movement and attacks.
- AI must understand actual stack occupancy, combat outcomes and protection, and deliberately make useful stacks.
- For each normal attack, the stack selects its best eligible defender for that particular attack. There is no mandatory melee-first priority; melee units are expected to win the comparison in many situations. This can be reviewed after testing.
- Cavalry bypass must be stopped by eligible anti-cavalry units.
- Siege, bomber attacks and ranged naval bombardment of ground stacks cause limited secondary damage.
- Collateral is 20% of the primary hit's damage and cannot reduce a secondary target below 50% of that target's maximum HP. Direct damage is separate.
- Retain VP's existing siege penalty initially: -33% attack strength against land units. The user selected this instead of replacing it with a 50% final-damage multiplier. Preserve city damage.
- Siege and bomber attacks on cities also inflict collateral on eligible units inside. Applicable fortifications provide additive, XML-configurable collateral protection, capped at 90% in total. Walls, castles, military bases, bunkers and other qualifying sources can contribute.
- Once the user gives the go-ahead, rebuilding/deploying test DLLs, launching/closing Civ V, using FireTuner with fresh games, and reversible toolchain work are authorized. Preserve saves, working backups and the user's windowed display settings.
- UI stretch goal: make stacks of up to 10 units easy to inspect and add a Move Stack button when two or more player-controlled units share a tile. Move eligible members toward the chosen hex and leave units that cannot perform the move behind, with clear advance feedback where possible. The normal default cap remains 9; ten-unit UI support also covers XML overrides.

## Design decisions resolved

The user confirmed best-defender selection across eligible combat units, with cavalry flanking and anti-cavalry interception as exceptions. City bombardment causes collateral, reduced by stacking fortification protection up to 90%. The separate collateral HP floor remains 50% of each secondary unit's maximum HP. Exact building protection values will be configurable and tuned during implementation/testing.

## Baseline dependency

Source is Release-5.4.6 at dcb33a654cd9e8efb038a0733b4025e19cbcd8ba. GitHub still lists 5.4.6 as latest stable at this research pass.

Update 2026-09-26: native MSVC Debug compiled successfully in about 25 seconds and passed the user-driven runtime smoke test: fresh map, several turns, save/reload and another turn. Loaded DLL hash, fresh startup log and AI turn 007 records agree. No new crash dumps/assertions were observed. The verified local DLL is currently installed. See work/BASELINE-VERIFIED.md and work/test-runs/native-debug-20260926/result.json.

Native build status (2026-09-26 23:41): work/build-vp.ps1 now invokes MSVC, default Debug. Optimized Release builds succeed with /MD /Z7 /Ox /Zm400 and no LTCG; latest233651 source-input hashes verified. Runtime release validation remains pending. Historical Clang initialization1114 and old Release PCH/link failures are retained in work logs, not the current build path.

Reference: https://github.com/LoneGazebo/Community-Patch-DLL/blob/Release-5.4.6/docs/build-toolchain.md

## Proposed XML defaults

XML is the user-facing configuration layer for all new mechanics, not just selected settings. SQL may establish database tables/columns and the DLL may implement behavior, but ordinary balancing and changing which technology, unit class, promotion or fortification supplies a benefit should be possible by editing XML. Keep a documented configuration reference with defaults, units, valid ranges and when a setting takes effect (for example, a new game or a save reload).

At minimum expose:

- Base stacking capacity, overall maximum and any city/domain-specific adjustments.
- Technology IDs and their stacking-capacity bonuses. Bonuses are cumulative: base capacity plus the sum of bonuses from researched technologies, subject to the XML-configured overall maximum. Both unlocks and bonus amounts can be changed without editing C++.
- Unit classes/promotions eligible for flanking, anti-flanking, collateral or other new roles, including unique-unit overrides.
- Collateral percentage, HP floor, victim limits by unit/tier, applicable target domains and any minimum-damage/rounding setting introduced by the mod.
- Fortification/building IDs, protection percentages and the combined protection cap (default 90%).
- Any newly added combat modifiers, AI scoring weights, tactical thresholds and search limits that are appropriate for tuning.
- Feature toggles for new optional mechanics where practical.

Load and cache these values through the game database. Validate settings, provide documented defaults and actionable errors for invalid references/ranges, and apply the same values to combat, previews and AI. If a numeric bound is an unavoidable engine/storage constraint, distinguish it from a balance setting and explain it in the configuration reference. Do not silently leave new balance constants hard-coded in C++ or Lua.

The following technology IDs and positions were checked against VP's local TechTreeSweeps.sql. Military Science (TECH_MILITARY_SCIENCE) is in Industrial tier 2, matching the requested late-Industrial/early-Modern timing. Use cumulative bonuses, counting each researched technology once, independently of acquisition order. Reconstruct correctly after save/load and later-era starts; do not double-apply bonuses when caches are rebuilt.

| Unlock | Era | Bonus | Cumulative combat units per domain |
|---|---|---:|---:|
| Start | Ancient | Base 2 | 2 |
| Iron Working | Classical | +1 | 3 |
| Gunpowder | Renaissance | +2 | 5 |
| Military Science | Late Industrial | +2 | 7 |
| Robotics | Information | +2 | 9 |

The cumulative column assumes all preceding listed technologies have been researched. If a technology is acquired out of sequence, sum only the bonuses actually unlocked. Default base capacity is 2 and default overall maximum is 9; both remain XML-editable. Bronze Working, Civil Service, Combustion and Combined Arms no longer grant a stacking increase in the default configuration.

Expose base/maximum capacity, technology-to-bonus rows, combat-role mappings, siege penalty, collateral percentage, HP floor, maximum victims, protection per building/source, and the 90% protection cap in XML. Custom database schemas may require a small SQL schema file, with user-editable values in XML. Do not make technology IDs or unit names mandatory C++ constants.

Capacity must depend on the moving unit's owner/team technology, not the owner of the destination tile or a global define changed during one player's turn. Recompute/invalidate caches on technology changes and derive limits correctly after loading saves or starting in later eras. Account for city-states and barbarians explicitly. Preserve existing restrictions on foreign occupants; avoid exploiting two players' different caps on one shared tile.

Proposed collateral victim limits by siege class: Catapult2, Trebuchet2, Cannon3, Field Gun4, Artillery5, Rocket Artillery5. Unique replacements inherit their unit-class tier, with XML overrides.

Proposed naval bombardment tiers: Liburna/Galleass2, Frigate3, Cruiser/Dreadnought4, Battleship/Missile Cruiser5. Apply only to eligible enemy ground combat units on land/city plots initially; embarked units need an explicit policy before inclusion. Naval combat retains its ordinary targeting rules.

Bombers also use the shared collateral rules: default 20% damage, the 50% secondary-target HP floor, limited victims and city fortification protection capped at 90%. Bomber class eligibility, tier-to-victim-limit mappings and any overrides must be XML-editable; unique replacements inherit their class settings. Exact tier defaults will be chosen during implementation. This adds collateral to bombing attacks without automatically giving bombers the siege-only direct-attack penalty.

## Combat design

Create shared, deterministic selection and damage calculations used by actual combat, previews, danger evaluation and tactical simulation. Keep the existing hostility, visibility, domain, cargo and defense-eligibility checks. Avoid calling high-level tactical helpers recursively from getBestDefender; reuse leaf damage calculations.

For normal attacks, rank all eligible combat defenders by predicted survival and damage exchange using current HP, terrain, promotions and attacker match-up. Do not exclude ranged/siege defenders just because a melee unit is present. Use stable unit IDs for ties. Ranged attacks need ranged-defense calculations rather than the current generic melee-defense comparison. Recalculate for each attack, including after damage or a casualty.

Proposed cavalry rule: eligible melee cavalry and armored successors may select exposed ranged/siege defenders. Eligible anti-cavalry interceptors prevent bypass; choose the best qualifying interceptor. Define eligibility in XML so unique units and upgrades behave consistently. Mounted ranged skirmishers do not automatically gain a melee-only bypass.

For secondary target i:

    baseCollateral = floor(primaryHitDamage * 0.20)
    protection     = min(90, sum(applicableCityProtectionPercentages))
    mitigated      = baseCollateral * (100 - protection) / 100
    collateral     = min(roundDamage(mitigated),
                         max(0, currentHP[i] - ceil(maxHP[i] * 0.50)))

Protection is zero outside a city unless another source is deliberately configured. Proposed integer-rounding policy: when baseCollateral is positive, preserve at least 1 HP of mitigated damage before applying the HP-floor allowance, so rounding does not turn the 90% protection cap into immunity. A unit already at/below the HP floor still receives zero collateral. Test this policy explicitly.

For example, protection sources of 20%, 25% and 30% give 75% combined protection. Adding another 25% reaches the 90% cap. These are illustrative values, not final building assignments. A base collateral hit of 20 then deals 5 at 75% protection or 2 at 90%, subject to the remaining HP-floor allowance.

Define the primaryHitDamage convention explicitly before implementation: the proposed default is the normally calculated primary hit after modifiers, before overkill clamping to the target's remaining HP. This avoids a nearly dead primary target nullifying collateral. The 50% floor is confirmed; this damage-base detail is a proposed default.

For a calculated30-damage hit, collateral is6 to a healthy100-HP unit,3 to one with53 HP, and0 to one with50 or40 HP. Evaluate each target's actual maximum HP. Skip ineligible/zero-damage targets before consuming the victim allowance. Choose victims deterministically and record IDs/damage before resolution, so a primary death or plot-list reorder cannot double-apply damage. Exclude the primary defender, civilians, aircraft, cargo and non-enemies from secondary victims.

Re-evaluate defender/protection after every death. A surviving defender keeps the enemy tile occupied; one kill must not allow advance through a remaining stack. City attacks retain the city as their primary target and cause collateral to eligible occupants, including the designated garrison when eligible. The new protection reduces new collateral damage; the existing city damage and garrison-absorption rules remain separate. Apply the collateral HP floor after accounting for existing garrison damage to avoid duplicate damage or unintended protection from direct damage. Apply the same city-protection calculation to qualifying naval bombardment and bomber collateral.

For bombers, account for interception and anti-air resolution before determining the damaging strike and collateral. An aborted/fully prevented bombing strike must not generate collateral. Apply the victim list once per bombing strike, using the same outcome model for air-attack previews and AI target scoring. Keep bomber bombing missions distinct from fighter air sweeps/interception and nuclear attacks; those do not acquire the new bomber collateral merely because they involve aircraft.

Existing SplashDamage damages adjacent hexes and can kill; DoExtraPlotDamage affects the target plot without the requested caps. Neither implements these rules. Keep their behavior explicit and update relevant AI predictions. CvCombatInfo's32 damage-member entries can carry the requested small number of extra victims without altering its public layout. Merge an existing garrison entry rather than creating duplicate damage records.

## AI implementation priorities

Correct simulation comes before bonuses encouraging stacks:

1. Replace binary occupancy with slot counts for live and simulated plots. Finished units occupy one slot.
2. Replace the two-enemy-defender representation with all surviving occupants; represent exceptional over-capacity positions correctly too.
3. Remove/count the actual killed unit. Preserve surviving occupancy, appropriate zone of control and target identity.
4. Share defender/collateral calculations with combat. Use simulated HP and positions, not live-world state when evaluating hypothetical moves.
5. Invalidate or key danger/attack caches by relevant stack composition, damage state and city collateral protection. Building completion/removal/capture must update protection.
6. Preserve one designated city garrison while representing additional occupants separately.

Then add deliberate behavior: assemble melee/ranged pairs near reachable threats, move ranged units into useful protected firing positions, avoid exposing them by moving the last protector away, value anti-cavalry protection against bypass, use siege/naval/bomber collateral against dense enemies, and disperse when enemy collateral makes concentration costly. Air target scoring must account for interception risk, fortification protection, target HP floors and expected damage across the stack. Account for retreat room and alternate firing positions.

The current tactical search considers at most 13 units and 6,000 positions. Two full nine-unit stacks exceed that unit budget. Keep bounded search initially, preserve important protector/ranged pairs during pruning, count omitted units as fixed occupants, and use simple stack-assembly decisions around the search. Do not multiply search limits by the configured stack size. Audit operations/gathering and city defense after the tactical core is correct.

Key source files: CvTacticalAI.cpp/.h, CvDangerPlots.cpp/.h, CvAStar.cpp, CvPlot.cpp/.h, CvUnit.cpp, CvUnitCombat.cpp, CvTeam.cpp, CvTechClasses.cpp and the Lua combat preview.

Research reference: https://forums.civfanatics.com/threads/a-serious-proposal-to-address-adding-unit-stacking.682388/page-2
Historical implementation reference: https://github.com/Gedemon/Civ5-Combat-Stacking (not a drop-in VP AI implementation).

## Stretch goal: readable stacks and Move Stack

Prioritize this after core stacking, combat and AI correctness, while preserving time for regression testing.

### Readability

- Replace crowded overlapping flags with a clear count badge and an expandable stack roster/list or grid. Keep all members accessible rather than truncating larger stacks.
- Show unit icon/name, HP, remaining movement, selected unit and relevant combat role. Make individual selection/cycling straightforward.
- Show combat occupancy and capacity by domain; distinguish support/civilian occupants and the city's designated garrison. Retain normal visibility rules for enemy units.
- Validate the layout at 2, 3, 5, 7, 9 and 10 units, including a mixed city stack, at the user's windowed 1920x1080 resolution and a smaller supported resolution.
- Use existing game/EUI icons and controls where practical. Put new layout/tuning numbers and the default two-unit button threshold in XML where feasible.

### Move Stack behavior

- Show a dedicated Move Stack action for a selected tile containing at least two player-controlled units. Capture the source tile's member IDs for this order; do not include neighboring tiles or take control of allied/foreign units.
- Reuse the existing destination-selection/highlight interaction where useful, but calculate a separate legal path and movement cost for each member. Keep individual movement budgets and normal terrain, domain, embarkation, border and zone-of-control rules.
- Before commitment, show a concise summary such as "7 move; 3 stay" and mark affected members in the roster. Tooltips should explain reasons such as no movement left, incompatible terrain/domain, blocked path or destination capacity. Highlight if a protecting unit will remain behind while vulnerable units can move.
- The initial command should evaluate whether members can complete the selected move with their remaining movement. Members that cannot complete it remain at the source; do not silently give them unrelated destinations. Clearly distinguish unreachable destinations from destinations requiring later turns. Any later multi-turn group-order extension must show differing arrival/stop outcomes explicitly.
- Reserve legal destination slots for the batch, including units already present and separate domain capacities. Use a stable, visible priority when only some members fit, with the selected unit first by default; expose new tunable priority weights in XML where applicable.
- Issue ordinary synchronized movement missions to eligible members. Revalidate during execution; changed occupancy or newly revealed threats may interrupt a move. Report resulting splits and remaining members instead of forcing illegal movement or teleporting units.
- Handle owned civilian/support units according to their own legal movement rules and separate stacking counts. Cargo and aircraft need their existing transport/rebase behavior and must not be moved as ordinary ground followers; make exclusions visible.
- Keep existing Squads memberships intact. The basic Move Stack action must not silently become a mass attack or declare war; enemy-occupied targets need the normal explicit combat interaction.
- Provide a brief post-order summary if the actual result differs from the preview, without requiring a modal dialog for every ordinary group move.

### Existing foundations and differences

Read-only review found useful hooks in CvUnit::DoSquadMovement / GetSquadMovementPreview, the Squads destination-mode Lua, EUI UnitPanel action construction and UnitFlagManager. Existing linked movement requires every follower to enter and equalizes movement allowances; existing group movement also includes neighboring tiles and formation offsets. Those semantics do not directly satisfy this command. Use shared infrastructure with a distinct stack-specific planner and result list.

Current EUI flag spreading uses a total span of about 35 pixels, leaving only a few pixels between ten flags. A roster/count treatment is preferable to simply adding more flags to that span.

### Stretch-goal validation

- Move all eligible units onto one legal hex without exceeding either domain's capacity.
- Leave exhausted, blocked and incompatible units behind, matching the preview and listed reasons.
- Test mixed movement speeds, damaged/fortified units, support units, partial destination capacity, city/coast transitions and newly revealed enemies.
- Verify that selecting the group never selects neighboring/allied units, rewrites Squads membership or silently attacks.
- Verify all ten members remain readable/selectable and that the selected unit, HP/movement changes and post-move split summary update correctly.

## Proposed unattended work order

These are priorities and rough allocations, not promises about completion time:

1. Confirm the verified native Debug checkpoint and use its build workflow. The initial fresh-game/save smoke test passed on 2026-09-26; validate Release configuration when useful.
2. Capacity/technology settings, city occupancy and ranged firing, with focused scenarios.
3. Shared defender/cavalry/collateral logic plus previews and simulation correctness.
4. Deliberate AI stack formation/protection and bounded search behavior.
5. If the core is working and time permits, implement the stack-readability and Move Stack UI stretch goal.
6. Reserve roughly the final hour for regression tests, autoplay, documentation and a clearly identified working checkpoint.

Implement mechanics for the full configured range and test the default capacities 2, 3, 5, 7 and 9, plus a ten-unit XML override to verify that the default is not hard-coded. Integrate in local commits/checkpoints after the baseline works. Do not publish or push anything. When time is short, preserve validated checkpoints and clearly mark incomplete/untested features. A polished, balanced AI across all eras, naval operations and large stacks may require further sessions.

## Evidence required before calling a build playable

- Change representative XML settings (base/max capacity, a technology unlock and value, collateral percentage/victim limit/HP floor, and building protection/cap), reload through the documented workflow, and verify that gameplay, previews and AI change consistently without recompiling the DLL. Audit newly introduced numeric literals for undocumented balance constants.
- Loaded module path/hash and fresh build identifier agree with the local artifact.
- Capacity respects technology, domain and cities; differing teams have independent capacities.
- Research Iron Working, Gunpowder, Military Science and Robotics and verify cumulative limits 3, 5, 7 and 9 from base 2. Test out-of-order technology grants, later-era starts and reloads without duplicate bonuses.
- Ranged firing works from legal stacks. Full-stack pathing, swaps, spawning and retreat do not deadlock.
- Defender identity agrees between preview, AI prediction and combat; include a case where a healthy ranged defender is better than a wounded melee defender. Cavalry/anti-cavalry tests cover successive deaths.
- Collateral respects victim count, primary exclusion,50% HP floor, odd/increased maxHP and unique-unit tiers.
- One kill never removes unhit defenders or prematurely clears an occupied enemy tile.
- City garrison, capture and city collateral behave consistently. Verify additive protection below/at/above 90%, removal of a fortification, minimum positive damage, and that only new collateral receives this protection.
- Bomber strikes against field and city stacks obey the same percentage, victim-limit and HP-floor rules. Verify interception/aborted attacks, anti-air damage, unique bomber replacements and tier upgrades, and that air-combat predictions match the resolved primary/collateral damage.
- AI deliberately protects a threatened ranged unit, understands cavalry and avoids wasteful over-concentration.
- Dense/chokepoint and late-era scenarios finish within acceptable turn times; compare tactical logs.
- Fresh-game save/reload reproduces the intended state. Broad compatibility with unrelated installed mods and multiplayer requires additional validation.

## Before the user leaves

Start instruction received. User approved tools, downloads, installations and PC test control. Keep the PC powered, connected and awake, with the desktop unlocked for game automation. Steam should be signed in. Close any game/save they want preserved before test control begins. Aim to resolve any interactive installer/login requirements while the user is still available. No start time or automation has been scheduled.
