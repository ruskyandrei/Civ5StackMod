# Decisive-war follow-ups from campaign47

Draft for a separate AI issues/improvement note. This is an evidence review and investigation plan, not an implementation or a balance change. Performance work remains the immediate priority. No DLL, XML, SQL, or gameplay source was changed for this review.

## Scope and outcome

Campaign: `work/test-runs/campaign47-20260930-1735`, native session `Stacking-20260930T163501-573-p39396-r1`, DLL47 source commit `3b008c0d4`. The user stopped the campaign and saved at turn251. The retained turn250 checkpoint is the final city-ownership observation used here.

There were no city captures during the first200 turns. The first observed conquest was Songhai taking Panama City on207. Songhai took Arpinum from Rome on227; Mongolia took Dublin on230. All three remain under their capturing civilizations at250:43,23, and20 turns of observed retention respectively. These are durable gains within this observation window, not immediate recaptures. There are also other late captures, including a barbarian capture and a subsequent transfer by conquest; raw capture-event totals should not be treated as major-civilization conquest success.

This single campaign cannot establish how much stacking changes conquest rates against ordinary VP. It does establish concrete cases where a prepared-looking force fails our readiness policy, and where production, recruitment, and useful local fighting do not become a sustained city attack. War-pair counts include allied city states and do not represent independent, voluntary offensive campaigns.

## 1. A viable early opportunity can disappear while assembly waits

**Observed:** Songhai's Rome forecast on55 had8 ready units against8 desired,5 capturers,253 predicted city damage,16 predicted healing,364 cityHP, and capture ETA0. The logged failure was reason6: arrival estimates spanned0–2 turns, exceeding the configured one-turn spread. `enemyStrength=11` is the aggregate visible-threat estimate, not necessarily the displayed city strength. Only one real city shot followed on56, for34 damage. By60, Rome had464HP and the requirement had become12 units plus4 siege; the force had9 ready units and no siege. The64 checkpoint confirms Rome at full464HP and displayed strength17.

**Code:** `CvStackingOffensiveAI::AssessAssault` uses the minimum and maximum arrival ETA across every counted healthy unit. One slower member can invalidate the whole wave. `DesiredAssaultUnits` and `DesiredSiegeUnits` recompute requirements from capacity and `KnownFortified`; the latter recognizes visible city strength or collateral protection. These are hard readiness gates, not just planning preferences.

**Hypothesis:** The full-group arrival-spread test may reject a sufficient first wave because of extra, slower reinforcements. Defenders can finish fortifications while this force waits, creating a much harder target. The forecast does not prove that attacking on55 would have succeeded.

**Concrete check/improvement candidate:** Evaluate whether a coherent subset already contains a capturer, enough siege, sustainable damage, and adequate protection, while slower arrivals remain reinforcements. Verify an early force with one slow optional member, a slow essential capturer, and a slow essential siege unit separately. Do not simply remove cohesion or permit piecemeal attacks into concentrated defender fire.

## 2. Force targets can outgrow an affordable or sufficient army

**Observed:** Dublin's target rose from14 to18 units between155 and160. By195 Mongolia had21/18 ready units,8/5 siege,8 capturers, and391 forecast damage against446HP; the logged blocker remained arrival spread0–3. At200 it still had19/18 ready and7/5 siege with capture ETA0. One safe cannon shot on198 did23 city damage, but the city healed before a committed wave. This attack eventually succeeded on230.

**Observed:** Rome's fleet near Panama City was at war with Songhai and had14/22 ready naval units on235,7 ranged ships against4 required,7 capturers, capture ETA0, no inbound units, and all counted arrivals at ETA0. Forecast damage266 and healing23 were sufficient for the configured four-turn damage horizon against470HP. It remained in phase2/reason4. There is no capture-ship or cohesion shortage in that particular sample; quantity and/or strength remains the gate. Strength sufficiency is not separately logged. The screenshot's three stacks are not an exact census of eligible ready units.

**Code:** `DesiredAssaultUnits` uses base units plus capacity-based increments and a fortified-city increment, for both land and sea. `AssessAssault` normally requires both a minimum unit count and strength/damage tests; fewer units bypass the count only when predicted one-turn damage already covers all cityHP and the strength test passes. Current diagnostics expose one precedence-ordered reason rather than every failed predicate.

**Concrete check/improvement candidate:** Separate minimum essential roles, effective combat power, sustained damage, and desired reinforcement reserves. A larger desired army should not automatically make an already sufficient force unusable after a technology unlock. Compare naval and land requirements with actual supply and production budgets. Add a fixture where capacity increases while a viable army is already staged, and one where a strong smaller fleet cannot deal all required damage in one turn but can sustain a short siege. Retain strict rejection of genuinely weak attacks.

## 3. Reinforcements must contribute to the objective, not just arrive nearby

**Observed:** Through150,7 offensive-production completions explicitly targeted Rome. Support records mention29 distinct units and repeated front/assembly arrivals. Unit2964 completed on124, arrived at assembly on126, lost its commitment for `no_progress` on135, and still attacked Roman field units on141,149,150. Arrivals and surviving units therefore exist, but do not establish city-attack participation. Rome's Songhai objective later expired for peace on195; that diplomatic end is not evidence of a claim-expiration defect.

**Code:** `Refresh`, `RecordTransfer`, `StageUnit`, `TacticalForces`, and `ReviewObjectives` govern continuity. Progress uses city distance, lower ETA, stage proximity, ready-unit changes, cityHP changes, and real production progress. These are imperfect proxies for assault progress. Stage proximity can keep a unit's commitment fresh; production progress and new arrivals can keep the objective useful while no city attack occurs. Conversely, a legal detour or valuable local fight may be labeled no progress. The existing stalled-queue resurrection fix should remain intact.

**Concrete checks:** Trace a produced unit through queue completion, dispatch, stage arrival, ready-wave credit, actual city/defender combat, reassignment, and release. Distinguish holding necessary reserves, protecting a threatened home city, real transport delays, and permanent assembly. Test detours without adding per-turn path searches. Check that attrition triggers replacement production before the remaining siege core collapses, and that useless objectives eventually release commitments despite fresh but ineffective local arrivals.

## 4. Production incentives can conflict with global supply and economy decisions

**Code evidence:**

- `CvUnitProductionAI::CheckUnitBuildSanity` can reject candidates for maintenance, land/naval recommendation limits, supply, resources, training, or deployment space before the stacking offensive bonus is added around1590. Increasing `AIOffensiveProductionPriority` cannot rescue a candidate already rejected by these checks. A flavor weight below1 is also rejected before this bonus.
- `CvMilitaryAI::SetRecommendedArmyNavySize` starts from `CvEconomicAI::GetSoftSupplyCap`, divides affordable units between defense, land offense, navy, and explorers, and still uses `BALANCE_BASIC_ATTACK_ARMY_SIZE` when weighting preferred offensive targets. This recommendation need not agree with one city's18–22-unit assault requirement plus reserves and home defense.
- `CvEconomicAI::GetSoftSupplyCap` considers gold and war/approach conditions. `CvMilitaryAI` may scrap or gift units when in deficit or over supply; oversupply is therefore not a free way to meet our larger targets.
- `ProductionChoice` credits healthy matching units and queued support/formation promises, limits concurrent support builds, and favors missing essential roles. Staffing credit is not the same as reaching a legal attack position. Formation and support ownership are intentionally separate.

**Not yet demonstrated:** The retained campaign checkpoints contain city/player counts, not historical supply caps, treasury, build-candidate rejections, or scrapping reasons. We cannot currently blame a specific siege shortage on money or supply. A `unit_unusable` release is not a death or scrap record.

**Concrete checks/improvement candidates:** At sparse campaign checkpoints, record actual supply, soft cap, recommended army/navy size, gold balance, war weariness, role inventory, and active objective demands. Use existing MilitaryAI and city-production logs for `nosupply`, `tooexpensive`, `unitbalance`, and `impossible` rejections. Test a supply-full force with too many interchangeable melee units and too little siege: reassignment, upgrade, or replacement should be evaluated before asking for more units. Match the desired offensive budget to resources available after essential defense. Preserve solvency and supply safeguards.

## 5. Distinguish ordinary city toughness from stacking defense and prediction error

**Observed:** Rome grows from strength17/full464HP on64 to strength44/full568HP on150 and strength55/full616HP on199. At250, Rome remains Roman with688HP; Panama City and Dublin have794HP and Arpinum778HP. Much of this is ordinary population/building progression. An isolated34- or23-damage shot cannot create persistent progress against healing without regular follow-up.

**Code:** `CvCity::GetMaxHitPoints` adds configured baseHP and building/population extras; `updateStrengthValue` includes buildings and ordinary modifiers. Only one selected garrison contributes the normal unit-strength bonus. Additional stacked units provide their own attacks and defensive bodies, not additive normal garrison bonuses for every unit.

**Specific approximation to audit:** Actual `CvCity::doTurn` healing includes base healing, building-defense healing, VP population, potential triple healing when no damage was taken last turn and no city plot is blockaded, and applicable defense-process healing. `AssessAssault` currently estimates only base plus population, unless fully blockaded. This can overestimate sustainable siege damage in some circumstances. Updating this estimate is a correctness candidate, separate from reducing actual healing or fortification strength. Read only information available to the AI and preserve the fully blockaded zero-healing case.

**Hypotheses/checks:** Compare cityHP damage, garrison absorption, collateral damage, and defender attacks separately. Compare a city with one defender against an otherwise identical ranged stack, using the same attack units and fortifications. Check whether early available siege can sustain damage through walls before changing city balance. The current mod disables city ranged attacks; stacked ranged defenders can still create concentrated fire. Test actual blocker predicates and city-healing estimates before changing damage, siege penalties, fortifications, or the collateralHP floor.

## 6. War preparation and target selection must match conquest feasibility

**Code:** `OpeningReady` checks staged healthy units, capture/ranged/siege roles, and aggregate strength; `ReadyToDeclare` gates a specific voluntary city-attack declaration path in `CvDiplomacyAI`. This does not cover every bribe, pact, ally, scripted, or already-active war. Readiness is not a promise of attack execution. Target scoring in `CvMilitaryAI` combines approach/path/desirability/economic value and current cityHP; it should be reviewed alongside actual defenders and the production budget needed to take the city.

**Concrete checks:** For voluntary wars, link the readiness record, operation target, force composition, declaration, first city attack, and first capture. Preserve cause distinctions; five native `WAR_DECLARATION` records are not the complete declaration history. Check whether the opening force can sustain a siege, whether defenders are reachable in its domain, and whether the economy can replace losses. Penalize objectives that are inaccessible or require unattainable forces; prefer reinforcing a viable attack over creating several underfunded goals. Do not demand conquest readiness for a forced defensive war.

## Suggested order after performance work

1. Validate count/cohesion readiness on preserved Dublin and Roman-fleet positions; log individual failed predicates and eligible/excluded unit counts in bounded diagnostic windows.
2. Reconcile offensive targets with supply, affordable army/navy recommendations, and role production. Diagnose rejected siege builds before tuning incentives.
3. Verify reinforcement contribution and abandonment, keeping the queue-ownership/stall fixes and avoiding new per-turn path work.
4. Compare actual city healing and attack forecasts; then assess early fortified-city balance with controlled tests.
5. Review voluntary-war preparation and target selection with the resulting feasible-force model.

Meaningful success measures: shorter declaration-to-first-effective-attack delay; sustainable cityHP reduction; fewer long1HP sieges without capturers; reinforcement units that actually contribute; durable holdings10/20turns after conquest; reasonable defensive retention; stable economies; and acceptable complete-turn times. Do not optimize for capture-row volume, phase1 counts, or permanent aggression alone. Use more than one fresh campaign and a carefully controlled ordinary-VP comparison before drawing balance conclusions.

## Evidence references

- Campaign native segments0–8; checkpoints64,150,181,199,236,250; `manual-stop-proof.json` confirms the251 save.
- `CvStackingOffensiveAI.cpp`: `ProductionChoice`308+, `DesiredAssaultUnits`560+, `AssessAssault`584+, `ReviewObjectives`875+, `RecordProduction`918+, `OpeningReady`1246+.
- `CvUnitProductionAI.cpp`: candidate sanity gates176–350; offensive production bonus1590.
- `CvMilitaryAI.cpp`: target score1272+; military budget1744+; deficit/oversupply scrapping2550+; existing military inventory/supply logging3031+.
- `CvEconomicAI.cpp`: `GetSoftSupplyCap`929+.
- `CvCity.cpp`: healing2332+; strength27501+; garrison27612+; maximumHP34322+.
- `CvDiplomacyAI.cpp`: voluntary readiness gate27651.

Line numbers refer to the reviewed local code and may move. Function names and the campaign/source IDs are the durable references. Summary diagnostics are intermittent; a missing forecast is not proof a unit was idle, and phase0/2 does not prove it never fought field units.

## Implementation status — 1 October 2026, DLL102

The first-wave/count distinction, own-army core admission, voluntary opening
feasibility, bounded affordable role-production exception, queue/staff lifecycle
invalidation, verified reinforcement route progress, actual combat contribution,
ready-siege net-progress timeout and shared legal-information healing forecast
are implemented. New numerical controls are XML-configurable. Directed tests,
native build/deployment and two saved251→255 replays pass. Dense253 takes59.641s
and59.375s versus57.517s accepted control, within the10% ceiling. See
[implementation and acceptance](ai-followup-20261001.md) for source IDs,
configuration qualifications and test coverage.

The short replay adds real city attacks at Hippo Regius, The Hague and Cumae;
it retains the control's Utrecht capture. It does not establish more durable
conquests. Remaining evaluation: fresh voluntary-war and operation-core scenarios,
24-turn abandonment and reinforcement-arrival behavior, early fortified-city
balance, supply/economy stability and10/20-turn conquest retention across multiple
campaigns. Rome's observed fleet was on naval-superiority missions, with no city
assault in the retained evidence; deciding when such a fleet should become a
city-attack force remains a separate strategic follow-up. Do not retune city
strength/healing or enlarge tactical search limits from these four turns alone.
