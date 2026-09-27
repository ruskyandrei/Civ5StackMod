# Autoplay to turn 236: stalled-war investigation

## Assessment

This campaign contains clear offensive failures, but does not establish that their frequency increased relative to unmodified VP or the earlier stacking build. There is no matched control campaign. The strongest actionable evidence concerns repeated route failures, loss of army continuity, delayed support and failure to convert a damaged city into a capture. These warrant attention before a broad defensive nerf. Stacking could still favor defense; the available Summary logs do not measure that effect directly.

No C++, Lua, XML, installed package or game state was changed. The game was already closed. The turn-0 and turn-236 saves and 198 relevant current-run logs were copied to `C:/Users/rusit/Documents/Codex/Civ5StackMod-analysis/autoplay2-turn236`. Archive hashes verify. Older named logs from earlier campaigns were excluded by the current run's start time. `manifest.json`, `analysis.json`, `review-metrics.json`, `native-summary.json`, the raw logs and the analysis scripts preserve the evidence and methodology.

Run identity: PID 22544 / `Stacking-20260927T130616-455-p22544-r1`; embedded DLL `Release-5.4.6-11-g9c33e26 Clean`. Four segments numbered 0–3 contain 123685 parsed records covering turns 0–236, with no missing segments, malformed records, rewinds or row-budget truncation. Most major players' final AI sample is 235; Siam and Brazil also have 236 samples. This is a game stopped at 236, not proof every player's 236 turn completed.

## Captures and war outcomes

`MilitaryAILog_*` records 12 conquests overall. The source invokes `LogCityCaptured` in the conquest branch, so this count excludes ordinary gifts/trades. Only three were conquests by one major civilization from another:

| Turn | Captor | City | Previous owner |
|---|---|---|---|
|70|India|Barcelona|Spain|
|167|Sweden|Rabat|Morocco|
|231|Sweden|Hyderabad|India|

The other nine involve barbarians or city-states, including recaptures. A conquests count is not a count of unique cities or every diplomatic ownership change. Original records: `MilitaryAILog_India.csv:749`, `MilitaryAILog_Sweden.csv:3588` and`:7035` in the archive.

Several concluded wars produced no major-city conquest:

| War | Declaration → peace | Recorded major-city conquests during that war |
|---|---|---|
|Sweden–Morocco, first war|58 → 104|0|
|Poland–Sweden|86 → 123|0|
|Russia–Ottomans, first war|113 → 178|0|
|Celts–Brazil, first war|119 → 164|0|
|Celts–Brazil, second war|186 → 218|0|
|Russia–India|184 → 219|0|

Spain–India at 37–101 yielded Barcelona for India; Sweden's later Morocco war at 127–213 yielded Rabat. Sweden took Hyderabad on 231, three turns after declaring on 228. Cities can therefore fall quickly in this ruleset; that does not rule out a defensive bias in other situations. Diplomatic message logs supply the declaration/peace dates; war-state logs corroborate the intervals. Do not treat the generic city-gate counter as actual attacks or operation success as conquest.

Policy logs confirm the user's context: Spain opened the Authority/Honor-ID branch on 16 and Sweden on 18; the other eight majors chose Tradition or Progress initially. They nevertheless conducted wars and created attack armies, so low aggression is not the sole explanation for the execution failures below.

## Main findings

### 1. Repeated path failures are the largest newly identified problem

There were 271 logged city-attack operations across the ten majors,263 ended and 8 still open. End reasons include 131 `LostPath`,44 `NoUnits`,14 `HalfStrength`,40 `Success`,20 `WarStateChange`,9 `DiploOpinionChange`,2 `TargetAlreadyCaptured`,2 `TooDangerous` and 1 `TimedOut`. These are operation instances, not independent wars, battles or casualty counts.

Of 131 path failures,118 ended on their creation turn and another 5 after one turn. This repeatedly recruits and releases armies without a useful march. A single recurring objective dominates: barbarian-held Lutetia at 78:63 accounts for 104 failures—India 60, Brazil 18, Spain 18 and the Celts 8. Lutetia was taken by barbarians on 80 and was not subsequently conquered in these logs. This concentration matters: the raw 131 is not evidence of 131 failed attacks on fortified major capitals. It is strong evidence of repeated unusable assignments that can tie up forces otherwise available elsewhere. Poland also logged 14 path failures against Madurai.

Example: Brazil operation 4658 recruits nine members on 166, immediately switches to movement around 85:39 toward 78:63, then ends `LostPath` on 167 with distance -1. The following attempt recruits another nine on 168 and fails that same turn (`OperationalAILog_Brazil.csv:482–523`). India repeatedly starts eight-unit attempts toward the same objective.

Source route: `PlotArmyMovesCombat` calls `ComputeTargetPlotForThisTurn`; a null step-path target aborts with `AI_ABORT_LOST_PATH`. The latter can be trying to reach the muster point during gathering, not necessarily the enemy city. Logs omit the exact failed segment, legality reason and alternative routes. Candidate target reachability, actual recruited-unit locations, centroid selection, neutral borders, embarkation and muster relocation need to be reconciled. The recent changes to recruitment/gathering may interact with this; no baseline replay was run, so do not label this solely an upstream bug or a proved regression.

### 2. Armies often stop being replenished after departure

Of 46 city-attack operations observed for at least five turns after entering movement,43 have no logged member addition on a later turn. All 14 `HalfStrength` endings are in that group. `HalfStrength` means the army fell below its required member threshold; casualties, healing releases and reassignment can all contribute, so it is not a kill count.

There is a matching source limitation: reserve recruitment is called while an army is waiting for reinforcements; loss handling in recruitment adds a missing slot to the build queue, while gathering/moving loss handling instead checks whether the army should abort. This lacks the continuing role/strength replenishment policy now on the todo list. `CvArmyAI::AddUnit` supplies the logged additions when a current army plot is available.

The new rear-transfer helper did work:180 major-player movement/arrival events, including 31 arrival records for 27 distinct units. These are repeated observations, not 180 distinct reinforcements, and arrival means within two hexes of staging, not combat contribution or formal army membership. Other tactical/homeland movement is outside this helper's counts. Thus the evidence is not that no support ever moved forward; the gap is continuous, objective-specific force maintenance and successful handoff.

Spain operation 5625 is illustrative. It recruited seven units on 185 for Moscow 64:31, entered movement immediately, recorded repeated contact/no progress, and ended `HalfStrength` on 220 after 35 turns. Its center remained near 70:34/71:34 late in the operation. The helper records support arriving near that army on 189 and 204, but no later army-member addition. Native support arrival alone was not enough to keep the offensive effective. Source contact logic can hold an army at its current center whenever nearby enemies are detected; that requires objective-aware review, not unconditional removal.

### 3. Early handoff after discovery is repeated beyond the Russian example

Nine operations log `Discovered by enemy` before marking deployment successful, bypassing the normal distance condition. Examples include Spain approaching India on 36 (nearest 4/farthest 5 hexes), Sweden approaching Morocco on 57 (7/11), Russia's Ottoman operation on 112 (6/11), and another Swedish approach on 126 (7/10). These are geometric distances, not attack ETAs. Some discovered forces may legitimately need to declare at a border, but discovery alone does not establish readiness. The existing [war-preparation review](war-preparation-review.md) covers the specific code and release behavior.

### 4. Damaging a city is not consistently converted into capture

Russia's Edirne assessment records remaining city HP 86 on 136,46 on 137 and 32 on 138. By 140 it has 52 HP and the expected damage estimate has fallen to 15; by 147 the city has 430 HP and expected damage 16. Russia never captured it. The assessment series spans 118–177 with 17 distinct turns reaching the capture-attempt planning gate; that gate is not proof every proposed attack executed.

At 136–138, the gate counted three candidates including one non-ranged candidate. The Summary logs do not identify that unit or its route/survival problem; the user's screenshot shows bombardment across water and possible third-party border constraints. This supports the [capture-plan todo](siege-capture-review.md), not a claim that no melee unit existed anywhere.

### 5. Some forces still spend a long time assembling

Nine operations have at least ten logged recruitment turns, and six have at least ten gathering turns. One Indian operation stayed in recruitment over 32 consecutive turns before deploying. The new no-progress recovery fired only once in this run. Its clock resets when members or distance improve, so an operation can remain ineffective for a long time despite intermittent progress. Moving-phase contact/no-progress is another separate gap. Longer deadlines alone will not fix these cases.

## What is not supported as the main bottleneck

The 13-unit tactical cap dropped candidates in only 3 of 17698 planning-recruitment records: two Brazilian calls on 215 and a Russian call on 234. Edirne used three candidates. Increasing that cap would not address most observed failures. The strategic transfer helper reached at most 4 successful transfers per player/turn, below its default cap 8; this says nothing about unlogged path-query budget saturation. All 914 logged garrison assignments changed position; no Summary sample reported illegal stacking or over-cap stacks, and there are no native long-plan warnings.

City-attack checks for majors total 6250:3042 enemy-dominance rejections,2729 no eligible units,370 insufficient-damage rejections and 109 attempt decisions. These repeatedly examine targets across turns; they are not 6250 offensives. They suggest obtaining a usable force at the target is a major problem, but enemy dominance can reflect strong defense as well as weak/constrained attack allocation.

## Can we blame stronger defense or collateral protection?

Not from these logs alone. This session used Summary throughout: there are no detailed city-protection snapshots or before/after combat participant records. We cannot measure how much collateral was prevented, how many defenders survived because of protection, or whether equivalent supported attacks would win with another protection curve. The HP-scaled protection proposal remains reasonable to test, but this analysis does not establish that it is needed for balance.

Our added fortification protection reduces collateral to occupants; it does not directly reduce ordinary city-HP damage. Other stacking mechanics—more defenders in one place, selecting a stronger defender, protected ranged units and easier concentration—can still increase defensive effectiveness. Local conditions and the map matter. Fixing demonstrable path/continuity/capture failures first will produce a more informative defensive-balance test than compensating for them with a general nerf.

## Suggested priority

1. Investigate repeated `LostPath` create/abort loops. Validate usable unit/muster/target routes consistently, repair a bad staging point where possible, and remember failed target/route combinations long enough to avoid instant identical retries. Log the actual segment and rejection reason. Audit interaction with the new recruitment/cohesion changes.
2. Implement persistent offensive reinforcement and production demand across movement and tactical handoff, protecting critical roles and forecasting support lead time. Reassess armies pinned in contact without meaningful progress.
3. Strengthen pre-war readiness and actual capture-route checks. Preserve useful commitments across declaration, and stop unsupported sieges from continually restarting without a viable capturer.
4. Test HP-scaled city protection and other balance changes with detailed combat traces after the above fixes. Use matched map/civilizations/difficulty and multiple seeds, with the prior allocation policy and an appropriate stacking/VP control; naturally diverging RNG means compare outcomes across campaigns rather than requiring identical late-game boards.

New route-loop and moving-phase findings are recorded on the todo list. No fixes or balance edits were applied during this investigation.
