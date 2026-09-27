# Military AI implementation plan

Status: implementation authorized on 2026-09-27. Work will use offline validation followed by at most one final game launch for smoke testing; broader autoplay comparison will be run by the user. Reviewed against stacking source checkpoint `1600bef` / DLL source `ef54698`, based on VP 5.4.6. The user reports the previous build reached turn 330 without an observed crash and the three-turn observer notification cleanup works in game.

## Implementation checkpoint — 2026-09-27

The first bounded implementation is built and installed from source `9c33e26`. The one live smoke session loaded330 and advanced into332 without a new crash report, ending at its180-second test limit; turn333 and same-process save/reload were not confirmed. Build, diagnostic and memory evidence is in [the implementation record](../work/MILITARY-AI-IMPLEMENTATION.md). Phases 0–4 have a usable initial implementation: shared city retention, placement/muster/garrison fixes, ETA-1 recovery, domain reserve budgets, bounded reserve transfers, role/strength readiness, assembly deadlines and gather-space/cohesion corrections. Phase 5 adds missing-siege reinforcement, reduced healthy rear-city preference and patrol reassignment; existing stack combat simulation remains in use. Configuration/defaults are now documented in [stacking configuration](stacking-configuration.md#military-allocation-settings).

This is not completion of every research/tuning item below. The current city assessment uses immediate reach plus discounted visible proximity, not a full two/four-turn threat planner. Strategic demand uses health-adjusted base strength and broad roles, not full promotion-aware combat simulation. Specialized last-city/production/route importance, ocean invasion/air force coordination, skirmish pinning, role substitutions, and comprehensive multi-front/congestion fixtures remain follow-up work. New long-range transfer paths intentionally do not embark; ordinary VP invasion operations retain that responsibility. Outcome/turn-time calibration and matched campaign comparisons are pending the user's fresh autoplay.

Offline coverage now includes 135 actual-source native allocation checks, 44 diagnostic policy/IO checks, 16 summarizer scenarios and existing movement/siege/placement/cache/notification regressions. These use controlled stubs for engine services; they do not establish real pathfinding behavior or campaign effectiveness. The completed bounded live smoke session is a release sanity check, not the 100-turn/multiple-seed acceptance study proposed below.

## Objective and constraints

Use available military units to accomplish specific offensive and defensive objectives, with explicit reasons for retaining, moving, healing or releasing each unit. Stacking is an option that improves force concentration and protection; filling every city or every tile to its capacity is not an objective.

- Preserve legal per-domain capacity, borders, movement, embarkation, city capture and aircraft rules. A stack remains separate units, not one combined-strength unit.
- Use the same defender, cavalry interception, collateral and city-fortification calculations as actual combat. Do not approximate a stack as simply N times one unit's strength.
- Work from the AI's legitimate visibility and remembered information. Separate immediate reachable threats, uncertain approaches and longer-term diplomatic exposure.
- Preserve emergency defense, recovery, civilian escorts and justified reserves. Reducing the number of idle units alone is not proof of stronger play.
- Expose new gameplay thresholds, weights and limits through XML with documented bounds. Keep engine limits separate from balance settings.
- Keep upstream hooks small and place reusable assessment/allocation logic in dedicated stacking AI files. Retain the existing bounded tactical search initially (13 units / 6,000 states).
- AI implementation is authorized. Preserve the running campaign until final deployment; do not replace its loaded DLL or inject scenario fixtures into it. Use one separate final smoke-test session.

## Evidence from the Danish autoplay game

Read-only live snapshots at turns 288, 291 and 293 were matched against the ordinary military, operational, tactical and homeland logs and native stacking diagnostics. Native logs were healthy: Windows directory metadata for open files was stale, not evidence of a logging failure. The session changed from Verbose to Summary at turn 274, so later detailed reasons came from ordinary logs and read-only Lua queries.

At turn 293, Hedeby (25,20) had three undamaged Tercios:

| Unit | Assignment |
|---|---|
| 9473 | Actual city garrison |
| 8751 | Repeated tactical garrison orders, not the actual garrison |
| 8460 | Land attack operation 9677, still recruiting |

No enemy combat units on Danish-visible tiles were within six hexes; the nearest was nine hexes away. This is geometric distance and a visibility-limited observation, not a complete path-based threat forecast. Hedeby's exposure list included cities belonging to players Denmark was not fighting. Frontline Tunsberg, by contrast, had enemies one hex away and genuinely needed protection.

Operation 9677 remained recruiting from turns 280 through 294. Naval operation 8885 began recruiting at 267, gathered from 275, and finally moved at 291. These are prolonged delays, not proof that every city occupant was assigned to defense. A 10-slot formation does not require all ten slots: `HaveEnoughUnits` distinguishes required and optional slots.

Evidence was archived separately as `denmark-20260927`, with source log copies, capture times and SHA256 hashes. Keep raw campaign logs/saves outside source control. Retain this scenario as one benchmark, not the sole tuning target.

## Code review findings and confidence

| Finding | Evidence / implementation location | Classification |
|---|---|---|
| Excluding the city center does not exclude it from the fallback placement search. | `CvCity::GetPlotForNewUnit(false)` skips its early center return, then still iterates ring index zero. Stacking makes an occupied center legal. | Confirmed control-flow defect; directly relevant to garrison displacement. |
| Garrison replacement requests do not require a better replacement. | `CvTacticalAI::PlotGarrisonMoves` wants a ranged replacement for a melee garrison; `FindUnitForThisMove` can return another melee unit. Existing garrison is processed before replacement handling. | Confirmed policy gap; repeated extra garrison orders observed. |
| Own cities cannot receive the intended muster patrol bonus. | `CvMilitaryAI::IsPossibleMusterCity` returns false when the supplied city's owner IS the AI player. Its caller in `HomelandAIHelpers::GetPatrolTargets` supplies own cities. | Confirmed contradictory ownership guard. |
| An ETA below two turns bypasses progress detection indefinitely. | `CvArmyFormationSlot::IsMakingProgressTowardsCheckpoint`; Tercio 8460 repeatedly reports ETA 1 without changing tile. | Confirmed blind spot; exact movement-block reason still needs instrumentation. |
| Patrols can retain units in a lower-priority current zone. | `ExecutePatrolMoves` immediately accepts a target in the current zone, searches only the top three patrol targets and uses an 11-step reach bound for majors. | Confirmed heuristic; global impact must be measured. |
| City exposure is not the same as immediate defensive need. | `CvCity::NeedsGarrison` calls `IsExposedToEnemy(NO_PLAYER)`; exposure derives from possible routes, including peace-time opponents. | Intentional upstream caution; refine allocation rather than erase it. |
| Reinforcement can stop before a siege has the right tools. | `PlotReinforcementMoves` exits for friendly overall/ranged dominance unless melee strength is zero; siege need is an existing TODO. | Confirmed role-blind gate, not yet measured in this replay. |
| Safe friendly cities receive a flat high tactical position score when a simulation has enemies. | `ScorePlotForCombatUnitMove` sets friendly-city plot score to 12. It does not ask whether one more occupant helps the objective. | Confirmed preference; suspected concentration/stalling contributor. |
| Reserve gating mixes naval and land counts against a land recommendation. | `CvMilitaryAI::DoCityAttacks`. | Confirmed cross-domain approximation; do not change without allocation metrics. |
| Cohesion compares coordinate variances to a linear gather tolerance. | `GetCenterOfMass` produces variance; `CheckTransitionToNextStage` compares it with `iGatherTolerance`. Final departure also checks furthest-unit distance. | Confirmed inconsistent units; intended tuning needs a fixture before changing. |
| Available gathering space and total army size can be compared inconsistently. | Stacking `GetGatherTolerance` subtracts occupants, including already assembled members, then compares remaining space with the entire army size. | Review and fixture required; count capacity for remaining arrivals or include assembled members consistently. |
| Enemy contact can change the whole army's turn target to its current center. | `PlotArmyMovesCombat` after `CheckForEnemiesNearArmy`. | Intentional combat safeguard; investigate detached skirmishes pinning reinforcements, not a blanket removal. |

Rechecked and rejected one suspected issue: `CvArmyAI::SetFormation` calls `ReleaseAllUnits`, which already clears formation entries. Do not add a redundant fix. Likewise, `IsGarrisoned()` refers to one designated city garrison, not every unit on the city plot.

## Delivery sequence

### 0. Baseline and explanations before broad tuning

Capture an unchanged save/build/configuration baseline and add bounded decision records at existing decision points. Identify units by owner/ID; record actual destinations and results, not just intended moves. Use existing evaluated danger/path values where possible; diagnostics must not trigger new world scans, consume RNG or influence decisions.

Add categories for city defense requirements, unit retention/release, recruitment rejection, operation readiness, assembly stalls, reinforcement routing and destination rejection. Include reason codes such as `required_garrison`, `healing`, `civilian_escort`, `army_committed`, `no_path`, `capacity_full`, `unsafe_endpoint`, `missing_role`, `no_improvement` and `no_progress`.

Distinguish requested, reserved, moving, arrived and failed assignments. Capture per-unit unchanged location/ETA and actual reason for a blocked move. Extend the offline summarizer; preserve existing file/row bounds and explicit truncation. Add optional city/operation/category filters if output volume warrants them.

Acceptance: the Danish examples can be explained from native diagnostics without an injected observer; Off versus enabled logging leaves the same captured gameplay state in a controlled replay.

### 1. Small correctness fixes

1. Honor `bAllowCenterPlot` throughout placement. Audit every caller before changing shared placement behavior; test production with center allowed, garrison displacement with center forbidden, full neighbors, mixed domains and no legal exit.
2. Make garrison replacement explicit. Reuse an adequate defender already in the city; require a measurable improvement before recruiting another; validate the replacement, preserve a defender during handoff, and release the surplus unit once the requirement is met. Do not mark a candidate as used merely for a same-tile non-improvement. Account for the city's actual strongest-garrison selection, including ties and ranged/city-strength tradeoffs.
3. Correct the muster-city ownership guard and cover own/enemy/null cities and each army type.
4. Detect stalled near-arrivals using actual position/path progress as well as ETA. Allow a short grace period for combat, healing and temporary congestion. Reroute before releasing a unit; prevent immediate recruitment back into the same failed assignment.

Acceptance: repeated no-op garrison recruitment stops; safe cities do not retain duplicate defenders through a replacement loop; ordinary 1UPT/stacking-disabled behavior and city production remain valid. Stalled ETA-1 units trigger a documented recovery action.

### 2. Shared defensive requirements and surplus accounting

Introduce a per-player, per-turn `CityDefenseAssessment` and unit retention query in dedicated stacking AI code. Reuse it across tactical garrison selection, operational recruitment, reinforcement and homeland patrol so those systems agree about which units are genuinely needed.

For each city/domain, assess:

- Reachable enemy melee capture, ranged/siege pressure, cavalry interception needs and plausible naval landings; include city HP/fortifications and a bounded uncertainty allowance.
- Friendly usable defensive strength, ranged support and nearby response time. Count an incoming reinforcement once and expire failed reservations.
- Baseline city importance: ordinary city, capital, last city, contested production center or essential route. Importance adds a bounded reserve requirement, not automatic filling to stack capacity.
- Healing/transit occupants separately from assigned defenders. Protect civilians and do not cannibalize critical escorts.

Start with a one-unit baseline for a safe ordinary city, with exceptions for early expansion, existing garrison benefits and severe military shortages. Additional defenders should satisfy an identified strength or role deficit. A protected frontline city may need several stacks around it, not every defender on its center tile.

Avoid redefining the global `NeedsGarrison` boolean in isolation: review its consumers and introduce AI-specific retention decisions first. Reserve requirements must be reconsidered after losses, captures, diplomacy and changes to stack capacity. Planning uses a snapshot; execution revalidates legal capacity, protection and ownership.

Acceptance: safe southern-city surplus becomes recruitable while Tunsberg-like frontline defenses, capitals, isolated coastlines and civilian escorts remain adequate.

### 3. Allocate free forces to objectives

Represent active fronts/operations as demands with target, priority, domain, missing roles/strength, legal staging space and travel cost. Prioritize preventing imminent city loss, then viable active-war objectives, then other reserves and peace-time exposure.

Allocate units deterministically by marginal contribution and arrival time, subtracting already committed and inbound strength. Account for strength/HP/promotions and useful roles rather than raw headcount. Keep land, naval and air demand separate; mixed operations require coordinated transport/escort and lawful access.

Add a longer-range reinforcement route for genuinely idle rear units; local tactical reinforcement alone cannot bridge a large empire. Replace patrol's unconditional current-zone preference with a bounded reassignment threshold and cooldown. Preserve a useful front against a second opponent and reevaluate invalid targets promptly.

Acceptance: repeated replay snapshots show healthy rear units arriving where they are needed, without oscillation, duplicate assignment or stripping emergency defenses. Measure arrival and contribution, not orders issued.

### 3a. Proactive reinforcement of an existing offensive

User priority added 2026-09-27: when an initial force is sent toward a city, begin recruiting and dispatching useful reinforcements before that force takes casualties, where resources and routes permit. Treat the offensive as a continuing commitment through preparation, approach, siege and capture, including tactical handoffs that end the original army operation.

- Let a viable initial core depart while a follow-up force assembles. Do not delay every attack until one oversized formation is full. Additional forces should reinforce the same objective rather than create competing attacks that fragment the available military.
- Set a target-specific desired combat strength, role mix and bounded nearby reserve. Consider visible defenders, expected reinforcement travel time, credible attrition, capture/holding needs, legal stack capacity and the value of the objective. Missing formation slots or casualties alone must not define demand.
- Allocate existing free units first where sensible; send unmet role demand to military production planning when building support is worthwhile. Credit reserved, training, travelling, staged and fighting units once each, with explicit ownership of the assignment. Apply existing supply, economic and home/other-front defense constraints.
- Dispatch support early enough to arrive while the opening force is still effective. Use safe staging areas and coherent travel groups when necessary; feed reinforcements into legal stack slots and rotate wounded troops to recover. A declared destination is not a completed reinforcement: track actual progress and arrival.
- Keep the objective and support commitments through the peace-to-war transition and operational-to-tactical handoff. Share the capture-plan demand from the Edirne review, including routes around water, third-party border access and controlled landings; do not merely send more ranged units toward an uncapturable city.
- Cap the committed/inbound force and reevaluate when the target falls, diplomacy changes, a route fails, support is too late or a stronger emergency arises. Cancel unnecessary production requests/reservations and deliberately reassign surplus rather than continually feeding an obsolete siege.
- Expose new desired-force/reserve margins, role targets, travel/dispatch horizons, reinforcement priorities, commitment caps and reassessment periods through XML. Add diagnostics separating requested, reserved, being trained, travelling, staged, fighting and failed support, including why no further reinforcement is useful.

User-observed failure to address: several attacks begin effectively, then lose momentum through attrition while no reinforcements arrive for multiple turns. This is an observation across the autoplay, not a quantified log finding for a particular battle. Forecast whether the fighting force will remain adequate over the combined recruitment/production, gathering and travel lead time; use known threats and observed losses with a bounded uncertainty margin. Dispatch support before the projected shortage, prioritizing preservation of essential capture/protection roles. Reassess viability if support cannot arrive in time rather than committing endless replacements to a losing attack. Track reinforcement-free frontline turns, projected versus actual usable strength, and stalls/withdrawals attributable to support arriving late.

Current implementation boundary: the rear-transfer helper can already request some support before losses, including a minimum demand for a full formation. However, that demand is based on vacant slots multiplied by the candidate's strength, with a one-unit floor; it is not this target-based force/reserve policy, does not coordinate a production queue, and depends on a still-active offensive army. This subsection is a planned extension, not a description of implemented behavior.

Acceptance scenarios: a full healthy army receives useful follow-up support before casualties; a long approach triggers earlier dispatch; missing melee/siege/anti-cavalry roles are filled without over-ordering; multiple cities do not promise the same unit or duplicate production; sea crossings and closed borders are respected; wounded units can be relieved; capture/abort cancels stale requests; home and simultaneous-front defenses stay adequate. Measure first support arrival relative to first combat/loss, fulfilled role deficits, time-to-capture, reinforcement losses and idle/oversupplied reserve turns. Preserve bounded tactical batches rather than increasing the 13-unit/6,000-state search to fit the entire offensive.

### 4. Make recruitment and gathering converge

Keep existing formation roles initially. Separate essential roles (e.g. a city-capturing melee unit, siege where required, naval escort) from interchangeable support. A large stack capacity does not imply multiplying every formation by that capacity.

- Add per-stage deadlines and meaningful progress histories; the existing whole-operation timeout is a last resort.
- Before another competing operation is created, consider reinforcing an existing operation against the same target.
- On prolonged recruitment, evaluate a viable smaller force, equivalent-role substitution, consolidation or cancellation/reassignment. A timeout alone never makes an unsafe assault viable.
- Detach/reroute stragglers when a coherent, adequately supported core can proceed. Respect coastal/ocean access and capture capability.
- Make gather-space accounting and cohesion units consistent. Measure reachable legal slots for remaining arrivals; test already assembled stacks, occupied bottlenecks and mixed fleets.
- Avoid the release/recruit loop by remembering a failed assignment long enough to choose a different route or role.

Acceptance: forces do not wait indefinitely for ETA-1 arrivals or impossible roles; assembly age and front-arrival time improve without a rise in unsupported attacks.

### 5. Objective-aware stack movement and combat

Refine city/stack position scoring so extra occupancy is valuable only when it improves defense, firepower, recovery or staging. Score actual marginal survival and damage under the existing defender/flanking/collateral rules. A single melee protector must not be credited as invulnerable protection for every ranged member against repeated attacks.

Preserve melee/ranged and anti-cavalry combinations when the threat warrants them. Make concentration depend on observed/remembered siege, ranged ships and bombers, using current collateral limits and city protection. Spread when feasible; do not destroy useful covering pairs just to reduce density.

Promote safe progress along an operation route while retaining fallback positions. Do not let an irrelevant distant skirmish hold every rear unit; retain the units actually needed to resolve contact. Validate choke-point throughput, full-stack alternate exits, movement-point differences and disembarkation.

Reinforcement should consider city siege/capture capability even when generic zone strength is already favorable. Stage forces outside the immediate battle and feed bounded tactical groups into it; do not blindly expand the 13-unit/6,000-state search. Account for units already committed in earlier groups and re-evaluate the actual resulting board.

Coordinate naval and air contributions with the land objective: useful coastal bombardment/collateral targets, reachable bases, carrier capacity, interception risk, fighter cover and bomber recovery. Keep independent naval staging requirements rather than assuming every city-held ship is a land defender. Do not divert an invasion fleet or an air group from its target solely because a nearby secondary target offers a small immediate score.

Acceptance: sustained sieges use available relevant forces, preserve capture capability, and choose protected stacks or dispersion for mechanical reasons. No new illegal stacks, stationary assignment loops or major search-memory growth.

### 6. Regression, replay and release gate

Deliver each phase as a separately reviewable change with its own native build and matching PDB. First test extracted pure policy code and focused disposable-game scenarios, then matched-save comparisons, then broader campaigns.

Required scenarios: safe rear city with three healthy melee units; threatened city with melee/ranged and cavalry/anti-cavalry; garrison replacement with no free neighbor; injured garrison versus healthy reserve; simultaneous fronts; blocked bridge; stable ETA-1 with no movement; relocating muster; disconnected coast/ocean restriction; missing required role versus empty optional slots; capital defense; city siege with surplus ranged but no capture unit; siege/bomber collateral dispersion; stack capacities 1,2,3,5,7,9/10; save/reload and logging Off/Summary/Verbose.

Compare unit-turns retained above assessed defense need, healthy unassigned unit-turns, duplicates/no-op garrison orders, operation recruitment/gathering age, actual reinforcements arriving, time to target, unit losses per objective, cities captured/lost and canceled/restarted operations. Also measure turn-time distribution, search states, log overhead and process memory.

Use several map layouts/civilizations/eras and a stacking-disabled control. Begin with short deterministic windows of the Danish save and other fixtures, then at least 100-turn campaign windows and eventually a complete game. Divergent AI decisions naturally change RNG consumption; compare objective outcomes across multiple seeds, not identical post-change worlds. Preserve user saves and use bounded guards only for explicitly disposable tests.

Do not claim a long-run win-rate or performance improvement from one campaign. If a change weakens defense or increases turn time materially, adjust or revert that phase before combining further changes.

## Original design controls and follow-up scope

The table below records the original design directions; it is not the current setting list. Current exact names/defaults/ranges are in the configuration reference linked above. Domain/city-role overrides can use dedicated tables instead of proliferating unrelated globals. Keep existing combat settings as the source of truth.

| Setting family | Initial proposal | Purpose |
|---|---|---|
| Safe-city baseline defenders | 1 | Ordinary city baseline; policy exceptions above |
| Immediate threat horizon | 2 turns | Reachable attack/capture risk, not raw hex radius |
| Uncertain approach horizon | 4 turns | Cautious reserve without treating every possible route as immediate danger |
| Capital/critical-city reserve and defense margin | Calibrate from baseline | Strength/importance needs, capped by useful deployment space |
| Garrison replacement improvement | Calibrate in common scoring units | Avoid equivalent swaps and repeated redundant orders |
| Reassignment cooldown / score improvement | 3 turns / calibrated margin | Reduce oscillation; emergency defense overrides cooldown |
| Assembly no-progress grace | 3 turns | Detect actual lack of progress including ETA 1 |
| Recruitment/gathering review ages | 5 / 5 turns | Trigger reevaluation, not unconditional departure |
| Failed-assignment cooldown | 3 turns | Prevent instant reuse of the same unsuccessful assignment |
| Long-range transfer budget and evaluation caps | Calibrate with late-game profiling | Bound CPU and pathfinding work |
| City marginal-defense, objective-progress and collateral weights | Calibrate with fixtures | Replace unconditional preferences with useful contribution |
| Diagnostic category/filter and detail intervals | Existing limits retained | Explain decisions without unlimited logs |

Persistent new assignment/cooldown history requires an explicit save-format decision. Prefer existing state and reconstructible caches where feasible; do not silently change serialized layouts. If new state is necessary, version it and document old-save behavior before release.

## Independent observer notification cleanup

Implement the requested UI behavior separately from AI changes: `UIObserverNotificationLifetimeTurns=3`, with 0 disabling it. A notification created on turn T becomes eligible at T+3. Use the engine's saved creation turn, including on reload; do not restart its age when EUI rebroadcasts it.

Run only for the active observer/autoplay view, through the ordinary UI removal path. Keep native restrictions on mandatory action notifications. Remove individual IDs so younger members of EUI bundles remain. Do not use a sparse ID table's length as a count, and do not bypass the DLL's notification rules with forced player dismissal.

Use event-driven bounded sweeps, detect observer exit/player changes and avoid reentrant removal. No per-frame world scan, gameplay orders, RNG or new DLL required. The supported implementation target is the VP EUI compatibility panel used by this prototype; non-EUI variants remain separate compatibility work.

Validate age boundary, zero/custom lifetime, save-style rebroadcast of old IDs, bundled notifications, sparse IDs, already dismissed entries, invalid/future timestamps, active-player switching, observer exit, autoplay with an ordinary player, normal play and nested notification events. Deploy only when the game is closed, with backup; no unreliable UI hot reload during the current campaign.
