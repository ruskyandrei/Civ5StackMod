# Edirne siege: capture capability and reinforcement follow-up

Recorded 2026-09-27; documentation only. The previous [war-preparation finding](war-preparation-review.md) is already on the todo list. User reports that around turn 138 Russia reduced Edirne to low HP by firing across water, without a suitable nearby military melee unit to take it. The desired behavior is to arrange a credible capturing force, or reassess/abandon an unproductive siege. No implementation, deployment, diagnostic-level change or game interaction was performed for this review.

## Evidence and uncertainty

Current run: PID22544, native session `Stacking-20260927T130616-455-p22544-r1`, DLL `Release-5.4.6-11-g9c33e26 Clean`, Summary logging. Russia is player4, Edirne is city1599 at74:36, Ottoman player8. Read-only log prefixes and SHA256/capture metadata: `C:/Users/rusit/Documents/Codex/Civ5StackMod-analysis/edirne-capture-20260927-133747`.

| Turn | Recorded observation |
|---|---|
|135|Edirne is a preferred Russian attack target, with Novgorod as muster. The city capture gate reports no eligible units.|
|136|Capture assessment: required damage86, expected maximum damage67, three candidates, melee count1.|
|137|Required damage46, expected maximum damage37, three candidates, melee count1.|
|138|Required damage32, expected maximum damage35, three candidates, melee count1. Tactical planning at74:36 evaluates three units against six enemies. The city remains an Ottoman target afterward.|
|138|Separately, operation3582 / army3583 begins recruiting toward Istanbul at75:31 from Novgorod70:32. Its recruited units include Swordsman2571, Heavy Skirmisher3419, Composite Bowman2432 and Great General3504. This is a competing objective, not proof it was wrong to choose Istanbul.|
|139|Edirne capture gate reports no eligible units.|
|140|Edirne assessment reports required damage52 versus expected damage15 and decides it is too early to attack.|

The logs support the low-HP siege observation. They do not establish literal absence of every melee unit: the capture gate counted one. Summary logging omits candidate identities and the chosen action breakdown, so we cannot determine whether this was an unsuitable scout, a ship, an exposed/wounded unit, a unit across an obstacle, or a valid candidate whose attack was rejected for another reason. No claim is made that every possible route to the city was impossible. Across-water bombardment and absence of an adequate capturing force are the user's visual observations; no live map probe was injected.

## Relevant code gaps

- `CvTacticalAI::ExecuteCaptureCityMoves` around925–991 evaluates expected damage and healing, then counts movable non-ranged candidates as melee. Its explicit no-melee early exit only applies when the city already has at most1HP. This coarse count does not certify an executable, survivable capture. The expected-damage estimate likewise is not a guarantee of capture.
- `FindUnitsWithinStrikingDistance` around4750 filters `isNoCapture` units and searches melee movement into the target's adjacent ring. That is useful screening, but adjacency alone is not proof of a legal final attack, adequate moves/strength, a safe water crossing or a survivable captured position. The later combat simulator can correctly reject the attack even when the earlier gate says `attempt`.
- Actual tactical simulation knows ranged attacks cannot capture and caps their final city damage. The missing work is connecting an unsuccessful capture plan to strategic reinforcement/target decisions, not allowing ranged city capture.
- `PlotReinforcementMoves` around2019–2164 has a coarse missing-melee branch only under friendly overall and ranged dominance, and uses zone melee strength rather than a target-specific capture plan. Land and water zones are handled separately. Other gates can prevent recruitment, including the early return for a foreign-owned zone with no enemy unit count; these deserve fixtures, not an assumption that every gate fired in this replay.
- `CvStackingAI::TryReinforceRearUnit` currently creates demands for threatened own cities and active offensive armies. It has no persistent demand for a vulnerable enemy city being bombarded by loose tactical units. Its native-domain transfer paths intentionally forbid embarkation. Cross-water capture therefore needs coordination with existing land routes, naval melee or controlled landing operations rather than simply sending an arbitrary nearby melee unit.

## Todo scope — no changes implemented

1. Add a shared, target-specific capture assessment: viable capturer identity, domain, health, capture permission, actual attack/approach route, moves, landing/embarkation requirements, expected arrival and survival after capture. Count committed/inbound support once. A melee unit in the wider zone or a ranged stack on the opposite bank must not fulfill this requirement by itself.
2. Treat a siege without that plan as an explicit capture-role deficit. Reserve/recruit a suitable land melee unit or, for a legally accessible coastal city, naval melee; coordinate escort/landing support where needed. Protect home defenses and useful frontline stacks. Reconsider competing operations when a reachable, almost-captured city presents a better opportunity.
3. Connect bombardment timing to the capture ETA. Continue useful softening/support while a credible force is coming; reevaluate if that unit dies, is reassigned, loses its route or cannot survive. Track siege progress across turns instead of restarting the decision from the city's current HP each time.
4. If no practical capture route/force can be assembled within a bounded window, reduce priority, retarget or withdraw as appropriate. Retain bombardment with a concrete independent benefit such as damaging defenders/collateral, denying healing for an imminent allied capture, or a worthwhile blockade/plunder objective. Do not use an unconditional ban on ranged-only attacks; compare their marginal benefit, risk and opportunity cost.
5. Put new capture-ETA limits, minimum force/health margins, reinforcement priorities, siege-progress windows and reassessment/abandonment thresholds in XML. Add Summary records for capture readiness/deficit, chosen reinforcement and continuation/retarget reason; Verbose records for rejected capturer identities, legal-route/attack checks, landing risk and the actual failed-plan reason.
6. Regression cases: Edirne around136–140; ranged fire across an impassable/unavailable crossing; a safe long land route; reachable coastal naval capture; an inadequate scout; a blocked or wounded capturer; stacking congestion; a capturer lost/reassigned while en route; isolated city with no defending units; a siege without an active army; competing Istanbul/Edirne objectives; ordinary ranged softening with support already arriving. Measure conversion of low city HP into captures, delay, casualties and troops freed by abandoning genuinely futile sieges.

This extends the plan's existing role-aware siege requirement from counting melee strength to maintaining a feasible capture plan through execution. Live attribution of the one melee candidate remains a diagnostic follow-up; code review alone cannot identify it.


## User screenshot: water crossing and possible Spanish border restriction

The user supplied an annotated close-up showing Edirne on the far shore and the circled Russian bombardment stack across the water to its southwest. Spanish territory is visible to the west/left. The reference is preserved as `user-edirne-cross-water-reference.png` beside this investigation's archived logs, with its own SHA256 metadata.

This supports a geographic explanation for ranged pressure without an immediate capture: firing across water does not establish a legal melee approach. A land capturer needs a legal route around the inlet or a permitted, viable crossing/landing; a naval melee capturer is an alternative only if the city and route are legally accessible. Enemy defenders, remaining moves and post-capture survival also matter. Closed Spanish borders could obstruct a western land route, but treaty state and all alternative paths cannot be established from this image. Treat that as a hypothesis, not a confirmed cause or proof that the city was unreachable.

Add an explicit regression for this configuration: ranged stack across an inlet, neutral third-party territory on the land approach, open versus closed borders, and embarkation/landing unavailable versus feasible. Assess the route under the actual unit's ownership, movement permissions, domain and expected attack state. Broad mixed-army reach searches that traverse foreign territory are candidate enumeration, not proof of a usable capture route. The current strategic rear-transfer helper's no-embark restriction is another relevant boundary; a controlled landing operation must be requested when appropriate rather than silently assuming the helper can ferry a melee unit across.
