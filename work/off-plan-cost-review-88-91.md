# Late-turn cost outside the PLAN search timer

Read-only native/source review, 2026-10-01. Controls are quiet DLL88 repeat
`perf-d88-indexed-store-off-r2-251-255` and DLL91 OFF
`perf-d91-kernel-probe-off-251-255`, turn253. No source edit, game connection,
compiler, or benchmark. Core inspected at DLL91; documentation-only commits
do not change these emitter bodies.

## What the existing measurements actually cover

| Measurement | Quiet88r2 | DLL91 OFF |
|---|---:|---:|
| Legacy-comparable native event window |57.531s|58.672s|
| Estimated PLAN interval union |33.018s|33.808s|
| Window outside estimated PLAN |24.513s|24.864s|
| Recorded phase union outside PLAN, including intersecting adjacent-turn rows |16.279s|16.646s|
| Residual after phases and PLAN |8.234s|8.218s|
| Activation-to-entry gap union within window |7.768s|7.831s|
| Residual after unioning phases, PLAN, and those gaps |0.468s|0.389s|

Activation gaps overlap measured phases/PLAN by2ms in both runs; this is why
simple subtraction misses2ms. Existing PLAN bounds are inferred from its high
precision duration and coarse emission/finalization ticks, not a native exact
CPU interval. All arithmetic here uses unions; inclusive phase rows are not
summed as exclusive shares.

Within selected turn253, the measured non-PLAN family partition is tactical
7.362/7.526s, homeland excluding tactical2.200/2.154s, and other measured player
scopes6.467/6.732s. Another0.250/0.234s is attributable to phase bounds emitted
with adjacent source turns. These are wall spans, not a claim that all elapsed
time was DLL computation.

## Almost eight seconds is between DLL update entries

`TURN_UPDATE_GAP` reports23 activation markers. Its dispatch total is
7.768/7.831s; same-thread CPU is0.015625/0s. Completed core-lock acquisition,
wrapper body, game body, begin/end hook, pre-moves head, and activation-tail
totals are all0ms at this timer resolution. This does not prove other game
threads or the whole process were idle, and does not identify the particular
engine wait.

The source explains the boundary: `CvGame::update` calls `updateMoves`, then
`CheckPlayerTurnDeactivate` later. The latter activates the next sequential
AI. `setTurnActive(true)` performs its player/city turn and opens the activation
marker. Its first unit AI pass then occurs in the next engine call to
`CvDllGame::Update`. `updateMoves` intentionally selects one active AI and
breaks. There is no existing DLL batching option or fixed delay governing the
measured dispatch span. The optional EXTERNAL_PAUSING sleeps are inside update
and cannot explain time reported between wrapper calls.

Directly calling the next unit AI or looping `update` would change ordered
GameCoreUpdateBegin/End hooks, timer/UI/network/autoplay-pause checks, turn
slices, and busy/mission processing. That is a separate scheduling redesign,
not an exact local speed optimization justified by these logs.

## Broad DLL opportunities, ranked by measured envelope

1. **Tactical work surrounding search: roughly7.4–7.5s.** The operation phase
   has5.055/5.135s outside estimated PLAN; zone attacks have1.617/1.597s. These
   phases are distinct children of dominance, not additional costs to add to
   tactical's envelope. PLAN_PERF setup totals1.704/1.767s and finalize totals
   0.047/0.030s across143 plans. Final support search therefore is not a hidden
   multi-second explanation in this replay.

   A concrete pre-stack candidate is `UpdatePlotDistanceToTarget`: every
   `FindAndExecuteBestUnitAssignments` attempt performs both land and naval
   `GetPlotsInReach` floods BEFORE `FindBestUnitAssignments` starts its setup
   timer. It then clears the distance field at caller return. The simple
   validity callbacks read revealed status, passable terrain/improvements,
   movement capabilities and territory/war permissions; they do not read unit
   HP or ordinary occupancy. Repeated same-target attempts could reuse an exact
   field when these narrower dependencies are proved unchanged. Real movement
   can reveal plots; captures change ownership/passable-city state; callbacks
   can change permissions. A broad scene-epoch assumption is insufficient.
   There is no isolated flood timer yet, so this is a strong structural
   candidate, not a measured share of those five seconds.

   Native execution, spotter/assembly/approach paths, target/recruit scans and
   mission-triggered danger/visibility refresh also lie outside PLAN. They
   mutate the live world; cached preview results cannot simply be reused across
   them. Existing PATH sampling covers generic FindPath/VerifyPath, including
   these queries when selected, but its bounded selected-row coverage must be
   retained when attributing outside-PLAN opportunities.

2. **Player preparation/city work: roughly6.5–6.7s total, city doTurn2.922/
   2.919s.** The city's same-thread CPU totals are2.891/2.953s. Economic AI is
   0.907/0.923s, player_prepare1.812/1.953s, and diplomacy0.545/0.658s; parent
   scopes overlap these children. `CvCity::doTurn` performs citizen optimization,
   strategy/production, economic valuation and multiple yield updates. A
   specific exact reuse seam is one iteration of `OptimizeWorkedPlots`:
   `GetBestOptionsQuick` evaluates plot/specialist yield payloads, then selected
   options rebuild those payloads for pair scoring before `DoApplyTileChange`.
   Returning/retaining selected immutable payloads within that iteration could
   remove duplicate extraction without pruning options or changing score/tie
   order. The cache must end at applied changes and the subsequent
   `gCachedNumbers.update(...,true)`. No subphase measurement yet proves which
   city component dominates; the entire city envelope is under three seconds.

3. **Homeland work: roughly2.2s.** `Update` calls builder planning, worker-region
   reachability, target discovery and ordered civilian/military moves. These
   include raw danger/path evaluation and mutable execution. A shared immutable
   topology/visibility preparation service may benefit both homeland and
   tactical callers, but safe per-query reuse is preferable to a new turn-wide
   cache with incomplete mutation hooks. The whole envelope is measured;
   attribution to builder/worker/other moves is currently unknown.

## The resource validation loop is real, but small here

`setTurnActive(false)` unconditionally computes resourceTypes×all-map counts,
then city×yield×minor friendship/alliance expectations before asserting. A
single plot pass could accumulate the same per-resource totals while preserving
modifier arithmetic and checks. However it executes after `unit_ai_update`
ends and before `DoUnitReset`/`unit_heal_reset` starts. Those enclosing gaps over
the eight majors total only92ms/77ms, and contain other teardown work too.
It cannot explain a multi-second deficit in these controls. The266ms largest
remaining residual is the barbarian-end to next-round first-player boundary.

Evidence: each run's `phases253.json` and complete native segment000000;
no missing segments or malformed rows. Relevant source seams: CvGame.cpp
update1620, CheckPlayerTurnDeactivate1744, updateMoves8939; CvDllGame.cpp502;
CvPlayer.cpp setTurnActive33743, player_doTurn10112 and city phase10439;
CvTacticalAI.cpp UpdatePlotDistanceToTarget6108, caller15206, planning timer15272,
operations1387 and setup/search/finalization emitter15596;
CvCityCitizens.cpp OptimizeWorkedPlots1938.
