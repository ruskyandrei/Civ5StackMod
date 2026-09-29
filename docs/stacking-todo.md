# Stacking development TODO


## Implementation checkpoint — 2026-09-29 (offline pass)

The older unchecked bullets below describe the full design, including campaign validation and advanced coordination. This checkpoint implements the following bounded first pass; see [configuration](stacking-configuration.md#offensive-continuity-and-damaged-fortifications-2026-09-29) and [validation record](offensive-ai-implementation.md).

- [x] Keep a prepared city-assault army assigned through voluntary declaration; replace discovery-based readiness with a healthy staged core, roles, visible strength and approximate legal opening route. Revalidate the readiness flag at declaration. Other immediate-war paths remain intact.
- [x] Remember city objectives and core/support commitments across tactical handoff. Prefer reinforcing those targets, with role, strength, reserve and lead-time allowances, bounded incoming/training credit and expiry. Safe arrived reserves stay near the army; suitable arrivals can fill actual unpromised formation slots.
- [x] Let moving formations request bounded optional/replacement combat production through VP's existing exclusive reservation and supply/economy machinery. Bound production plus approximate travel time and prevent overwriting an already occupied slot. Further production outside formation slots remains open.
- [x] Check the actual muster/deploy route before recruitment; recover disconnected centroid routes from bounded actual unit origins; delay repeated failed target/domain retries. Review stalled moving armies and let an unexposed core advance after peripheral opportunity combat.
- [x] Assess actual capture paths, unit health and projected capture retaliation, including naval melee and visible adjacent co-belligerents. Request missing roles and stop prolonged low-HP city fire with no feasible capture plan when no useful collateral remains. Unknown path-budget results do not assert infeasibility.
- [x] Scale capped fortification collateral protection with pre-hit city HP, including virtual prior damage in multi-hit attack/danger forecasts; retain XML toggles and existing damage rules.
- [x] Move the roster above measured combat-preview bounds, including the outcome banner. Constrain its scroll area/width, restore baseline placement after preview closes, and hide rather than overlap if the preview leaves no room.
- [x] Add XML controls, native diagnostic explanations and offline regression coverage. Keep 13-unit / 6,000-state tactical limits unchanged.
- [ ] In-game smoke checks, fresh autoplay with Summary diagnostics, selected Verbose siege windows, save/reload and comparative campaign calibration. No game was launched during this implementation pass.
- [ ] Extend coordinated amphibious capture transport/escort, production after army handoff or beyond formation slots, measured attrition/arrival forecasting, wounded rotation and cooperative-war timing. The first pass improves their inputs but does not implement all of these systems.

## Earlier checkpoint

Release20260927-105159 (`Release-5.4.6-8-gef54698 Clean`) compiled 176 translation units with native VC9 in 67.968 s and is deployment-verified (`105445-e3f58adf`). DLL SHA256: `D25416742EE592C3673DFED18F1C6816D8A4685C91707362C2B5DDA3A26BC3E7`. The final bounded Turn240 replay progressed into turn246 with no new crash, no LONG_PLAN warnings and no memory threshold. The guard stopped it at180 seconds during player41; turn246 and the campaign were not completed.

## Completed implementation and validation

- [x] Add native DLL diagnostics without an injected Lua observer. The direct top-center Diagnostics button is deployed and visually usable; Off, Summary, Verbose, Close and Escape were tested in game. The original EUI dropdown access problem is resolved. `StackAutoplayObserver` was nil during native validation.
- [x] Add XML defaults for summary/detail/memory intervals, player filtering, row/file limits, histogram overflow bucket and long-plan warnings. Runtime level changes apply only to the loaded session.
- [x] Record per-player/turn structural statistics, wounded/illegal units, stack-size histograms and bounded virtual-memory samples. Verbose records expose unit roles and city/garrison identities. Composition is explicitly separate from a safety forecast.
- [x] Record city-attack gates, recruitment filters/budget drops, chosen assignments and score components, operation messages, and bounded long-history warnings before assignment insertion. Search limits remain 13 units and 6,000 states.
- [x] Add actual-combat before/after logging using saved owner/unit IDs, including primary/secondary/garrison participants, explicit inflicted-versus-received damage labels, and post-resolution positions. Missing-unit records do not automatically assert combat death.
- [x] Add run/build/configuration identifiers and immediately flushed, live-readable rolling files. Off/On retains the loaded session's ring; new sessions have separate prefixes. Fixed workspace, cached settings, recursive locking and TLS status snapshots avoid unbounded diagnostic state.
- [x] Validate logger policy with 36 actual-source VC9 checks and the corrected UI with 55 Lua checks plus the existing roster suite. Observer/autoplay visibility is implemented and the button was visible in the live observer run; normal-player hiding, empty-hex dismissal, same-unit flag reopening, row selection and movement cancellation also passed in a separate live check. Confirm no gameplay orders or RNG calls in the diagnostics code. Live logs are in the correct engine Logs directory and readable while the game runs; Off/resume retains the same prefix and opens segment 1.
- [x] Implement the selected AI improvements: stronger protection at visible fog edges, conservative protected siege approaches, city-specific bombard protection preferences, unique-hex blockade estimates, and a bounded alternative exit for a full-stack blocker. All 41 targeted actual-source VC9 checks pass; representative live coverage remains pending.
- [x] Correct the ineffective VC9 danger-vector shrink expression. All 71 actual-source checks and independent review pass. This establishes capacity release, not a measured memory saving or a crash fix.
- [x] Prepare the bounded external memory watcher; 28 offline checks pass. The coordinator also recorded one successful read-only sample of the actual DX11 game. The final replay also exercised the exact-process duration stop at 180.034 s. Memory thresholds did not fire; earlier guards closed already-crashed processes and must not be counted as crash prevention.

- [x] Compare fresh processes loading `auto_test_1` from Turn 0 through one autoplay turn with logging Off versus Verbose. All captured fields match for 60 units and 30 cities, with no illegal-unit flags. This is one captured-state comparison, not proof of every game-state value or long-run equivalence.
- [x] Verify an actual catapult shot and its native combat trace: 30 assertions pass, primary damage is 34, two secondary victims take 6 each, and all four logged participant IDs/HP before and after agree with the fixture. The pre-fixture native archive has 395 rows; the final 494-row archive includes the fixture and level toggles and is not a second benchmark.

## Remaining validation and extensions

- [ ] Extend off/on equivalence, event-count and save/reload validation to later turns and more event types. The single-turn comparison and one collateral shot do not establish whole-campaign determinism or exhaustive logging coverage.
- [x] Diagnose and correct the demonstrated same-tile no-op loop and separate NULL endpoint fault (39 and16 native checks). Replay the original Turn240 save without a Lua observer on 105159: progress into246,5,836 native records, no LONG_PLAN/TRUNCATED and no new crash. The former Spain244 target103:20 finishes with24 assignments, including terminal markers for unit7508. The180-second stop leaves246 incomplete; the retention-only fix was insufficient in the earlier run.
- [ ] Measure overhead on a large late-game position, including disabled logging, collection time, output cost and the effect of truncation/rotation. The duration stop is now exercised; memory-threshold/completion-signal behavior remains a separate validation scope. Preserve original saves.
- [ ] Extend decision explanations where needed: the current chosen-plan components are not an exhaustive trace of every protector, concentration penalty, defender or cavalry-interception alternative. The actual catapult trace proves one result path; broader forecast-to-result correlation still needs runtime evidence.
- [ ] Add area/category filters if useful; current filtering is by player. Add explicit city-stack and anti-cavalry aggregate statistics if needed; current verbose identities/flags support inspection but are not all dedicated summary fields.
- [x] Live-check normal-player diagnostics hiding and empty-hex roster dismissal, same-unit reopening, row selection and movement cancellation on the final DLL. Original units retained their HP and moves; the game closed normally. Evidence: `work/test-runs/ui-final-20260927`.
- [ ] Continue broader AI/balance coverage: collateral dispersion, naval/air strategy, sustained city sieges, long campaigns, multiplayer and unrelated-mod compatibility.

Final replay memory: peak private2,423.832MiB, peak committed+reserved3,218.863MiB, minimum free877.012MiB and minimum largest block724.312MiB across176 samples. These values describe one bounded run; no overhead or leak-free claim is made. Evidence: `work/test-runs/turn240-final-20260927/native-summary.json`, `memory.out`, `provenance.json` and `independent-readout.json`.

The temporary [Lua autoplay observer](../work/AUTOPLAY-OBSERVER.md) remains an earlier structural-data tool, not a requirement for the native logger. See the [configuration reference](stacking-configuration.md), [core review](../work/DIAGNOSTICS-CORE-REVIEW.md), [UI checks](../work/DIAGNOSTICS-UI-REGRESSION.md), [memory watcher](../work/MEMORY-WATCH.md) and [crash investigation](../work/CRASH-245-20260927.md) for evidence and limits.

## Military allocation follow-up (2026-09-27)

- [x] Implement the first bounded [military AI allocation pass](military-ai-plan.md#implementation-checkpoint--2026-09-27): shared retention, useful garrison orders, reserve transfers, domain budgets, assembly recovery and native explanations. Campaign calibration and advanced naval/air planning remain open. See `work/MILITARY-AI-IMPLEMENTATION.md` for release evidence.
- [ ] Compare rear-city surplus, operation assembly delays and actual front arrivals against the Danish replay and independent offensive/defensive scenarios before tuning broader policy.
- [x] User confirmed three-turn observer notification expiry working in autoplay through turn 330. Offline age/rebroadcast/normal-play cases also pass; this report does not add an independent live save/reload boundary test.


## Pre-war preparation and initial offensive (fresh autoplay, 2026-09-27)

- [ ] Strengthen voluntary war readiness and preserve assault commitments across declaration. [Russia–Ottomans investigation](war-preparation-review.md): five units recruited on 105; a visibility shortcut marked them ready/successful on 112 despite 6–11 hex distances to Istanbul; war declared and operation ended on 113; the same spearmen received sentry orders on 114. Subsequent Istanbul requests failed for lack of units on 115–117. This upstream shortcut counts visible units, making stacking especially relevant. No gameplay changes made during this investigation.
- [ ] Distinguish exposed preparations from a force actually able to deliver an opening attack. Require a viable, suitably staged core and bounded attack ETA, with legal borders, home defense, roles and stacking capacity respected; carry the plan through the declaration instead of releasing distant troops into general duties.
- [ ] Support bounded pre-war reinforcement/production and cooperative preparation where advance notice exists. Preserve immediate-war exceptions for bribes, defensive pacts and forced/team/scripted wars. Expose all new numeric controls in XML and add declaration-reason/readiness/handoff diagnostics plus tests described in the linked review.


## Siege capture support and reassessment (Edirne, turn 138)

- [ ] Maintain a viable capture plan for each siege: reserve a unit that can legally reach, attack and survive taking the city, with a credible arrival time. Coordinate land routes, coastal naval melee or controlled landings across water; do not equate nearby melee strength with capture capability. [Edirne investigation](siege-capture-review.md) records the user's observation and confirms a 32-HP assessment on turn 138. The current log counted one melee candidate, but its identity and actual suitability are not recorded at Summary level.
- [ ] Escalate a missing/failed capture plan into a reinforcement or operation-allocation demand, including sieges performed by tactical units outside an army. Reassess competing objectives and preserve support commitments through the attack.
- [ ] Reassess prolonged bombardment without a feasible capturing force: recruit/route support, retarget or withdraw according to expected benefit and cost. Preserve useful preparatory fire, defender/collateral damage and other concrete objectives. Expose new timing, strength, priority and abandonment thresholds in XML and add capture-candidate/path/rejection/progress diagnostics. No gameplay changes made for this observation.

- [ ] Reproduce the user-supplied Edirne map layout: Russian ranged stack across the inlet, possible Spanish closed borders on the western land approach. Validate actual unit-specific border access and attack/landing routes; test both open/closed borders and feasible/unavailable crossings. The screenshot is archived with the siege review; Spain's treaty status remains unconfirmed.


## Proactive reinforcement of existing attacks (user priority)

- [ ] Begin recruiting, staging and dispatching follow-up support while the initial assault force advances, before casualties where useful. Prioritize reinforcing a viable existing offensive over creating competing attacks; let the initial core depart without waiting for every reinforcement.
- [ ] Maintain target-specific desired strength, role mix and a bounded reserve, accounting once for assigned/training/inbound units. Coordinate surplus troops and new production, safe travel, legal stack capacity, capture support and replacement of wounded units while protecting home/other fronts.
- [ ] Preserve support commitments across war declaration and tactical handoff; cancel/reassign them when the objective or route changes. Make new thresholds/budgets XML-configurable and log actual support progress/arrivals. Detailed scope and acceptance cases: [military AI plan, proactive reinforcements](military-ai-plan.md#3a-proactive-reinforcement-of-an-existing-offensive). Planning only; no gameplay changes made for this request.

- [ ] Address the observed pattern of promising offensives fading through attrition during multi-turn reinforcement gaps. Include recruitment/production, gathering and travel time in support forecasts; dispatch before the frontline drops below useful strength, preserve critical roles, and measure gaps and late-arrival stalls. Reassess attacks whose timely reinforcement is infeasible. This is a user-reported pattern awaiting quantified campaign analysis.


## City HP scales fortification collateral protection

- [x] Scale fortification-derived collateral protection linearly with the city's current HP fraction: effective protection = capped combined building protection × clamp(current city HP / maximum city HP, 0, 1). A full-health city receives 100% of its configured protection; a city at half HP receives 50%; a zero-HP city receives none. Apply the existing combined protection cap before HP scaling so stacking extra fortifications cannot compensate for a damaged city. Example: 90% capped protection becomes 45% at half HP and 0% at zero HP.
- [x] Keep the existing collateral HP floor and ordinary city/garrison damage rules separate. Expose an XML enable/disable setting for the new scaling behavior and retain XML-configurable building protection and the combined cap. Implemented in the 2026-09-29 checkpoint; in-game validation remains pending.
- [ ] Use the same effective protection in actual combat, AI damage forecasts and any protection display. Define and document whether collateral uses city HP before or after the primary hit; the implemented timing is before each hit, including virtual prior city damage. Test full/half/zero HP, cap ordering, no fortifications, healing and capture, integer rounding, and siege/naval/bomber collateral against cities.


## Turn-236 campaign findings: route failures and offensive continuity

- [ ] Prioritize repeated city-attack path-failure loops. [Campaign review](autoplay-236-review.md): 131 of 271 attack-operation instances ended LostPath, 118 on their creation turn; 104 concerned barbarian-held Lutetia. Reconcile target screening with actual unit/muster/centroid routes, repair staging where possible, and add a bounded failed-route/target retry policy. Audit interaction with recent recruitment/gathering changes; the run does not identify the exact failing segment or establish an upstream-only cause.
- [ ] Add failed-segment/legality diagnostics and moving-phase progress/contact review. Spain's Moscow operation lasted 35 turns with repeated no-progress/contact and ended below its required force threshold. Current assembly recovery does not address that entire moving-phase failure mode.
- [ ] Validate persistent reinforcement and capture support against the archived turn-0/236 campaign: 43 of 46 operations observed at least five turns after departure logged no later member additions; Edirne fell to 32 HP then recovered to 430 without capture. Support arriving near an army must not be treated as proof of maintaining its effective force.
- [ ] Use controlled campaigns and detailed city/combat traces to separate AI execution failures from defensive balance. Only three major-to-major conquests occurred in this run, but Summary logging does not quantify fortification/collateral mitigation. Keep the HP-scaled protection item as a balance experiment rather than a proven remedy.


## Stack UI placement above combat preview

- [x] Move the stack UI to sit immediately above the combat preview panel so it does not obscure the combat outcome, damage estimates or modifiers. The user's screenshot shows the current roster overlapping the left side of the preview. Account for expanded/collapsed roster height, scrolling, screen bounds and UI scaling; verify both panels remain readable when the preview appears or changes size. Preserve normal roster use when no combat preview is visible. Implemented in the 2026-09-29 checkpoint; visual in-game validation remains pending.
- Reference screenshot: `C:/Users/rusit/Documents/Codex/Civ5StackMod-analysis/stack-ui-combat-preview-reference/user-stack-ui-overlap.png` (source and SHA256 recorded alongside it).

## Diagnostic efficiency and normal-play access — 2026-09-29

- [x] Review current evidence and remove per-record unbuffered output as the normal policy. Add bounded batching/flush controls and retain an immediate crash-trace option.
- [x] Avoid repeated capacity/role evaluation per stack member; honor the summary interval before and after the first AI pass. Add category masks and bounded Verbose windows.
- [x] Add compact Summary combat/capture outcomes, operation production/staffing snapshots, incoming-attack filters and first-pass logger cost records.
- [x] Add Ctrl+Shift+D map access in normal play while the diagnostics button stays hidden. Validate actual Lua input bridges offline.
- [ ] Measure whole-autoplay improvement, live shortcut/input behavior and logging-enabled gameplay equivalence in the next prepared game. See [review](diagnostics-review.md).
- [ ] Consider target-selection score explanations, objective-linked losses/arrival gaps and AI-subsystem timing if the compact results identify a need.


## Coordinated siege staging and committed capture support — 2026-09-30

[Memphis and Djenne review](siege-staging-review.md) records the ongoing fresh autoplay and exact evidence. No gameplay changes made for these observations. Djenne reached 1 HP on four recorded turns, while seven capture-pass assessments in turns 130–143 had zero eligible melee; possible capturers two to five turns away kept the missing-capture timer at zero. Memphis repeatedly failed the current damage gate while its offensive suffered attrition. The danger system already counts visible stacked ranged defenders; the new work is coordinating commitment and timing.

- [ ] Reserve a particular viable capturer, dispatch it with an actual target commitment and track route/ETA progress. Separate candidates, committed arrivals and executable capture orders. Do not let rotating or stationary candidates indefinitely reset siege reassessment. Respect other fronts, civilian protection, legal final attacks, capture survival and replacement needs.
- [ ] Maintain a shared gather/commit/reassess phase and safe staging area for both active armies and loose tactical sieges after handoff. Choose staging outside the combined city/defender attack footprint using existing visibility-limited danger forecasts; account for movement, terrain, range, stack capacity and reachable positions instead of assuming ring two or three is safe.
- [ ] Move a sufficient ready wave into attack range within one AI turn. Evaluate healthy core/roles, expected retaliation and net city damage, committed capture ETA and timely reinforcements. Preserve opportunistic captures and useful safe fire; bound waiting, handle unsafe/blocked staging and reassess when the plan changes.
- [ ] Coordinate early reinforcement dispatch, arrived reserves and wounded rotation so waiting units are not consumed piecemeal. Keep the existing tactical search limits; use cheap bounded objective assessments and cached threat/path work.
- [ ] Add efficient Summary phase/progress/threat/readiness records and distinguish ranged softening from a capture order/result. Retain filtered Verbose candidate/path detail. Make every new numerical threshold, timing window, priority, work budget and diagnostic interval XML-configurable.
- [ ] Validate strong/weak cities, delayed or failed capturers, ranged defender stacks, mobile/long-range threats, chokepoints, blocked borders, naval/cross-water routes, post-handoff sieges, home-defense competition and bounded wait/reassignment. Measure launch delay, exposure losses, reinforcement gaps and low-HP capture conversion in comparative campaigns before balance changes.

- [ ] London follow-up: share insufficient-assault decisions with city-zone positioning/postures, so forces do not remain exposed in low-value skirmishes while bombardment is erased by healing. Compare safe staging/reinforcement, useful field/garrison damage, blockade and retreat/retarget costs. The turn-163 London simulation retained all 12 supplied units; raising the 13-unit search cap is not supported by that example. Audit the separate hard-coded 13-turn siege-damage horizon and make any new/revised number XML-configurable.
- [ ] Add stable attacker/defender IDs and owners, plus city-versus-unit attacker kind, to compact combat diagnostics. The London Summary trace explains weak city damage but cannot identify every wounded unit or distinguish city shots from unit shots. Reuse captured combat participants; avoid new map scans or unrestricted Verbose logging.
