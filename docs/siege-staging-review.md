# Coordinated siege staging and capture commitments

Recorded 2026-09-30 from the ongoing fresh Summary autoplay. This review adds follow-up work; it does not change gameplay, the deployed DLL, diagnostic settings or the running game.

## Evidence

Run `Stacking-20260929T230114-513-p30344-r1`, DLL `Release-5.4.6-18-gef5f17dc6 Clean`. Frozen native segments 00/01 and nine relevant VP log files are preserved in `C:/Users/rusit/Documents/Codex/Civ5StackMod-analysis/siege-review-20260930`. The native copies contain 53,119 records spanning turns 0–146; this is a snapshot, not a completed campaign. `analyze_sieges.py` produces `siege-evidence.json`, including input SHA256 hashes and the selected records with file/line references. Ordinary VP logs lack exact native event ordering and unit positions at Summary level.

### Celts attacking Memphis

Memphis is Egyptian city 1307 at (66,45), plot 4026. Operation 2237 recruited seven units into a nine-slot formation on turn 101, departed on 103, contacted enemies on 107/110 and handed off to tactical control on 111. Its logged completion on 112 means the operation reached its handoff condition, not that Memphis fell. The native operation snapshots show seven members on 108/109, six on 110/111, one replacement needed and no replacement training at those latter snapshots.

During turns 101–115 the recorded capture gate rejected the city eight times for insufficient damage and three times for no eligible units. On turns 108–114 the nonempty assessments had only one to five current candidates, with expected damage of 16–33 against city healing of 16 and required damage of 360–410. These are candidates for that tactical pass, not a census of all troops assigned to the offensive. Celtic tactical logs record horsemen killed by Egypt on 109 and 114; they do not establish that Memphis or its ranged garrison delivered those particular kills.

The user's observation of piecemeal exposure is consistent with a coordination gap. The logs establish inadequate current attack capability and attrition, but do not prove the location or source of every casualty.

### Polynesia attacking Djenne

Djenne is city 1083, owner 28, at (13,49), plot 4325. Polynesia's seven-unit operation 1605 began on 59, contacted enemies and handed off on 62, then ended with `Success` on 63. That success is also a handoff result. The archived operational log contains no new city-attack operation during turns 90–145; the continuing siege is visible in tactical/native logs.

In the turn 130–143 window:

- Seven `CITY_GATE reason=attempt` records all contain `melee=0`. Other gates report three no-eligible results, one insufficient-damage result and two enemy-dominance results.
- Actual ranged combat reduced Djenne to 1 HP on turns 133, 134, 136 and 137, without a recorded ownership change. Some further shots at 1 HP still damaged the ordinary garrison; these cannot automatically be called useless fire or new collateral.
- The broader `CAPTURE_PLAN` repeatedly accepted a candidate at an estimated two to five turns away, alternating land and sea units. Every recorded missing-capture timer was zero. Unit 2941's estimate rose from four to five turns; unit 2820's rose from two to three to four; finding a possible candidate did not imply progress toward capture.
- A separate support record shows unit 2213 travelling toward Djenne on turn 143 with ETA two. This is evidence of dispatch, not proof of arrival or capture.

The exact reasons particular candidate units did not arrive are not established by Summary data. Nevertheless, the code identifies a structural reason the siege can keep treating capture support as available despite its absence locally.

## Code findings

`CvDangerPlots.cpp`, `UpdateDangerSingleUnit`, `AssignUnitDangerValue` and `CvDangerPlotContents::GetStackDanger`, already consider the city's ranged attack and individual visible enemy units. Attackers are deduplicated by owner/unit ID, so co-located ranged defenders are not collapsed into one threat. Stack defender selection and collateral are included. A new staging policy should reuse this machinery and audit its assumptions rather than introduce a second inconsistent danger calculation.

`CvTacticalAI.cpp`, `PositionUnitsAroundTarget` (around line 3457), runs a local low-aggression combat simulation, then approaches remaining units individually using an approximate ring-two path. Ordinary combat units can accept endpoint danger up to half their current HP. Protected siege approaches have a separate allowance. These checks do not provide a target-wide decision to wait for a sufficiently strong wave, and ring two is not inherently outside city or defender firing range. Both gathering and loose tactical reinforcements use this positioning path.

`CvStackingOffensiveAI.cpp`, `CapturePlan` (around line 161), resets the candidate every turn and accepts the first surviving unit with a plausible adjacent native-domain path within the configured horizon. It respects other army/objective assignments, but does not reserve the accepted candidate, issue it an arrival order or require its ETA to improve. Its route ends adjacent to the city; it does not certify the final executable capture order. Accepting any candidate resets `noCaptureSince`. `ContinueSiege` (around line 540) therefore cannot trigger its missing-capture review while such candidates keep being found.

`AddDemands` counts potential capture roles among local/committed support without maintaining a particular executable capture commitment. After an operation ends, its staging plot becomes the target city itself. Reinforcement safety filters can reject transfers, but there is no shared safe collection area for a siege conducted outside an active army.

`CvTacticalAI::ExecuteCaptureCityMoves` (around lines 925–1003) allows the attack gate to proceed with no eligible melee if the city has more than 1 HP. The `attempt` label can therefore mean ranged softening. It is not evidence that a melee capture order was issued. The actual simulator correctly prevents ranged capture; diagnostics should expose the distinction.

## Proposed work, in priority order

1. **Maintain an executable capture commitment.** Separate possible candidates from reserved, travelling, ready and failed capturers. Prefer credible arrival and survival over first unit iteration order. Preserve a selected capturer across turns, coordinate allocation priorities, verify legal approach and final attack, and retain a replacement option. Track ETA/route progress; changed candidates must not indefinitely reset the stall timer. Preserve useful allied capture opportunities and home-defense obligations. Apply to land/naval capture and tactical sieges after army handoff.
2. **Share a siege phase across army and tactical attackers.** Gather, commit and reassess using the target's existing objective. Select legal, reachable staging plots outside the combined city/defender attack footprint, accounting for movement, range, terrain/line of sight, nearby enemies, stack capacity and known fog danger. Do not hard-code a universal distance of three tiles. If no safe area exists, compare a bounded assault or alternative target rather than oscillating or waiting indefinitely.
3. **Assess a wave and advance it in the same AI turn.** Require a healthy fighting core, protection for vulnerable units, sufficient expected city damage after healing, and an actual capture plan. Account for the enemy response during the waiting period and credible reinforcement ETAs. Check that enough units can reach useful firing/attack positions that turn; an inaccessible or full stack must not count as ready. Let useful safe bombardment continue and retain opportunistic captures of weak targets. Do not wait for every reinforcement. Use hysteresis, bounded gathering time and reassessment when support, target or routes change.
4. **Prevent attrition while waiting.** Keep arriving support at the shared staging area, preserve capture/screen roles, replenish before effective frontline strength collapses, and rotate wounded units when feasible. Release or redirect stalled commitments when reinforcement cannot arrive in time. Preserve the existing 13-unit/6,000-state tactical search bounds; army-wide readiness must be a cheap bounded assessment, not a combinatorial search over every troop.
5. **Add compact explanations and validation.** Summary should record siege phase/reason changes and periodic compact snapshots: ready versus inbound roles, committed capturer and ETA/progress, city/defender threat, projected losses, net city damage, staging choice and launch/stall reason. Distinguish bombardment from a ready capture and actual capture order/result. Put detailed candidate/path rejections in a filtered Verbose window. Cache per-objective work, honor existing diagnostic filters/intervals and bound path/threat queries.

All new numeric controls belong in XML: gathering/reassessment windows, readiness and health margins, capture progress/arrival windows, reinforcement credit, role priorities, threat budgets, tolerable exposure/loss and diagnostic cadence. Select defaults after fixtures and campaign measurements; do not use a larger generic attack cap as a substitute for coordinating the units already assigned.

## Acceptance and campaign follow-up

Offline fixtures should cover a city with several ranged defenders and delayed reinforcements; a weak city that should be taken promptly; mobile/long-range defenders; narrow approaches and full stacks; blocked borders and water crossings; a capturer claimed by another duty, killed or stationary; post-handoff tactical sieges; naval capture; useful ranged-only support and no safe staging area. Preserve fog restrictions, deterministic ordering, save/reload recovery and disabled-setting behavior. Distinguish policy-stub checks from real pathfinder/game validation.

Use short in-game siege fixtures followed by fresh comparative autoplays. Measure exposed-unit losses before the main wave, reinforcement gaps, capturer ETA progress, launch delay, and low-HP-to-capture conversion. Existing Summary logs support this review but do not quantify every defender's contribution or prove stacking balance needs a defensive nerf. Record selected Verbose windows only where they resolve a specific ambiguity.


## America outside London, turns 160–168

The user reported numerous American units around London, a single Knight defending inside with some ships, little persistent city damage and severe attacker attrition. A second read-only snapshot is preserved in the archive's `london/` directory: native segments 00–02, American/English operational, tactical and military logs, and `london-evidence.json` with hashes and source row references. No gameplay or diagnostic settings were changed.

London is English city 1074 at (15,24), plot 2127; England is player 4 and America player 7. City attack traces repeatedly begin at 470 HP. Recorded American ranged attacks produced these city-HP losses:

| Logged turn | Total city HP lost in recorded American attacks |
| --- | ---: |
| 162 | 19 |
| 163 | 15 |
| 164 | 17 |
| 165 | 20 |
| 166 | 27 |
| 167 | No recorded American city attack |
| 168 | 10 |

The gate estimated healing at 23 HP per turn. That estimate and repeated full-health pre-hit snapshots explain why the city could look undamaged after successive weak bombardments. The record does not establish every exact healing modifier, and deferred animation resolution means an event's logged turn is not a complete synchronous per-turn ledger. Ordinary garrison absorption is also present: for example, the turn-162 hit inflicted 19 on the city and 9 on one garrison/bystander. This is separate from the 25% fortification collateral protection reported at full health; that protection is not a 25% reduction to primary city damage.

On turns 162–165 the capture gate estimated only 37–48 damage from seven to nine current candidates against 470 city HP and healing of 23. Its existing 13-turn net-damage test rejected a city assault every time. `P_STEAMROLL` on 162/164 and `P_EXPLOIT_FLANKS` on 163/165 nevertheless performed local low-aggression simulations around London. The turn-163 simulation retained all 12 supplied units and used 2,293 search positions, so the 13-unit cap was not trimming that particular force. Actual city hits in this window are ranged; there is no recorded American melee attack on London. A nominal viable capturer with ETA zero was repeatedly assessed, so this siege differs from Djenne's absent local capture support: London's city-health/damage deficit remained the immediate attack gate.

English counterattacks are recorded on nearby plots. Examples include ranged hits of 23 at (14,23) on 160 and 42 at (16,22) on 162, and a melee attack at (15,23) on 163 inflicting 21 and receiving 36 retaliation. These show combat around London, not merely ships sitting in harbor. American tactical logs also record a Trireme killed by England on 165 and a Spearman killed by England on 166; those lines lack locations and cannot prove both deaths occurred at London. Summary combat omits participant IDs, types and defender owner, and does not distinguish an attacking city from an attacking unit, so exact attribution of the wounded American roster needs a more detailed saved-position replay or additional compact fields.

The user's harbor-fire assumption matches the deployed code/configuration. `NewCustomModOptions.xml` enables `CORE_NO_NAVAL_RANGED_ATTACKS_FROM_CITIES=1`; `CvUnit::isNativeDomain` rejects ships on a city land plot under that option, and `canRangeStrike` requires a native domain. Docked ranged ships cannot fire from there with these settings. This does not stop ships that leave the city or other nearby defenders from attacking.

This case strengthens the need to share the siege-readiness decision with positioning and tactical postures. A rejected assault should lead to safe collection/reinforcement, a sufficiently damaging coordinated attack, or a bounded reassessment. Local skirmishing can remain useful when its expected benefit justifies its attrition, but it should not consume the force needed for a viable assault while city damage is erased by healing. Check blockade opportunities and garrison/field-unit damage as concrete benefits rather than banning every attack after a capture-gate rejection. Audit the hard-coded 13-turn siege horizon and expose it to XML if changed; it is distinct from the 13-unit tactical-search cap.

Add low-cost stable attacker/defender IDs, owners and city-versus-unit attacker kind to Summary combat, without per-event map scans. Together with siege-phase reasons, this will let future traces distinguish city fire, defender attacks, American attacks on field units, and ineffective city bombardment. Put unit type/position detail in bounded snapshots or filtered Verbose windows. London's evidence supports an execution/coordination issue; it does not by itself demonstrate an excessive defensive bonus introduced by stacking.


## Campaign follow-up reported at turn 204

Recorded 2026-09-30. The game continued during this read-only investigation; the frozen snapshot in `C:/Users/rusit/Documents/Codex/Civ5StackMod-analysis/siege-review-20260930/followup-turn204` contains native turns 0–208 plus the relevant Polynesian/Celtic/English VP logs. `followup-evidence.json` records input hashes and selected event references. Conclusions below about campaign progress use captures through turn 204. No game interaction or gameplay changes were performed.

The native logs confirm Memphis changed from Egypt to the Celts on turn 195. On 193 recorded ranged attacks reduced its HP from 145 to 73; on 194 further attacks reduced 97 to 4. On 195 its capture gate listed 17 candidates, eight eligible melee, required damage 37 and expected damage 153. A ranged hit reduced the city from 37 to 3, then a melee attack with 31 retaliation captured it. This demonstrates a successful bombardment-plus-capture sequence with a substantially larger available force than the early attack; it does not identify every participating unit type or establish that all seventeen contributed. Deferred combat resolution also limits exact synchronous turn-ledger interpretation.

English combat captures through 204 include Philadelphia on 190, Los Angeles on 193, Seattle on 195 and San Francisco on 203. Their old/new city IDs and ownership changes are recorded. At Philadelphia the last ranged hits reduced 77 HP to 1, followed by a melee capture with 29 retaliation. The user's observation identifies the navy as the successful force; Summary combat does not itself record the capturing unit's domain. These outcomes are useful positive comparison cases for coordination, capture capability and damage exceeding healing, rather than proof that every offensive is healthy.

### Djenne's siege has faded while the war continues

Polynesia's last recorded attack on Djenne was ranged fire on turn 137. No Polynesian melee attack on the city is recorded anywhere in this snapshot. Early capture-gate assessments sometimes had one or two eligible melee (24 of 40 `attempt` assessments across the complete snapshot); that label still did not become an actual melee order/result. The previously reviewed 130–143 window remains a distinct seven-assessment case with zero eligible melee.

The land zone has continuously used `P_WITHDRAW` from 146 through the snapshot's last tactical record at 208. Thus the turn-204 observation follows 59 consecutive turns of withdrawal posture. City attacks from another owner are recorded later, including player 63 ranged fire on 179 with Djenne at 422 HP before and 414 after; that is not Polynesian bombardment. Do not assume the city has stayed at its former 1 HP throughout the war.

No replacement city-attack operation targeting (13,49) is present after the original operation's handoff on 62/63. Polynesia has since recruited attacks against other coordinates. Its current military target scoring still mentions Djenne, but that does not prove an army was committed or a restart feasible.

The support history includes these attempts with no recorded `front_arrival` or `joined_formation` for the target:

| Dispatch turn | Unit | ETA | Release turn |
| --- | ---: | ---: | ---: |
| 143 | 2213 | 2 | 149 |
| 146 | 2535 | 2 | 152 |
| 170 | 3792 | 1 | 176 |
| 179 | 3760 | 1 | 180 |

These releases are not proof the units never moved or died: the existing `release_stale` label conflates an unusable/missing unit, vanished objective and stale recorded progress. Identity, route and actual movement need explicit diagnostics. Progress is currently updated by `RecordTransfer`, so later tactical movement can occur without a new transfer/progress record.

### Confirmed objective-expiry edge case

The target's land objective expired on 154 and again on 180. A capture plan/observation on 167 reconstructed/refreshed it; support was dispatched to that same objective on 179, but the objective expired immediately on 180 and unit 3760 was released in the same refresh.

`CvStackingOffensiveAI::Refresh` expires an inactive objective when `turn - refreshed` exceeds `AIOffensiveSupportMemoryTurns` (default 12). `RecordTransfer` updates the unit commitment without refreshing or revalidating the corresponding objective lifetime. Consequently a valid dispatch at the end of the memory window can lose its objective before its promised arrival. The observed 167/179/180 sequence matches that code path. Simply increasing the memory setting delays the same boundary and is not a complete fix.

Planned fix: revalidate target ownership/war, route and objective value before accepting support; keep the objective alive while credible committed support is progressing, or reject/cancel that dispatch deliberately with an explicit reason. Maintain bounded expiry for genuinely obsolete or stalled targets, and distinguish expired observation memory from a strategic choice to abandon the siege. Check actual unit movement as well as transfer records when aging commitments. Record each release's cause and objective age, last progress, dispatch age and ETA compactly.

`PlotReinforcementMoves` also returns immediately for withdrawal posture. Capture-gate observations are intermittent and ceased for this target after 181 in the snapshot, allowing the handed-off objective to disappear while the war remains active. A bounded strategic review must operate independently of local capture selection: either assemble a credible new force, retain a deliberate lower-cost objective, or stop feeding support into an abandoned attack. Diplomatic peace remains governed by the existing diplomacy system; these logs alone do not establish that continuing the war is itself a diplomacy bug.

Acceptance additions: support dispatched one turn before objective expiry; moving support crossing a tactical handoff; credible ETA progress with no new transfer call; genuinely dead/reassigned/stalled support; withdrawn-but-still-at-war target; deliberately abandoned target; renewed low-HP capture opportunity; successful Memphis/naval capture controls. All new expiry grace, review intervals and work budgets remain XML-configurable. Compare whether promises result in actual arrivals and capture orders, not just recruitment or candidate logs.


## User map reference at turn 210

The user supplied the Djenne screenshot at turn 210. The original image is preserved as `C:/Users/rusit/Documents/Codex/Civ5StackMod-analysis/siege-review-20260930/followup-turn204/djenne-layout-reference.png`, with its source path, SHA256 and byte count in `djenne-layout-reference.json`.

The screenshot shows Djenne directly north of Polynesia's core, with Tahiti to its west and Honolulu/Samoa to the south. There is substantial adjoining land and roads near the approach. Portugal's Goa is to the east. This layout does not show an obvious mandatory naval crossing or isolated overseas objective, and it is consistent with the short approach ETAs recorded for some support units. The image does not certify each unit's final attack path or availability; the regression should verify roles, health, other commitments, terrain/stack congestion and legal paths using actual game services.

Use this as a specific accessible-core-city regression: while the war continues, a withdrawn/expired local siege must still receive a bounded strategic assessment. If feasible, assemble nearby healthy siege, screens and a reserved capturer, preserve progressing arrivals through objective expiry, and execute the assault as a coordinated wave. Otherwise record a deliberate reassessment/reassignment with a reason. Do not require conquering this target irrespective of other fronts, but do not let proximity, existing roads and newly dispatched support disappear from consideration because the tactical zone is withdrawing or observation memory expires.

The map supports prioritizing allocation/commitment and assault execution over a generic sea-crossing explanation. It complements the confirmed 179/180 expiry edge and the absence of recorded Polynesian melee city attacks; it does not by itself establish which individual troops could have captured Djenne at its earlier 1-HP windows.
