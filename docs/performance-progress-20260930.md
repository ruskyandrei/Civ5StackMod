# Resumed late-game performance work — 30 September 2026

Target: complete turns250+ below30 seconds while preserving useful AI behavior.
The previous matched post240 test improved full241 from83.109s to70.469s under
DLL50 with matching recorded outcomes. That remains above the goal.

## Direct late-game control

The preserved manual251 save loads successfully under DLL50. An explicit new
`--source-mode human` test path validates the paused human return-player state,
then enters observer autoplay. VP deliberately chooses diplomacy/production/
research/policies during that slot transition. Compare only identical saved
source and preparation across builds; this is a normalized replay branch,
not proof of identity with the original uninterrupted campaign.

- Source: `work/test-runs/campaign47-20260930-1735/Stack DLL47 Campaign Manual Stop T251 20260930-1735.Civ5Save`.
- SHA256: `2A31D7020FFA5348582DD46442D079308CEDC7880248C1B1623A39FF62BC659B`.
- Control folder: `work/test-runs/perf-d50-manual251-control`.
- Native run: `Stacking-20260930T200459-934-p39284-r1`.
- DLL50 SHA256: `2B97CEE47B2D8CF8EDC1377DC9FB2F62CF8860BEFFF65D6A1557387F2E85E4E3`.
- Bounded251→253, human return0; complete comparable turn252 is **95.938s**,
  with **67.526s PLAN** over125 searches and28.412s outside PLAN's recorded sum.
- Final census:850 units,81 cities. Source save hash remains unchanged.
- Loaded and stopped correctly, then closed through the normal API. Process
  exit code was unavailable; no claim of exit0. CPU/GPU guards stayed below
  sustained cutoffs. A new candidate comparison is required before claiming
  any additional speedup.

Phase analysis now also includes adjacent-turn phase records whose time bounds
overlap the chosen legacy-comparable window. In this252 control,391ms of253
preparation was previously outside the selected-turn-only accounting. All
recorded phase unions leave10.124s unattributed; this is wall-clock time and may
include engine scheduling/callback/rendering. It is not proof of pure CPU work.

## First candidate prepared

Complete maximum melee attack/defense strengths are memoized inside the
existing locked preview scope, while retaining the original math bodies.
Keys include raw NULL-plot semantics, both city/opponent attack counters,
projected wounds, embark flags and same-promotion attack history. Scripted
movement-event paths in HeavyCharge and nonquick city blockade bypass full
attack reuse. Existing cache capacity and gameplay/search limits are unchanged.
Separate full-attack/full-defense hit/miss counters expose additional cache
pressure rather than hiding it.

Offline actual-source full-body comparison:140,042 checks passed; existing
generic/ranged/cache checks:96,078 passed. Engine services are deterministic
substitutes, so native outcome and timing comparisons remain necessary.

Compact `PLAN_EXEC_FAIL` and `PLAN_RETRY` Summary diagnostics were added to
explain rejected orders. The latter logs bounded ordered IDs and basic-state
signatures; equality does not establish complete tactical scene identity and
does not drive gameplay.89 actual-source diagnostic checks and16 batch checks
pass. Retry limits and the discovered legacy A_USE_POWER behavior are unchanged
pending runtime evidence.

In the252 control, Arabia's operations repeatedly search target25:25. Several
5–7s attempts have matching work counts and no intervening COMBAT record.
Two earlier attempts do execute ranged hits, so those are changed-state
replans. The new failure diagnostics are needed to identify the repeated
failures; Summary counts alone do not justify deleting retries.

## DLL52 native result and the next correctness fix

`c2de0e55f` built as `Release-5.4.6-52-gc2de0e55f Clean` in
`work/msvc-output/Release/20260930-212752` (179 translation units,75.015s).
DLL SHA256: `8B0440069823C61A54CB15AE65031A0E1868982C8DE136E22602757600E5350A`.

Matched manual251→253 run: `work/test-runs/perf-d52-manual251-candidate`,
native `Stacking-20260930T203510-790-p37228-r1`. Full252 fell from95.938s to
**77.594s**, with PLAN67.526s→49.908s over the same125 searches. All274 retained
semantic records match (199 PLAN,75 COMBAT_SUMMARY), with identical847-unit
before and850-unit after censuses,81 cities and23 players. No capture branch
was exercised. Normal API shutdown succeeded; no new dump. The game is closed.

The full cache removed most generic-only hits but raised shared-cache evictions
from755,940 to1,921,686 in252. Ranged misses increased2,172,185→2,489,429; complete
attack/defense hits were6,125,306/15,827,936. This is a measured tradeoff, not
evidence that cache capacity should be changed blindly.

New execution diagnostics identify the expensive repeated-plan cause. All eight
Arabia25:25 attempts fail `city_attack_gate`, for ranged units6976/7095 trying
to fire from2138 into city2225. Repeated attempts have equal ordered basic unit
signatures; preceding idempotent mission orders do exist, so this is not a claim
that no calls occurred. Both city-attack scorer gate returns use `SetScore(0,0,0)`.
`IsAcceptable()` rejects only the impossible sentinel, and virtual assignment
application still applies the retained damage payload. A denied attack can
therefore influence a plan and then fail execution repeatedly.

The next candidate changes those two denial returns to `SetImpossible()`,
preserving `AllowCityAttack` policy and search/retry limits. This is an intended
correctness change, so subsequent actions/outcomes may differ; exact old-plan
equivalence is no longer the acceptance test for that fix. Validate denied
actions cannot enter virtual plans, preserve allowed/capture paths, then inspect
runtime failures and complete-turn times. Ledger production remains on hold
until this simpler fix is measured.

The source fix and39 actual-source checks are ready: the old control admits
50 points of phantom city damage; rejected fixed actions cannot enter the
candidate list or advance the virtual city state. Allowed/capture/unit-combat
paths retain their outputs. Native evidence identifies target2225 as Utrecht
(Netherlands); the eight Arabia plans cost35.335s total, including valid earlier
orders before failure. This is not a claim that all35.335s can be eliminated.
See `work/test-runs/perf-d52-manual251-candidate/denied-city-attack-review.json`.

## Further candidates

- Caller-local reuse of complete stack damage outcomes behind the existing
  scalar cache. An isolated exact-source split prototype passed288,016 checks
  with numerical services substituted; field/city/air/collateral loop order,
  off-stack AA wounds, raw-ID aliases, city-fall sentinels and hazards are
  covered. Production integration is held until the first candidate is tested.
- If full strength keys cause eviction pressure, project only proven equivalent
  injury modifiers/thresholds in the key, keeping original math and bounds.
- Diagnose actual execution failures before changing retry behavior.
- Measure the pre-unit-AI Lua hook/busy guard and engine dispatch gaps with
  aggregate timing; do not create per-poll logging or assume a fixed delay.
- City production, homeland and operation execution are secondary measured
  costs. Unit sorting/visibility were tiny in241. Legacy compiler LTCG is
  disabled because of earlier linker hangs; avoid treating toolchain changes
  as a proven improvement.

All new work remains local unless explicitly pushed. Preserve both the original
DLL47 and DLL50 controls, saved inputs, normal-exit records and crash evidence.
