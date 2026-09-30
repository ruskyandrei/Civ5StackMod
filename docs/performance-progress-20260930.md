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

## DLL53: denied-city attack fix measured

`6f383711c` built as `Release-5.4.6-53-g6f383711c Clean`, in
`work/msvc-output/Release/20260930-214752`. Installed DLL SHA256:
`F6B4A2F0E6E3063B99BBB666A760271ABF57EDAB3AD5E269E55EC37AB03FAF9C`.
The matched manual251 replay is `work/test-runs/perf-d53-manual251-citygate`.
The measured252 window fell from77.594s to **48.234s**, PLAN49.908s to15.293s,
with125 to116 searches. The 30-second target is not yet met.

The Utrecht plans cost35.335s before and2.270s after the fix. Across turn252,
city-attack-gate execution failures fell16 to0, total retries22 to4, and retries
with unchanged ordered basic unit state13 to0. Remaining retries involved actual
movement/combat/visibility changes. The fix deliberately changes actions: two
additional field-combat records occurred; no city capture was exercised. Utrecht
remained Dutch,82 damage of534HP after253. Final census850 units and81 cities;
normal API quit completed, no new crash dump. This is not a conquest result.

All recorded phase intervals cover33.516s of that48.234s window;14.716s remain
outside those scopes. Roughly9.721s lies between major-player turn processing and
the first actual unit-AI pass. These are wall-clock gaps, not yet evidence of CPU
work, intentional delays or renderer cost. Next instrumentation measures the
pre-AI script hook/busy guard and thread CPU time with bounded aggregate rows.

### Benchmark boundary correction

The earlier manual251-to253 runs used an identical bounded autoplay setup, but
the ending boundary includes return-to-human processing: `CvGame::doTurn`
decrements autoplay before incrementing the game turn. Their95.938/77.594/48.234s
windows are useful matched samples, not proven steady observer-turn timings.
The next control/candidate runs use251-to254 and measure252-to253 while autoplay
remains active at both boundaries. Exclude the final return-adjacent interval.
Retain the same immutable source, normalization, options and diagnostics.

Exact optimization candidates now being integrated separately from the city-gate
fix: caller-local full danger outcomes behind the existing scalar cache, and a
genuine VC9/x86 acquire read replacing redundant Interlocked read-modify-writes.
Both retain cache invalidation/ownership checks and search/entry budgets. Their
isolated tests do not establish a whole-game performance gain.

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

## Steady-observer control before the outcome-cache candidate

`perf-d53-steady251-control` completed manual251-to254 and quit normally;
native run `Stacking-20260930T211159-845-p16080-r1`. Interior252-to253 is
**45.033s**, PLAN14.757s over116 searches, with17421ms in measured phase
work outside PLAN and about12.9s outside selected-turn phase scopes. This
confirms that returning to a human did not explain most of the earlier48s.

The following253-to254 interval is132.188s, PLAN99.943s over139 searches.
It includes the final return transition, but that cannot explain the99.943s
of measured search. Multiple large Arabia plans around Utrecht dominate;
actual movement/combat changes and a city capture occur during the retries.
Preserve this harder case for correctness and performance comparisons instead
of presenting252 as a general late-game result. Detailed retry analysis is
in progress; do not simply suppress retries after real state changes.

The next candidate leaves search, score, actor and cache-entry limits unchanged.
It reuses complete damage outcomes locally in protector/source-leaving queries,
retains the original scalar fallback, and uses the documented genuine VC9/x86
acquire-read semantics for owner/epoch reads while retaining atomic writes.
Sampled entry-hook/busy timing and absolute same-thread CPU counters distinguish
script/lock waits from work between existing phases. Offline numerical/thread
fixtures establish bounded equivalence, not measured native speed gains.
