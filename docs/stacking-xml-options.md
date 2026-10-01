# XML options added by the stack mod

Every option this mod adds to Vox Populi, gameplay first, performance and
diagnostics last. Ranges and longer explanations are in
[stacking-configuration.md](stacking-configuration.md).

Files:

- `(1) Community Patch/Database Changes/StackingConfig.xml` holds everything
  below except the siege penalty.
- `(2) Vox Populi/Database Changes/StackingVPConfig.xml` holds the siege
  penalty against land units.

Unless a table is named, an option is a `<Row Name="..." Value="..."/>` in
`Stacking_Settings`. Values are integers; switches are 0 or 1. Restart Civ V
after editing and start a new game. All players in a multiplayer game need
identical files.

## 1. Gameplay rules

### Master switches

| Option | Default | Meaning |
|---|---:|---|
| `Enabled` | 1 | Master switch for all stacking rules. |
| `DefenderSelectionEnabled` | 1 | The best defender of a stack is chosen against each attacker. |
| `FlankingEnabled` | 1 | Cavalry can bypass the top defender and hit vulnerable units. |
| `CollateralEnabled` | 1 | Siege, ranged ships and bombers deal secondary damage to a stack. |
| `DisableCityRangedAttacks` | 1 | Cities no longer shoot; stacked ranged units defend them. 0 restores VP city bombardment. |

### Stack capacity

Capacity = the smaller of `MaximumCapacity` and `BaseCapacity` + bonuses +
researched technology bonuses.

| Option | Default | Meaning |
|---|---:|---|
| `BaseCapacity` | 2 | Combat units per tile at the start of the game. |
| `MaximumCapacity` | 9 | Upper limit after all bonuses. |
| `LandCapacityBonus` | 0 | Extra slots on land tiles. |
| `SeaCapacityBonus` | 0 | Extra slots on sea tiles. |
| `CityCapacityBonus` | 0 | Extra slots inside a city. |
| `MinorCapacityBonus` | 0 | Extra slots for city-states. |
| `BarbarianCapacityBonus` | 0 | Extra slots for barbarians. |

Table `Stacking_Technologies` (`TechType`, `CapacityBonus`): one row per
technology that raises capacity. Add, remove or change rows freely.

| Technology | Bonus | Capacity with the earlier rows |
|---|---:|---:|
| Start | | 2 |
| `TECH_IRON_WORKING` | +1 | 3 |
| `TECH_GUNPOWDER` | +1 | 4 |
| `TECH_MILITARY_SCIENCE` | +1 | 5 |
| `TECH_ROBOTICS` | +1 | 6 |

### Collateral damage

| Option | Default | Meaning |
|---|---:|---|
| `CollateralPercent` | 20 | Share of the primary hit dealt to each secondary victim. |
| `CollateralHPFloorPercent` | 50 | Collateral cannot take a unit below this share of its maximum HP. |
| `CollateralMinimumDamage` | 1 | Minimum collateral per victim after protection and rounding. |

Table `Stacking_CollateralDomains` (`DomainType`, `Enabled`): where collateral
applies. Defaults: `DOMAIN_LAND` 1, `DOMAIN_SEA` 0, `DOMAIN_AIR` 0.

### City protection against collateral

| Option | Default | Meaning |
|---|---:|---|
| `CityProtectionMaximumPercent` | 90 | Cap on the combined building protection. |
| `CityProtectionScalesWithHP` | 1 | Protection shrinks in proportion to the city's lost HP. |

Table `Stacking_BuildingClassProtection` (`BuildingClassType`,
`ProtectionPercent`): Walls 10, Castle 15, Arsenal 20, Military Base 25, Bomb
Shelter 30. An optional `Stacking_BuildingProtection` table (`BuildingType`,
`ProtectionPercent`) overrides the class value for one building.

### Unit roles

Four tables with a reference column, `Role` and `Value`:
`Stacking_UnitCombatRoles` (`UnitCombatType`), `Stacking_UnitClassRoles`
(`UnitClassType`), `Stacking_PromotionRoles` (`PromotionType`) and the optional
`Stacking_UnitRoles` (`UnitType`, overrides everything, including with 0).

| Role | Meaning | Defaults |
|---|---|---|
| `FLANK` | Melee unit that can bypass the top defender. | Mounted and armor combat classes. |
| `FLANK_TARGET` | Unit a flanker can reach. | Archer and siege combat classes. |
| `ANTI_CAVALRY` | Unit that intercepts flankers. | Spearman, Pikeman, Tercio, Rifleman; Formation I, Formation II and Anti-Tank promotions. |
| `COLLATERAL_LIMIT` | Maximum number of secondary victims (0-32). | Siege 2, naval ranged 2, bomber 3 by combat class; Catapult/Trebuchet 2, Cannon/Great Bombard 3, Field Gun 4, Artillery/Rocket Artillery 5; Liburna/Galleass 2, Frigate 3, Cruiser/Dreadnought 4, Battleship/Missile Cruiser 5; WWI Bomber 3, Bomber 4, Stealth Bomber 5. |

### Siege penalty against land units (`StackingVPConfig.xml`)

| Option | Default | Meaning |
|---|---:|---|
| `UnitPromotions_Domains`: `PROMOTION_SIEGE_INACCURACY`, `DOMAIN_LAND`, `Attack` | -33 | Attack strength modifier of siege units against land units. Not a final-damage multiplier; city damage is unchanged. |

## 2. Interface

| Option | Default | Meaning |
|---|---:|---|
| `UIStackEnabled` | 1 | Stack roster panel and compact unit flags. |
| `UIStackMoveMinimumUnits` | 2 | Own units on a tile needed for the Move Stack action. |
| `UIStackFlagCollapseThreshold` | 3 | Units on a tile before their flags collapse into one. |
| `UIStackRosterWidth` | 360 | Roster width. |
| `UIStackRosterRowHeight` | 38 | Minimum roster row height. |
| `UIStackRosterMaximumHeight` | 430 | Roster height before it scrolls. |
| `UIStackRosterOffsetX` | 110 | Roster horizontal position. |
| `UIStackRosterOffsetY` | 220 | Roster vertical position. |
| `UIStackCombatPreviewGap` | 8 | Gap between the roster and the combat preview. |
| `UIStackResultDelayMilliseconds` | 250 | Delay before a stack move reports its result. |
| `UIObserverNotificationLifetimeTurns` | 3 | In observer or autoplay mode, notifications are dismissed after this many turns. 0 keeps them. |

Text keys in `Language_en_US`: `TXT_KEY_STACKING_UNIT_READY_NO_SPACE` and
`TXT_KEY_STACKING_UNIT_READY_NO_SPACE_SUMMARY` (notification when a finished
unit has no stacking space).

## 3. AI behaviour

`AIEnabled` and `AIMilitaryAllocationEnabled` must both be 1 for sections 3.3
to 3.9.

### 3.1 Switches

| Option | Default | Meaning |
|---|---:|---|
| `AIEnabled` | 1 | The AI prefers and scores stacks. |
| `AIMilitaryAllocationEnabled` | 1 | City defence and reinforcement allocation. |
| `AICityRoleDefenseEnabled` | 1 | City defenders are chosen by role (garrison, ranged, reserve). |
| `AIOffensiveSupportEnabled` | 1 | Objectives keep receiving reinforcements and production. |
| `AIWarPreparationEnabled` | 1 | The AI declares a city-attack war only when its army is staged. |
| `AIAssaultCoordinationEnabled` | 1 | Assaults gather, stage and attack as one wave. |
| `AIAssaultDominanceOverride` | 1 | A ready local force attacks a city even in an enemy-dominated zone. 0 restores VP's rule. |
| `AIEndTurnRangedFireEnabled` | 1 | Idle ranged and siege units fire at a target in range at the end of the AI turn. |

### 3.2 Stack preference

| Option | Default | Meaning |
|---|---:|---|
| `AIStackProtectionWeight` | 20 | Weight for a well-protected stack composition. |
| `AIStackJoinBonus` | 12 | Bonus for joining a useful stack. |
| `AIStackLeaveProtectorPenalty` | 30 | Penalty for leaving a stack exposed. |
| `AIStackAntiFlankBonus` | 12 | Bonus for anti-cavalry cover. |
| `AIStackCollateralWeight` | 100 | Weight on forecast collateral damage (100 is neutral). |
| `AIStackConcentrationPenalty` | 10 | Penalty per surplus unit under collateral threat. |
| `AIStackConcentrationFreeUnits` | 2 | Units in a stack before that penalty starts. |
| `AIStackPairRecruitBonus` | 25 | Bonus for keeping protector and ranged pairs together. |
| `AIStackPairRecruitRange` | 1 | Distance in tiles for such a pair. |

### 3.3 City defence

| Option | Default | Meaning |
|---|---:|---|
| `AICitySafeDefenders` | 1 | Land defenders in a safe city. |
| `AICityMaximumDefenders` | 3 | Maximum land defenders reserved on a city tile. |
| `AICityEmergencyDefenders` | 2 | Minimum when the city is besieged or about to fall. |
| `AICityMaximumNavalDefenders` | 2 | Ships held at a city under naval pressure. |
| `AICityMaximumMeleeDefenders` | 1 | Melee defenders normally kept in a city. |
| `AICityThreatenedMinimumRanged` | 2 | Ranged defenders wanted in a threatened city. |
| `AICityRangedSharePercent` | 75 | Share of city defenders that should be ranged. |
| `AICityApproachRadius` | 6 | Radius in which visible enemies count as a threat. |
| `AICityApproachWeight` | 35 | Strength credit (percent) for nearby enemies not yet attacking. |
| `AICityStrengthCreditPercent` | 50 | Share of the city's own strength counted as defence. |
| `AICityDefenseStrengthPercent` | 120 | Defence wanted relative to the assessed enemy strength. |
| `AICapitalDefensePercent` | 125 | Multiplier for a threatened capital. |
| `AICityUnitStrengthEstimate` | 25 | Assumed strength of one unit when estimating defence value. |
| `AICityGarrisonValuePercent` | 50 | Estimated defence value of the garrison. |
| `AICityRangedValuePercent` | 100 | Estimated defence value of a ranged defender. |
| `AICityMeleeReserveValuePercent` | 25 | Estimated defence value of an extra melee defender. |
| `AICityRangedProductionPriority` | 800 | Production priority for a missing ranged city defender. |
| `AICityRangedTransferPriority` | 80 | Transfer priority for a missing ranged city defender. |
| `AIGarrisonRangedBonus` | 20 | Score bonus for ranged, non-siege garrisons. |
| `AIGarrisonReplacementPercent` | 20 | Improvement needed to swap an adequate garrison. |
| `AIRearCityPlotScore` | 6 | Preference for parking healthy surplus troops in rear cities. |
| `AIRearCityHealthyPercent` | 70 | HP above which that preference is reduced. |

### 3.4 Reinforcements and formation assembly

| Option | Default | Meaning |
|---|---:|---|
| `AIReinforcementUnitsPerTurn` | 8 | Reserve units sent per player and turn. 0 disables. |
| `AIReinforcementMaximumTargets` | 8 | Demands considered per unit. |
| `AIReinforcementMaximumTurns` | 12 | Longest trip accepted. |
| `AIReinforcementTravelWeight` | 15 | Score penalty per travel turn. |
| `AIReinforcementDefensePriority` | 300 | Base score of a city-defence demand. |
| `AIReinforcementAttackPriority` | 200 | Base score of an offensive demand. |
| `AIReassignmentCooldown` | 3 | Turns a transfer keeps its goal. |
| `AIReassignmentContinuityBonus` | 40 | Preference for keeping the same goal. |
| `AIFailedAssignmentCooldown` | 3 | Turns before retrying a failed objective. |
| `AIRecruitmentReviewTurns` | 5 | Operation age before an incomplete formation is considered. |
| `AIAssemblyMinimumCombatUnits` | 4 | Members needed for an incomplete formation to proceed. |
| `AIAssemblyRequiredPercent` | 75 | Share of required slots filled. |
| `AIAssemblyMaximumMissing` | 1 | Required slots that may stay empty. |
| `AIAssemblyMinimumRanged` | 2 | Ranged units needed. |
| `AIAssemblyStrengthPercent` | 150 | Strength needed relative to the target and its defenders. |
| `AIAssemblyNoProgressTurns` | 3 | Stationary turns before a straggler is handled. |
| `AIAssemblyStallReviewTurns` | 12 | Turns without progress before the assembly is reviewed. |
| `AIPatrolCurrentZoneBonus` | 20 | Preference for staying in the current zone. |
| `AIOffensiveOperationsPerDomain` | 2 | Concurrent offensive operations on land and at sea. |
| `AIOffensiveReserveMinimumUnits` | 4 | Free healthy units needed before a new operation starts. |
| `AICityAssaultMinimumSiege` | 1 | Siege units wanted near a land siege. |

### 3.5 War opening

| Option | Default | Meaning |
|---|---:|---|
| `AIWarOpeningMaximumTurns` | 3 | The army must be within this many turns of the target. |
| `AIWarOpeningMinimumUnits` | 4 | Healthy units in range. |
| `AIWarOpeningReadyPercent` | 75 | Share of the army in range. |
| `AIWarOpeningMinimumRanged` | 1 | Ranged units in the staged core. |
| `AIWarOpeningStrengthPercent` | 150 | Staged strength relative to the target and its defenders. |

### 3.6 Offensive objectives, focus and recapture

| Option | Default | Meaning |
|---|---:|---|
| `AIOffensiveSupportMaximumObjectives` | 8 | City objectives remembered per player. |
| `AIOffensiveSupportMemoryTurns` | 12 | Turns an objective is kept without siege activity. |
| `AIOffensiveSupportMinimumUnits` | 12 | Force wanted per objective. |
| `AIOffensiveSupportMaximumUnits` | 32 | Cap on units credited to one objective. |
| `AIOffensiveSupportReserveUnits` | 4 | Reserves wanted above the core. |
| `AIOffensiveSupportStrengthPercent` | 150 | Strength wanted relative to visible defenders. |
| `AIOffensiveSupportReservePercent` | 25 | Base strength reserve. |
| `AIOffensiveSupportTravelReservePercentPerTurn` | 2 | Extra reserve per turn of distance. |
| `AIOffensiveSupportMaximumReservePercent` | 60 | Cap on the reserve. |
| `AIOffensiveSupportMinimumCapturers` | 2 | Melee units able to capture. |
| `AIOffensiveSupportMinimumRanged` | 2 | Ranged support units. |
| `AIOffensiveSupportLocalRadius` | 4 | Radius in which units count as present. |
| `AIOffensiveSupportStallTurns` | 5 | Turns before a non-moving unit loses its reservation. |
| `AIOffensiveSupportRolePriority` | 80 | Extra priority for a missing role. |
| `AIOffensiveContributionRadius` | 2 | Radius in which combat counts as contributing to an objective. |
| `AIOffensiveFocusObjectives` | 2 | Only the best this-many objectives per domain get reinforcements and production. 0 disables the focus. |
| `AIOffensiveFocusForceCapPercent` | 200 | Cap on the force-versus-enemy part of the ranking. |
| `AIOffensiveFocusDistancePenalty` | 4 | Ranking penalty per tile from the nearest own city. |
| `AIOffensiveFocusOperationBonus` | 60 | Ranking bonus when an operation targets the city. |
| `AIOffensiveFocusContinuityBonus` | 30 | Ranking bonus for objectives already in focus. |
| `AIRecaptureMemoryTurns` | 30 | A lost city stays an objective for this many turns. 0 disables. |
| `AIRecaptureFocusBonus` | 100 | Ranking bonus for a recently lost city. |
| `AIRecaptureDemandPriority` | 40 | Reinforcement priority for a recently lost city. |

### 3.7 Offensive production

| Option | Default | Meaning |
|---|---:|---|
| `AIOffensiveProductionMaximumUnits` | 4 | Units in production for objectives at once. 0 disables. |
| `AIOffensiveProductionMaximumTurns` | 12 | Longest build plus travel time accepted. |
| `AIOffensiveProductionStallTurns` | 6 | Turns without build progress before a request is cancelled. |
| `AIOffensiveProductionSiegeReserves` | 2 | Spare siege units requested beyond the wanted number. |
| `AIOffensiveProductionPriority` | 400 | Production priority for objective units. |
| `AIOffensiveProductionRolePriority` | 400 | Extra priority for a missing role. |
| `AIOffensiveProductionRoleRepairUnits` | 2 | Extra units allowed to fill missing roles. |
| `AIOffensiveProductionRecommendationSlack` | 2 | Units allowed above the normal military recommendation. |

### 3.8 Assault size and composition

Force wanted = `AIAssaultBaseUnits` + (capacity - 1) x
`AIAssaultUnitsPerCapacity`, adjusted by the rows below.

| Option | Default | Meaning |
|---|---:|---|
| `AIAssaultBaseUnits` | 6 | Base force for a city assault. |
| `AIAssaultUnitsPerCapacity` | 2 | Extra units per stack capacity step. |
| `AIAssaultStrongCityStrength` | 25 | City strength from which a city counts as strong. |
| `AIAssaultStrongCityExtraUnits` | 4 | Extra units against a strong or fortified city. |
| `AIAssaultOpportunityHPPercent` | 30 | A city at or below this HP is an easy target. |
| `AIAssaultOpportunityUnits` | 4 | Force that is enough for an easy target. |
| `AIAssaultMinimumReadyUnits` | 4 | Lower limit of the force. |
| `AIAssaultMaximumReadyUnits` | 24 | Upper limit of the force. |
| `AIAssaultBaseSiege` | 2 | Siege units wanted. |
| `AIAssaultCapacityPerExtraSiege` | 2 | Capacity steps per additional siege unit. |
| `AIAssaultStrongCityExtraSiege` | 2 | Extra siege against a strong or fortified city. |
| `AIAssaultMaximumSiege` | 8 | Upper limit of siege units. |
| `AIAssaultEssentialSiegeUnits` | 2 | Siege units the first wave must have. |
| `AIAssaultNavalMinimumRanged` | 4 | Ranged ships needed for a naval assault. |
| `AIAssaultSmallExtraSiegeSlots` / `...FrontSlots` | 3 / 3 | Optional slots added to the small city-attack formation. |
| `AIAssaultBasicExtraSiegeSlots` / `...FrontSlots` | 4 / 4 | Same for the basic formation. |
| `AIAssaultBiggerExtraSiegeSlots` / `...FrontSlots` | 5 / 5 | Same for the bigger formation. |

### 3.9 Assault timing, staging, bombardment and capture

| Option | Default | Meaning |
|---|---:|---|
| `AIAssaultApproachTurns` | 3 | Units within this many turns count toward the wave. |
| `AIAssaultHealthyPercent` | 65 | HP a unit needs to count as ready. |
| `AIAssaultStrengthPercent` | 125 | Strength needed relative to the local enemy. |
| `AIAssaultDamageHorizon` | 4 | Turns in which the wave must be able to bring the city down. |
| `AIAssaultIncompleteDamagePercent` | 125 | Damage margin when the city's healing is not fully known. |
| `AIAssaultFirstWaveMaximumTurns` | 1 | Latest arrival admitted to the first wave. |
| `AIAssaultWaveArrivalSpreadTurns` | 1 | Allowed gap between first and last arrival. |
| `AIAssaultGatherTurns` | 6 | Turns of gathering before the assault is reviewed as stalled. |
| `AIAssaultAbandonTurns` | 24 | Turns without useful action before the assault is abandoned. |
| `AIAssaultAttackProgressStallTurns` | 24 | Turns a ready siege may go without net city damage. 0 disables. |
| `AIAssaultReviewInterval` | 3 | Turns between assault reviews. |
| `AIAssaultStageRadius` | 6 | Distance from the city in which staging tiles are sought. |
| `AIAssaultStageCohesionRadius` | 2 | Units this close to the staging tile count as gathered. |
| `AIAssaultStageDangerPercent` | 0 | Danger (share of HP) accepted on a staging tile. |
| `AIStationaryFireDangerPercent` | 50 | While gathering, ranged units fire from their tile unless danger exceeds this share of HP. 0 uses the staging rule. |
| `AIAssaultBombardStrengthPercent` | 60 | Ranged units bombard while the wave gathers if the force has this share of enemy strength. 0 disables. |
| `AIAssaultBombardMinimumRanged` | 2 | Ranged units needed for bombardment. |
| `AICapturePlanMaximumTurns` | 6 | How far ahead a capture is planned. |
| `AICapturePlanMinimumHPPercent` | 60 | HP a distant capturing unit needs. |
| `AICaptureNoProgressTurns` | 6 | Turns before a capturer that makes no progress is replaced. |
| `AICaptureRetryTurns` | 4 | Turns before that unit may try the same city again. |
| `AICaptureContinuityBonus` | 120 | Preference for keeping the same capturer. |
| `AISiegeNoCaptureReviewTurns` | 8 | Turns a siege may lack a capturer before its fire is reviewed. |
| `AISiegeNoCaptureLowHPPercent` | 25 | Below this city HP, pointless fire stops when no capturer exists. |
| `AIOperationRouteRetryTurns` | 6 | Turns before retrying a target after a lost path. 0 disables. |
| `AIOperationRouteRepairCandidates` | 4 | Alternative start points tried after a route fails. |
| `AIOperationMovingStallTurns` | 12 | Turns a march may make no progress. |
| `AIOperationContactStallTurns` | 20 | Same, after the army has fought. |
| `AIOperationContactHoldPercent` | 50 | Share of exposed units at which the core holds its position. |

## 4. Performance and work budgets

These do not change which rules apply; they bound how much the AI computes.

| Option | Default | Meaning |
|---|---:|---|
| `AITacticalStrengthCacheEntries` | 16384 | Combat-strength results reused within one tactical search. 0 disables. |
| `AITacticalForecastEntries` | 24000 | Danger and defender forecasts kept per tactical search (about 172 bytes each). |
| `AITacticalYieldPositions` | 2000 | Search positions between interface updates. Lower it if the interface stutters during AI turns. |
| `AITacticalCacheAirActors` | 1 | Keep the caches when aircraft take part. 0 only for mods with `CanLoadAt` listeners. |
| `AIAssaultTacticalBatches` | 3 | Successive tactical searches for a large assault. |
| `AIAssaultExtraBatchesPerTurn` | 16 | Extra searches allowed per player and turn. |
| `AIAssaultTacticalRetries` | 4 | Retries of an assault search within a turn. |
| `AIAssaultPathQueriesPerTurn` | 64 | Path queries for assault planning per player and turn. |
| `AIAssaultStageCandidates` | 96 | Staging tiles examined. |
| `AIAssaultStagePlacementCandidates` | 8 | Staging placements tried per unit. |
| `AIAssaultFiringPositionCandidates` | 6 | Alternative firing routes tried. 0 disables. |
| `AIAssaultFiringPositionScanPlots` | 96 | Tiles examined for firing positions. |
| `AIAssaultFiringPositionRadiusMaximum` | 6 | Search radius for firing positions. |
| `AIAssaultWaveMaximumRecords` | 64 | Wave records kept per objective. |
| `AICapturePlanPathQueriesPerTurn` | 32 | Path queries for capture planning per player and turn. |
| `AIReinforcementPathQueriesPerTurn` | 32 | Path queries for reinforcements per player and turn. |

## 5. Diagnostics

Logging only; no effect on the game. Off by default.

| Option | Default | Meaning |
|---|---:|---|
| `DiagnosticsLevel` | 0 | 0 off, 1 summary, 2 verbose. The in-game menu overrides it until reload. |
| `UIStackDiagnosticsHotkeyEnabled` | 1 | Ctrl+Shift+D opens the diagnostics menu. |
| `DiagnosticsCategoryMask` | 63 | Sum of: 1 snapshots, 2 military, 4 tactical, 8 combat, 16 performance, 32 memory. |
| `DiagnosticsPlayer` | -1 | Log one player only; -1 logs all. |
| `DiagnosticsVerboseStartTurn` | -1 | First turn of verbose records; -1 is open. |
| `DiagnosticsVerboseEndTurn` | -1 | Last turn of verbose records; -1 is open. |
| `DiagnosticsSummaryInterval` | 1 | Turns between summary snapshots. |
| `DiagnosticsDetailInterval` | 10 | Turns between verbose unit and city snapshots. 0 disables. |
| `DiagnosticsMemoryInterval` | 10 | Turns between memory samples. 0 disables. |
| `DiagnosticsPerformanceInterval` | 1 | Turns between cost records. 0 disables. |
| `DiagnosticsCombatSummary` | 1 | One compact record per combat. |
| `DiagnosticsTacticalSampling` | 0 | Extra tactical plan sampling, for investigation only. |
| `AIAssaultObjectiveSummaryInterval` | 5 | Turns between assault objective summary records. |
| `DiagnosticsLongPlanThreshold` | 256 | Warn when a tactical plan grows past this length. 0 disables. |
| `DiagnosticsHistogramMaxStack` | 32 | Largest stack size with its own histogram bucket. |
| `DiagnosticsMaxRowsPerTurn` | 4096 | Records per turn before output is truncated. |
| `DiagnosticsMaxFileKB` | 4096 | Size of one log segment. |
| `DiagnosticsMaxFiles` | 8 | Log segments kept per session. |
| `DiagnosticsBufferKB` | 64 | Write buffer size. |
| `DiagnosticsFlushEveryRows` | 256 | Flush after this many records. |
| `DiagnosticsFlushIntervalMilliseconds` | 1000 | Flush after this much time. 0 disables the timer. |
| `DiagnosticsImmediateFlush` | 0 | Write every record at once; use when reproducing a crash. |
