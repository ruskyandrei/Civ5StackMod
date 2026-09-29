# Siege composition, production and replacement

Recorded 2026-09-30 after the user observed city-attack forces losing their one or two siege weapons and leaving melee units exposed against fortifications. Investigation and TODO only: no gameplay, XML defaults, deployed files or active autoplay settings changed.

## Confirmed composition gaps

The current offensive support policy in `CvStackingOffensiveAI::AddDemands` (around lines 343–370) counts all ranged attacks together and uses `AIOffensiveSupportMinimumRanged=2`. Ordinary archers can meet that minimum without any siege weapons. The opening-readiness policy likewise counts `IsCanAttackRanged`, so a staged core can satisfy its ranged requirement without effective city bombardment.

`CvTacticalAI::PlotReinforcementMoves` (around lines 2046–2065) has a separate missing-siege check when friendly overall/ranged dominance would otherwise stop reinforcements. Its default `AICityAssaultMinimumSiege=1` counts nearby units whose current AI role is `UNITAI_CITY_BOMBARD`. It does not require a target-specific damage budget, a healthy protected battery, actual firing access or replacements before attrition. A siege weapon assigned a different AI role can also be missed by that role-only count. This gate does not run for every posture/dominance combination.

The formation templates in `(1) Community Patch/Database Changes/Units/CoreNewUnitFormations.xml` contain siege preferences, but allow ranged substitution:

- The small city-attack force used in Classical/Medieval eras has two required bombard slots, each with primary `UNITAI_CITY_BOMBARD` and secondary `UNITAI_RANGED`. It also has three required front-line slots and two optional front-line slots.
- The basic Renaissance/Industrial force has three required bombard positions, with interchangeable siege/ranged primary and secondary roles, plus two optional siege-preferred bombard positions.
- The bigger Modern-or-later force has only two required siege-preferred bombard slots and one optional such slot, all allowing ordinary ranged replacements, alongside four required and two optional front-line slots.

Thus filling an army's required slots is not a guarantee it can damage a fortified city effectively. The bigger template also does not automatically provide more siege weapons. `MilitaryAIHelpers::GetCurrentBestFormationTypeForLandAttack` (around line 4333) chooses these templates by era, rather than the particular target's fortification/HP/damage requirement.

## Campaign evidence and limits

The frozen logs referenced in [the siege-staging review](siege-staging-review.md) contain a clear example: the initial Celtic Memphis operation 2237 on turn 101 recruited five melee/mounted units and two Composite Bowmen, with no siege weapons. That is the initial operation roster, not a complete census of later tactical arrivals.

The American operation archive contains repeated land-attack rosters with a single Catapult: operation 2862 on 126 recruited four Spearmen, one Horseman, one Catapult and one Composite Bowman, plus a Great General; operation 2988 on 131 recruited a Swordsman, two Spearmen, one Catapult and one Composite Bowman. These counts describe recorded recruitment events. They do not identify which complete roster fought outside London on 162–168 or prove why each siege unit was subsequently lost. London's actual weak city damage is established separately by its combat traces.

## Production is broader than a missing count

VP already tracks siege separately in `CvMilitaryAI::UpdateBaseData`. Its `IsTestStrategy_NeedSiegeUnits` and `IsTestStrategy_EnoughSiegeUnits` (around lines 4159–4173) use empire-wide siege/melee ratios and `FLAVOR_SIEGE`. `CvUnitProductionAI` applies corresponding strategy bonuses/balance checks. These are useful general composition controls, but are not a city-objective damage or replacement requirement. A player can have some siege globally without having enough healthy, reachable bombardment for its current offensive.

Our `CvAIOperation::RefreshReinforcementRequests` (around lines 343–362) adds production requests only while a city-attack operation is moving, only for free unpromised formation slots, with a default two pending/in-training requests. Slots are traversed in formation order. Occupied interchangeable ranged slots cannot request additional true siege merely because the target needs it; early melee vacancies can use the request budget. After tactical handoff, this function does not maintain a separate production queue for the continuing objective. Increasing only a tactical siege-count constant cannot solve those production/assignment gaps.

## Planned changes

1. Give each city objective separate requirements for effective bombardment, field ranged support, protective melee/anti-cavalry and actual capture support. Classify by configurable capabilities and unit/promotion data rather than only the current AI mission role. Handle unique siege weapons and support units explicitly; a unit that cannot damage the city must not fill its bombardment requirement by name alone.
2. Increase the desired healthy siege force for fortified targets. Combine an XML-configurable minimum/proportion and bounded reserve with expected useful city damage after healing, city strength/HP, defender pressure, firing positions and available technology. Count only ready/committed units with credible routes, setup/movement and arrival times. Several siege units are generally a better initial battery than one fragile weapon, but choose defaults through fixtures rather than imposing the same count on every city.
3. Prevent ordinary ranged substitutes and extra melee from concealing an unmet siege requirement. Adjust formation siege preferences/requirements where appropriate and use objective readiness to handle composition beyond fixed slots. Preserve viable early attacks before siege technology, weak-city captures and coastal/air bombardment alternatives when they provide actual damage and can operate safely.
4. Create target-linked siege production and recruitment demands during preparation, approach and the ongoing siege, including after tactical handoff and when ordinary slots are occupied. Prioritize the missing role and timely replacements through VP's existing production/supply/economy safeguards. Reserve each produced/inbound unit once, credit its ETA/health conservatively and cancel obsolete promises. Reassess a siege if required bombardment cannot arrive in time.
5. Recruit and dispatch reserve siege before the initial battery is lost. Stage it safely with suitable screens, use protective stacks or dispersion according to collateral/flanking risk, rotate wounded weapons and preserve capture support. Feed arrivals into the shared assault-wave plan; do not leave melee exposed waiting for artillery or advance an unprotected replacement alone.
6. Log compact desired/ready/healthy/inbound/training role counts, predicted city damage versus healing, role deficits, production refusals/assignments and replacements actually arriving. Record at phase changes or existing bounded intervals; keep rejected candidate details in filtered Verbose windows. Measure siege losses and replacement gaps as well as captures.

All new minima, ratios, reserve counts, health/strength margins, damage/readiness horizons, production priorities, work budgets and diagnostic intervals must be XML-configurable. Keep unit capabilities configurable through XML/database data where practical. Do not globally increase siege production irrespective of active targets, supply, threatened home cities or other fronts.

Acceptance cases: strong fortified city with abundant melee but no siege; archers occupying every interchangeable bombard slot; one siege unit lost/wounded with replacements already committed; a full formation needing additional bombardment; an operation handed off to tactical control; siege before/after technology unlock; unique siege/support units; blocked/setup-limited firing positions; naval/air alternatives; multiple targets competing for the same production; safe staging/stack screens and collateral exposure. Validate actual paths and production assignment in game after bounded offline policy checks, then compare sustained city damage, siege survival, reinforcement gaps and captures across campaigns. This extends the staging/capture plan rather than replacing it.


## Larger assault forces enabled by stacking

User direction added 2026-09-30: expand desired unit counts and concentration for rapid city assaults, because the inherited formations were designed for one combat unit per hex. This also applies to protective/capture troops, ordinary ranged support and follow-up reserves, not only siege weapons. Documentation only; current gameplay targets remain unchanged.

The current custom support policy uses a minimum of six combat units, remembered core plus two reserve units, and an eighteen-unit maximum per target/domain (`CvStackingOffensiveAI::AddDemands`). These are our recent prototype defaults, distinct from the inherited small/basic/bigger formation templates. Desired strength can request more than the count minimum, but a small remembered core and interchangeable roles can still yield a small or unsuitable assault. Fixed-slot production and tactical handoff constrain how larger demands are fulfilled.

Expand formation combat capacity, target/core counts, required role counts, reserve/replacement allowances and production/recruitment throughput together. Scale desired concentration with the attacker's unlocked stack capacity, target strength/HP and defenses, actual firing/approach space, available military and credible reinforcement arrival. A larger permitted stack should let the AI plan several protected stacks around the target and bring the ready wave forward in one AI turn. Count troops that can participate, not simply units in the surrounding region or distant production promises.

Provisional ranges for calibration, not implemented defaults:

| Offensive | Ready combat force | Effective bombardment within that force | Follow-up reserve |
| --- | ---: | ---: | ---: |
| Ordinary fortified city | 12–16 | 4–6 | 4–6 |
| Strong city or substantial defending stacks | 18–24 | 6–8 | 6–8 |

These are objective totals across multiple hexes; they are not per-hex stack limits or an unconditional minimum for every target. Retain smaller opportunistic attacks against weak cities and before bombardment technology, and credit genuine naval/air alternatives separately. A large objective may need an allocation ceiling around 24–32 ready plus reserved/inbound combat units for the first calibration, rather than the current eighteen; make all ranges, ceilings, scaling and role shares XML-configurable. Resolve the final defaults through bounded fixtures and campaign comparisons. Supply, production capacity, legal terrain/borders, collateral exposure, home defense and other fronts remain inputs to feasible commitment.

The thirteen-unit tactical search and 6,000-state storage are calculation limits, not the desired total military force. Retain those bounds initially and support coordinated batches within the same AI turn, with processed-unit/target reservations, critical-role coverage and reassessment against the resulting board. Additional units must not disappear after the first candidate truncation or all be marked processed merely because one batch planned. Bound total work per objective/player and measure turn time: more batches increase cost even if each individual search is capped. Prefer larger reinforcement of an existing viable offensive over more fragmented unrelated operations.

Validation should include low/high unlocked stack capacities, several simultaneous protected stacks, a force above thirteen participating across batches in one turn, restricted approaches that cannot employ the full desired force, production/arrival accounting above eighteen, role-preserving wounded replacements, weak-city opportunities, competing fronts and collateral-heavy defense. Log desired/assigned/ready/inbound counts and cap/space/supply reasons compactly; measure first-wave participation, assault duration, capture conversion and AI processing cost. This is the broader force-size requirement for the siege/staging implementation, not just an instruction to turn up one constant.
